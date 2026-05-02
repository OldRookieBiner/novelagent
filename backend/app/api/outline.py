"""Outline API routes"""

import json
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.outline import Outline
from app.schemas.outline import (
    OutlineResponse,
    OutlineUpdate,
    ChapterCountRequest,
    CollectedInfoUpdate,
    OutlineGenerateRequest,
)
from app.utils.auth import get_current_user
from app.utils.deps import get_user_settings_or_raise, get_llm_for_context
from app.utils.project import get_project_for_user, get_project_and_outline
from app.utils.workflow import get_or_create_workflow_state
from app.utils.error import format_sse_error
from app.agents.state import (
    STAGE_OUTLINE,
    STAGE_CHAPTER_OUTLINES
)
from app.agents.nodes.outline_generation import (
    generate_outline_stream,
    parse_outline,
    outline_generation_node,
    # 导入章节数计算常量
    DEFAULT_CHAPTER_COUNT,
    WORDS_THRESHOLD_SHORT,
    WORDS_THRESHOLD_MEDIUM,
    WORDS_THRESHOLD_LONG,
    WORDS_THRESHOLD_VERY_LONG,
    WORDS_PER_CHAPTER_SHORT,
    WORDS_PER_CHAPTER_MEDIUM,
    WORDS_PER_CHAPTER_LONG,
    WORDS_PER_CHAPTER_VERY_LONG,
    WORDS_PER_CHAPTER_EPIC,
    MIN_CHAPTERS_SHORT,
    MIN_CHAPTERS_MEDIUM,
    MIN_CHAPTERS_LONG,
    MIN_CHAPTERS_VERY_LONG,
    MIN_CHAPTERS_EPIC,
)
# info_collection_node 已移除，信息收集由前端表单处理

router = APIRouter()


@router.get("/{project_id}/outline", response_model=OutlineResponse)
async def get_outline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get outline for a project."""
    _, outline = get_project_and_outline(project_id, current_user.id, db)
    return OutlineResponse.model_validate(outline)


@router.post("/{project_id}/outline")
async def generate_outline(
    project_id: int,
    request: OutlineGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate outline using AI from collected info with SSE streaming."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot regenerate a confirmed outline"
        )

    user_settings = get_user_settings_or_raise(current_user, db)

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_OUTLINE
    db.commit()

    # Get LLM service
    llm = get_llm_for_context(request, current_user, user_settings, db)

    # Prepare state for outline generation
    # 优先从 inspiration_template 列读取，回退到 collected_info 字典中的 inspiration_template
    inspiration_template = outline.inspiration_template or ""
    if not inspiration_template:
        inspiration_template = (outline.collected_info or {}).get("inspiration_template", "")

    # 导入 LangGraph 流式工具
    from app.agents.streaming import create_single_node_graph, stream_node_events
    from app.agents.nodes.outline_generation import outline_generation_node

    # 构建完整的 NovelState
    graph_state = {
        "project_id": project_id,
        "stage": "outline",
        "collected_info": outline.collected_info or {},
        "inspiration_template": inspiration_template,
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting or {},
        "outline_emotional_curve": outline.emotional_curve,
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": [],
        "chapter_outlines_confirmed": False,
        "written_chapters": [],
        "current_chapter": 1,
        "review_mode": "hybrid",
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": 3,
        "waiting_for_confirmation": False,
        "confirmation_type": None,
        "outline_confirmed": False,
        "llm_config_id": request.llm_config_id if request else None,
    }

    # 创建单节点 graph
    graph = create_single_node_graph(outline_generation_node)
    config = {"configurable": {"thread_id": f"outline-{project_id}"}}

    async def stream_generator():
        """Generate outline via LangGraph and stream via SSE."""
        accumulated_content = ""

        try:
            async for sse_event in stream_node_events(graph, graph_state, config):
                # 解析 chunk 内容用于 accumulated_content
                if sse_event.startswith("data: "):
                    try:
                        chunk_content = json.loads(sse_event[6:].strip())
                        if isinstance(chunk_content, str):
                            accumulated_content += chunk_content
                    except json.JSONDecodeError:
                        pass
                yield sse_event

            # Parse the final outline
            parsed = parse_outline(accumulated_content)
            outline.title = parsed["title"]
            outline.summary = parsed["summary"]
            outline.plot_points = parsed["plot_points"]
            outline.characters = parsed.get("characters", [])
            outline.world_setting = parsed.get("world_setting", {})
            outline.emotional_curve = parsed.get("emotional_curve")

            # 更新工作流状态
            workflow_state = get_or_create_workflow_state(db, project_id)
            workflow_state.stage = STAGE_OUTLINE

            db.commit()
            db.refresh(outline)

            # Send completion event with parsed outline and updated stage
            completion_data = {
                "outline": {
                    "title": parsed["title"],
                    "summary": parsed["summary"],
                    "plot_points": parsed["plot_points"],
                    "characters": parsed.get("characters", []),
                    "world_setting": parsed.get("world_setting", {}),
                    "emotional_curve": parsed.get("emotional_curve"),
                    "confirmed": False,
                    "chapter_count_suggested": outline.chapter_count_suggested,
                },
                "stage": STAGE_OUTLINE,
            }
            yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            # 检查是否有已生成的内容（可能是用户中断）
            if accumulated_content and len(accumulated_content) > 50:
                try:
                    parsed = parse_outline(accumulated_content)
                    if parsed["title"] or parsed["summary"]:
                        outline.title = parsed["title"]
                        outline.summary = parsed["summary"]
                        outline.plot_points = parsed["plot_points"]
                        outline.characters = parsed.get("characters", [])
                        outline.world_setting = parsed.get("world_setting", {})
                        outline.emotional_curve = parsed.get("emotional_curve")
                        db.commit()
                except Exception:
                    pass
            yield format_sse_error(e)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.put("/{project_id}/outline", response_model=OutlineResponse)
async def update_outline(
    project_id: int,
    request: OutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update outline (title, summary, plot_points, collected_info, inspiration_template)."""
    _, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a confirmed outline"
        )

    # Update fields if provided
    if request.title is not None:
        outline.title = request.title
    if request.summary is not None:
        outline.summary = request.summary
    if request.plot_points is not None:
        outline.plot_points = request.plot_points
    if request.collected_info is not None:
        outline.collected_info = request.collected_info
    if request.inspiration_template is not None:
        outline.inspiration_template = request.inspiration_template

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/confirm", response_model=OutlineResponse)
async def confirm_outline(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm outline and move to next stage."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline has required content
    if not outline.title or not outline.summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must have title and summary before confirming"
        )

    # Check if already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline is already confirmed"
        )

    # 从灵感数据计算章节数
    collected_info = outline.collected_info or {}
    target_words = collected_info.get("targetWords", 100000)
    words_per_chapter_str = collected_info.get("wordsPerChapter", "")
    custom_words_per_chapter = collected_info.get("customWordsPerChapter")

    # 计算每章字数
    if words_per_chapter_str == "custom" and custom_words_per_chapter:
        words_per_chapter = custom_words_per_chapter
    elif words_per_chapter_str and words_per_chapter_str != "custom":
        try:
            words_per_chapter = int(words_per_chapter_str)
        except (ValueError, TypeError):
            words_per_chapter = WORDS_PER_CHAPTER_MEDIUM
    else:
        words_per_chapter = WORDS_PER_CHAPTER_MEDIUM

    # 根据目标字数和每章字数计算章节数
    if isinstance(target_words, int) and target_words > 0 and words_per_chapter > 0:
        chapter_count = max(3, int(target_words / words_per_chapter))
    else:
        chapter_count = DEFAULT_CHAPTER_COUNT

    # Update outline with chapter count
    outline.chapter_count_suggested = chapter_count
    outline.chapter_count_confirmed = True

    # Confirm the outline
    outline.confirmed = True
    # Skip chapter count stage, go directly to chapter outlines generating
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/chapter-count", response_model=OutlineResponse)
async def set_chapter_count(
    project_id: int,
    request: ChapterCountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set chapter count for the outline."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is confirmed
    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before setting chapter count"
        )

    # Validate chapter count
    if request.chapter_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter count must be at least 1"
        )

    # Set chapter count
    outline.chapter_count_suggested = request.chapter_count
    outline.chapter_count_confirmed = True

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


@router.put("/{project_id}/outline/collected-info", response_model=OutlineResponse)
async def update_collected_info(
    project_id: int,
    request: CollectedInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update collected info directly (skip chat if desired)."""
    project, outline = get_project_and_outline(project_id, current_user.id, db)

    # Check if outline is already confirmed
    if outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update collected info after outline is confirmed"
        )

    # Update collected info
    current_info = dict(outline.collected_info or {})  # 拷贝以触发 SQLAlchemy 变更检测
    if request.genre is not None:
        current_info["genre"] = request.genre
    if request.theme is not None:
        current_info["theme"] = request.theme
    if request.main_characters is not None:
        current_info["main_characters"] = request.main_characters
    if request.world_setting is not None:
        current_info["world_setting"] = request.world_setting
    if request.style_preference is not None:
        current_info["style_preference"] = request.style_preference

    # 处理新增灵感采集字段
    new_fields = [
        'novelType', 'targetWords', 'coreTheme', 'targetReader', 'era',
        'wordsPerChapter', 'customWordsPerChapter', 'maleLead', 'customMaleLead',
        'femaleLead', 'customFemaleLead', 'protagonist', 'narrative',
        'goldFinger', 'customGoldFinger', 'customGenre', 'customWorldSetting',
        'inspiration_template',
    ]
    for field in new_fields:
        value = getattr(request, field, None)
        if value is not None:
            current_info[field] = value

    outline.collected_info = current_info

    # 同步 inspiration_template 到 independent 列，确保 generate_outline 能读取
    if request.inspiration_template is not None:
        outline.inspiration_template = request.inspiration_template

    # Check if all required info is provided (use new field names)
    target_reader = current_info.get("targetReader")
    has_genre = bool(current_info.get("genre") or current_info.get("customGenre"))
    has_world = bool(current_info.get("world_setting") or current_info.get("worldSetting") or current_info.get("customWorldSetting"))
    has_protagonist = bool(
        current_info.get("protagonist") or
        current_info.get("maleLead") or current_info.get("customMaleLead") or
        current_info.get("femaleLead") or current_info.get("customFemaleLead")
    )
    if has_genre and has_world and has_protagonist:
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_OUTLINE

    db.commit()
    db.refresh(outline)

    return OutlineResponse.model_validate(outline)


