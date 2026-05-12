"""Chapters API routes"""

import json
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.schemas.chapter import (
    ChapterOutlineResponse,
    ChapterOutlineUpdate,
    ChapterResponse,
    ChapterContentUpdate,
    ChapterGenerateRequest,
    ReviewRequest
)
from app.schemas.outline import ChapterOutlinesGenerateRequest
from app.utils.auth import get_current_user
from app.utils.deps import get_user_settings_or_raise
from app.utils.project import get_project_for_user
from app.utils.workflow import get_or_create_workflow_state
from app.utils.error import format_sse_error
from app.agents.state import (
    STAGE_CHAPTER_OUTLINES,
    STAGE_WRITING
)
from app.agents.nodes.chapter_generation import (
    generate_chapter_outlines_stream,
    generate_chapter_content_stream,
    clean_chapter_content,
)
from app.api.workflow import build_initial_state
from app.utils.llm import get_llm_from_state_async

router = APIRouter()


def get_outline_for_project(
    project_id: int,
    db: Session
) -> Outline:
    """Get outline for a project."""
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found. Please create an outline first."
        )

    return outline


@router.get("/{project_id}/chapter-outlines", response_model=List[ChapterOutlineResponse])
async def list_chapter_outlines(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all chapter outlines for a project."""
    project = get_project_for_user(project_id, current_user.id, db)

    # 使用 LEFT JOIN 一次性获取所有章节数据，避免 N+1 查询
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func

    # 获取所有章节大纲，并预加载关联的章节
    chapter_outlines = db.query(ChapterOutline).options(
        joinedload(ChapterOutline.chapter)
    ).filter(
        ChapterOutline.project_id == project_id
    ).order_by(ChapterOutline.chapter_number).all()

    # Build response with has_content flag
    response = []
    for co in chapter_outlines:
        # 检查是否有对应的章节内容（已通过 JOIN 加载）
        has_content = co.chapter is not None

        outline_dict = {
            "id": co.id,
            "project_id": co.project_id,
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "ending": co.ending,
            "target_words": co.target_words,
            "confirmed": co.confirmed,
            "created_at": co.created_at,
            "has_content": has_content
        }
        response.append(ChapterOutlineResponse(**outline_dict))

    return response


async def _stream_chapter_outlines_sse(
    initial_state: dict,
    project_id: int,
    db: Session,
):
    """章节大纲 SSE 流式生成共享函数

    供 create_chapter_outlines 和 replan_chapter_outlines 复用。
    逐章生成章节大纲，progress/done 事件格式统一。
    使用独立 Session 写入 DB，避免请求级 Session 失效。
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.agents.nodes.chapter_generation import generate_chapter_outlines_stream
    from app.utils.llm import get_llm_from_state_async
    from app.utils.workflow import get_or_create_workflow_state
    from app.agents.state import STAGE_CHAPTER_OUTLINES

    try:
        llm = await get_llm_from_state_async(initial_state, db)
        generated_chapters = []

        async for event in generate_chapter_outlines_stream(initial_state, llm):
            if event.get("type") == "progress":
                chapter_data = event.get("chapter", {})
                generated_chapters.append(chapter_data)

                progress_payload = {
                    "chapter_number": event.get("chapter_number"),
                    "total": event.get("total"),
                    "chapter": {
                        "chapter_number": chapter_data.get("chapter_number"),
                        "title": chapter_data.get("title", ""),
                        "scene": chapter_data.get("scene", ""),
                        "characters": chapter_data.get("characters", ""),
                        "plot": chapter_data.get("plot", ""),
                        "conflict": chapter_data.get("conflict", ""),
                        "ending": chapter_data.get("ending", ""),
                        "target_words": chapter_data.get("target_words", 3000),
                    }
                }
                yield f"event: progress\ndata: {json.dumps(progress_payload)}\n\n"

            elif event.get("type") == "done":
                # 使用独立 Session 写入 DB（避免请求级 Session 失效）
                save_db = SessionLocal()
                try:
                    chapter_outlines = event.get("chapter_outlines", generated_chapters)
                    created_count = 0

                    for co_data in chapter_outlines:
                        chapter_outline = ChapterOutline(
                            project_id=project_id,
                            chapter_number=co_data.get("chapter_number", 1),
                            title=co_data.get("title"),
                            scene=co_data.get("scene"),
                            characters=co_data.get("characters"),
                            plot=co_data.get("plot"),
                            conflict=co_data.get("conflict"),
                            ending=co_data.get("ending"),
                            target_words=co_data.get("target_words", 3000),
                            confirmed=False
                        )
                        save_db.add(chapter_outline)
                        created_count += 1

                    # 更新 WorkflowState
                    wf = get_or_create_workflow_state(save_db, project_id)
                    wf.stage = STAGE_CHAPTER_OUTLINES
                    wf.waiting_for_confirmation = True
                    wf.confirmation_type = "chapter_outlines"
                    save_db.commit()
                finally:
                    save_db.close()

                done_payload = {
                    "total": created_count,
                    "stage": STAGE_CHAPTER_OUTLINES
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    except Exception as e:
        yield format_sse_error(e)


@router.post("/{project_id}/chapter-outlines")
async def create_chapter_outlines(
    project_id: int,
    request: ChapterOutlinesGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成所有章节大纲（SSE 流式，逐章进度）

    使用 generate_chapter_outlines_stream 逐章生成，LLM 通过
    get_llm_from_state_async 获取（与 LangGraph 节点相同机制）。
    每章完成时发送 progress 事件，全部完成后写入 DB 并发送 done 事件。
    """
    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before generating chapter outlines"
        )

    if not outline.chapter_count_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter count must be set before generating chapter outlines"
        )

    existing = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outlines already exist. Delete them first to regenerate."
        )

    user_settings = get_user_settings_or_raise(current_user, db)

    # 更新工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)
    workflow_state.stage = STAGE_CHAPTER_OUTLINES
    db.commit()

    # 构建初始状态（传入 db 预加载角色/关系数据）
    llm_config_id = request.llm_config_id if request else None
    initial_state = build_initial_state(
        project, outline, workflow_state, llm_config_id, db=db
    )

    async def stream_generator():
        """逐章生成章节大纲并流式发送进度事件"""
        async for sse_event in _stream_chapter_outlines_sse(initial_state, project_id, db):
            yield sse_event

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.put("/{project_id}/chapter-outlines/{chapter_num}", response_model=ChapterOutlineResponse)
async def update_chapter_outline(
    project_id: int,
    chapter_num: int,
    request: ChapterOutlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a specific chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if already confirmed
    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a confirmed chapter outline"
        )

    # Update fields if provided
    if request.title is not None:
        chapter_outline.title = request.title
    if request.scene is not None:
        chapter_outline.scene = request.scene
    if request.characters is not None:
        chapter_outline.characters = request.characters
    if request.plot is not None:
        chapter_outline.plot = request.plot
    if request.conflict is not None:
        chapter_outline.conflict = request.conflict
    if request.ending is not None:
        chapter_outline.ending = request.ending
    if request.target_words is not None:
        chapter_outline.target_words = request.target_words

    db.commit()
    db.refresh(chapter_outline)

    # Check if chapter content exists
    has_content = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first() is not None

    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )


@router.put("/{project_id}/chapter-outlines/{chapter_num}/confirm", response_model=ChapterOutlineResponse)
async def confirm_chapter_outline(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm a chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if already confirmed
    if chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline is already confirmed"
        )

    # Check if outline has required content
    if not chapter_outline.title or not chapter_outline.plot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline must have title and plot before confirming"
        )

    # Confirm the chapter outline
    chapter_outline.confirmed = True

    # Check if all chapter outlines are confirmed - 使用两个简单查询
    from sqlalchemy import func

    total_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id
    ).scalar() or 0

    confirmed_outlines = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).scalar() or 0

    # 确认后，已确认数需要 +1（因为当前章节还未 commit）
    confirmed_outlines += 1

    # If all confirmed, update workflow state to chapter writing
    if total_outlines > 0 and confirmed_outlines == total_outlines:
        workflow_state = get_or_create_workflow_state(db, project_id)
        workflow_state.stage = STAGE_WRITING

    db.commit()
    db.refresh(chapter_outline)

    # Check if chapter content exists
    has_content = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first() is not None

    return ChapterOutlineResponse(
        id=chapter_outline.id,
        project_id=chapter_outline.project_id,
        chapter_number=chapter_outline.chapter_number,
        title=chapter_outline.title,
        scene=chapter_outline.scene,
        characters=chapter_outline.characters,
        plot=chapter_outline.plot,
        conflict=chapter_outline.conflict,
        ending=chapter_outline.ending,
        target_words=chapter_outline.target_words,
        confirmed=chapter_outline.confirmed,
        created_at=chapter_outline.created_at,
        has_content=has_content
    )


# =============================================================================
# Chapter Content Endpoints
# =============================================================================

@router.get("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse)
async def get_chapter_content(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get chapter content by chapter number."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Find the chapter content
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.post("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    project_id: int,
    chapter_num: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an empty chapter entry linked to chapter outline."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Check if chapter already exists
    existing_chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if existing_chapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chapter {chapter_num} already exists"
        )

    # Create new empty chapter
    chapter = Chapter(
        chapter_outline_id=chapter_outline.id,
        content=None,
        word_count=0,
        review_passed=False,
        review_feedback=None
    )

    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.put("/{project_id}/chapters/{chapter_num}", response_model=ChapterResponse)
async def update_chapter_content(
    project_id: int,
    chapter_num: int,
    request: ChapterContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update chapter content."""
    project = get_project_for_user(project_id, current_user.id, db)

    # Find the chapter outline
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # Find the chapter
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    # Update content and word count (use len() for Chinese text)
    chapter.content = request.content
    chapter.word_count = len(request.content) if request.content else 0

    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        chapter_outline_id=chapter.chapter_outline_id,
        content=chapter.content,
        word_count=chapter.word_count,
        review_passed=chapter.review_passed,
        review_feedback=chapter.review_feedback,
        review_result=chapter.review_result,
        rewrite_count=chapter.rewrite_count,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.post("/{project_id}/chapters/{chapter_num}/generate")
async def generate_chapter(
    project_id: int,
    chapter_num: int,
    request: ChapterGenerateRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成章节正文（SSE 流式）

    使用 generate_chapter_content_stream 流式生成，LLM 通过
    get_llm_from_state_async 获取（与 LangGraph 节点相同机制）。
    状态通过 build_initial_state 构建（含 DB 预加载的角色/关系数据），
    确保生成上下文与 LangGraph 节点一致。

    DB 写入使用独立 Session（从 SessionLocal 创建），避免请求级
    Session 在长流式操作期间失效导致内容丢失。
    """
    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # 查找章节大纲
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    if not chapter_outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter outline must be confirmed before generating content"
        )

    # 保存 chapter_outline_id 供流内部使用（不预先创建空记录）
    chapter_outline_id = chapter_outline.id

    # 构建初始状态（传入 db 预加载角色/关系数据）
    llm_config_id = request.llm_config_id if request else None
    workflow_state = get_or_create_workflow_state(db, project_id)
    initial_state = build_initial_state(
        project, outline, workflow_state, llm_config_id, db=db
    )
    initial_state["current_chapter"] = chapter_num

    # 构建当前章节大纲数据（从 DB 获取完整字段）
    current_outline = {
        "chapter_number": chapter_outline.chapter_number,
        "title": chapter_outline.title,
        "scene": chapter_outline.scene,
        "characters": chapter_outline.characters,
        "plot": chapter_outline.plot,
        "conflict": chapter_outline.conflict,
        "ending": chapter_outline.ending,
        "target_words": chapter_outline.target_words,
    }

    async def stream_generator():
        """流式生成章节正文

        生成完成后原子性写入数据库：使用独立 Session 创建或更新
        Chapter 记录并填充内容。不在流之前创建空记录，避免中断时
        残留 content=NULL 的脏数据。

        使用独立 Session 而非请求级 db，原因：
        1. 请求级 db 在 StreamingResponse 完成后由 get_db().finally
           调用 rollback + close，可能导致长流式操作后 commit 失败
        2. LLM 流式生成耗时数分钟，期间 PostgreSQL 连接可能被回收
        """
        from app.database import SessionLocal

        save_db = SessionLocal()
        try:
            # 通过与 LangGraph 节点相同的机制获取 LLM 服务
            llm = await get_llm_from_state_async(initial_state, db)

            # 流式生成章节正文
            content = ""
            async for chunk in generate_chapter_content_stream(initial_state, current_outline, llm):
                content += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

            # 后处理：清理 LLM 可能添加的结尾数字
            content = clean_chapter_content(content)
            if not content:
                yield format_sse_error(ValueError("生成内容为空"))
                return

            # 原子性写入数据库（使用独立 Session）
            word_count = len(content)
            chapter = save_db.query(Chapter).filter(
                Chapter.chapter_outline_id == chapter_outline_id
            ).first()

            if chapter:
                # 更新已有记录
                chapter.content = content
                chapter.word_count = word_count
            else:
                # 创建新记录（含内容，不留空记录）
                chapter = Chapter(
                    chapter_outline_id=chapter_outline_id,
                    content=content,
                    word_count=word_count,
                    review_passed=False,
                    review_feedback=None
                )
                save_db.add(chapter)

            # 更新工作流状态
            wf = get_or_create_workflow_state(save_db, project_id)
            wf.stage = STAGE_WRITING
            save_db.commit()
            save_db.refresh(chapter)

            # 发送完成事件
            chapter_response = {
                "id": chapter.id,
                "chapter_outline_id": chapter.chapter_outline_id,
                "content": content,
                "word_count": word_count,
            }
            yield f"event: done\ndata: {json.dumps({'chapter': chapter_response})}\n\n"

        except Exception as e:
            yield format_sse_error(e)
        finally:
            save_db.close()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{project_id}/chapters/{chapter_num}/review")
async def review_chapter(
    project_id: int,
    chapter_num: int,
    request: ReviewRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """审核章节质量（SSE 流式）

    使用 review_chapter_node LangGraph 节点函数进行审核，LLM 通过
    get_llm_from_state_async 获取（与 LangGraph 节点相同机制）。
    审核过程流式输出审核文本，完成后发送审核结果。

    SSE 事件：
    - chunk: 审核文本片段 {content: string}
    - done: 审核完成 {passed: bool, feedback: string, issues: string[]}
    - error: 审核失败 {error: string}
    """
    from app.agents.nodes.review import review_chapter_node, check_review_passed

    project = get_project_for_user(project_id, current_user.id, db)
    outline = get_outline_for_project(project_id, db)

    # 查找章节大纲
    chapter_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num
    ).first()

    if not chapter_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter outline {chapter_num} not found"
        )

    # 查找章节内容
    chapter = db.query(Chapter).filter(
        Chapter.chapter_outline_id == chapter_outline.id
    ).first()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_num} content not found"
        )

    if not chapter.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chapter has no content to review"
        )

    # 构建初始状态（传入 db 预加载角色/关系数据）
    llm_config_id = request.llm_config_id if request else None
    workflow_state = get_or_create_workflow_state(db, project_id)
    initial_state = build_initial_state(
        project, outline, workflow_state, llm_config_id, db=db
    )
    initial_state["current_chapter"] = chapter_num
    initial_state["written_chapters"] = [{"chapter_number": chapter_num, "content": chapter.content}]

    # 构建章节大纲数据（从 DB 获取完整字段）
    chapter_outline_dict = {
        "chapter_number": chapter_outline.chapter_number,
        "title": chapter_outline.title or "",
        "scene": chapter_outline.scene,
        "characters": chapter_outline.characters,
        "plot": chapter_outline.plot or "",
        "conflict": chapter_outline.conflict,
        "ending": chapter_outline.ending,
        "target_words": chapter_outline.target_words,
    }

    # 保存审核参数供流内部使用
    strictness = request.strictness if request else "standard"
    chapter_outline_id = chapter_outline.id

    async def stream_generator():
        """流式审核章节

        审核完成后原子性写入数据库：使用独立 Session 保存审核结果。
        使用独立 Session 而非请求级 db，原因与 generate_chapter 相同：
        长时间 LLM 操作期间请求级 Session 可能失效。
        """
        from app.database import SessionLocal

        save_db = SessionLocal()
        try:
            # 通过与 LangGraph 节点相同的机制获取 LLM 服务
            llm = await get_llm_from_state_async(initial_state, db)

            # 构建审核 prompt（与 review_chapter_node 相同逻辑）
            from app.services.prompt_loader import get_system_prompt
            from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info

            info = initial_state.get("collected_info", {})
            outline_str = _format_chapter_outline_str(chapter_outline_dict)
            chars_str = format_characters_info(initial_state)

            prompt = get_system_prompt(save_db, "review").format(
                strictness=strictness,
                chapter_outline=outline_str,
                chapter_content=chapter.content,
                genre=info.get("novelType", "未指定"),
                main_characters=chars_str,
                style_preference=info.get("stylePreference", "未指定"),
            )

            # 流式调用 LLM，逐块发送审核文本
            response = ""
            async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
                response += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"

            # 解析审核结果
            from app.agents.nodes.review import parse_review_result
            review_result = parse_review_result(response)
            review_result["raw_response"] = response

            # 保存审核结果到数据库（使用独立 Session）
            ch = save_db.query(Chapter).filter(
                Chapter.chapter_outline_id == chapter_outline_id
            ).first()

            if ch:
                ch.review_passed = check_review_passed(review_result)
                ch.review_feedback = review_result.get("raw_response")
                ch.review_result = review_result
                save_db.commit()

            # 发送完成事件
            result_data = {
                "passed": ch.review_passed if ch else False,
                "feedback": ch.review_feedback if ch else "",
                "issues": review_result.get("issues", []),
            }
            yield f"event: done\ndata: {json.dumps(result_data)}\n\n"

        except Exception as e:
            yield format_sse_error(e)
        finally:
            save_db.close()

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )