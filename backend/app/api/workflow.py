"""Workflow API routes for LangGraph integration"""

import json
import logging
from typing import Optional, AsyncIterator
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline
from app.models.checkpoint import WorkflowCheckpoint
from app.models.workflow_state import WorkflowState
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.utils.error import format_sse_error
from app.utils.deps import get_user_settings_or_raise
from app.agents.graph import create_novel_graph_with_checkpointer
from app.agents.state import NovelState

router = APIRouter()


async def stream_workflow_events(
    graph,
    config: dict,
    initial_state: dict = None,
) -> AsyncIterator[str]:
    """共享的 LangGraph 工作流 SSE 事件流生成器

    将 LangGraph astream_events 事件转换为 SSE 字符串。

    - 如果 initial_state 不为 None，视为首次执行，先发送 workflow start 事件
    - 如果 initial_state 为 None，视为恢复执行，先发送 workflow_resume 事件

    处理的事件类型：
    - on_chain_start → node_start
    - on_chat_model_stream → chunk（LLM 流式内容）
    - on_chain_end → node_done（或 waiting 如果等待确认）

    Args:
        graph: 编译后的 LangGraph graph
        config: LangGraph 配置字典
        initial_state: 初始状态（首次执行时传入，恢复执行时传 None）

    Yields:
        SSE 格式字符串，以 \\n\\n 结尾
    """
    try:
        # 首次执行 vs 恢复执行
        if initial_state is not None:
            yield f"event: node_start\ndata: {json.dumps({'node': 'workflow', 'message': 'Starting workflow'})}\n\n"
        else:
            yield f"event: node_start\ndata: {json.dumps({'node': 'workflow_resume', 'message': 'Resuming workflow'})}\n\n"

        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            if event_type == "on_chain_start":
                yield f"event: node_start\ndata: {json.dumps({'node': event_name})}\n\n"

            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                # 处理 output 不是字典的情况（如 END 字符串）
                if isinstance(output, dict):
                    if output.get("waiting_for_confirmation"):
                        yield f"event: waiting\ndata: {json.dumps({'node': event_name, 'confirmation_type': output.get('confirmation_type')})}\n\n"
                        # 工作流暂停，同时发送 done 事件通知前端当前阶段完成
                        yield f"event: done\ndata: {json.dumps({'message': 'Workflow paused for confirmation'})}\n\n"
                        return
                    else:
                        yield f"event: node_done\ndata: {json.dumps({'node': event_name, 'state': output})}\n\n"
                else:
                    # output 不是字典（如 END 字符串），说明工作流已完成
                    # 跳过 node_done，直接等待最终的 done 事件
                    pass

            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk:
                    content = getattr(chunk, "content", str(chunk))
                    if content:
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

        yield f"event: done\ndata: {json.dumps({'message': 'Workflow completed'})}\n\n"

    except Exception as e:
        yield format_sse_error(e)


# ========== Request/Response Schemas ==========

class WorkflowRunRequest(BaseModel):
    """工作流运行请求"""
    llm_config_id: Optional[int] = None  # 指定模型配置 ID
    llm_model_name: Optional[str] = None  # 指定模型名称（覆盖配置中的默认模型）


class WorkflowConfirmRequest(BaseModel):
    """工作流确认请求"""
    # 可选：用户修改后的数据
    outline_title: Optional[str] = None
    outline_summary: Optional[str] = None
    chapter_outlines: Optional[list] = None


class WorkflowReplanRequest(BaseModel):
    """重新规划请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None
    # 重新规划时同步保存的灵感采集数据
    collected_info: Optional[dict] = None
    inspiration_template: Optional[str] = None


class WorkflowReplanChapterOutlinesRequest(BaseModel):
    """章节大纲重新生成请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None


class WorkflowStateResponse(BaseModel):
    """工作流状态响应"""
    project_id: int
    has_checkpoint: bool
    stage: Optional[str] = None
    waiting_for_confirmation: bool = False
    confirmation_type: Optional[str] = None
    current_state: Optional[dict] = None


# ========== Helper Functions ==========

def build_initial_state(
    project: Project,
    outline: Outline,
    workflow_state: WorkflowState,
    llm_config_id: Optional[int] = None,
    llm_model_name: Optional[str] = None,
    db: Optional["Session"] = None
) -> NovelState:
    """
    从项目、大纲和工作流状态构建初始 NovelState。

    当传入 db 参数时，会从数据库预加载已持久化的角色和关系（带 id），
    覆盖检查点中可能存在的旧数据，确保节点始终使用最新的 DB 数据。

    Args:
        project: 项目实例
        outline: 大纲实例
        workflow_state: 工作流状态实例
        llm_config_id: 模型配置 ID
        llm_model_name: 模型名称（覆盖配置中的默认模型）
        db: 可选的数据库会话，用于预加载角色/关系数据

    Returns:
        NovelState 字典
    """
    # 获取章节大纲
    chapter_outlines = [
        {
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
    ]

    # 获取已写入的章节
    written_chapters = []
    for co in project.chapter_outlines:
        if co.chapter and co.chapter.content:
            written_chapters.append({
                "chapter_number": co.chapter_number,
                "title": co.title,
                "content": co.chapter.content,
                "word_count": co.chapter.word_count,
            })

    # 构建状态
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制（使用 workflow_state.stage，无需映射）
        "stage": workflow_state.stage,

        # 灵感/输入
        # 优先从 inspiration_template 列读取，回退到 collected_info 字典中的 inspiration_template
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template or (outline.collected_info or {}).get("inspiration_template"),

        # 大纲
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting,
        "outline_emotional_curve": outline.emotional_curve,
        "outline_confirmed": outline.confirmed,

        # 章节大纲
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": chapter_outlines,
        "chapter_outlines_confirmed": all(co.confirmed for co in project.chapter_outlines) if chapter_outlines else False,

        # 章节正文
        "written_chapters": written_chapters,
        "current_chapter": workflow_state.current_chapter,

        # 审核/重写
        "review_mode": workflow_state.workflow_mode,
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": workflow_state.max_rewrite_count,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
        "confirmation_type": workflow_state.confirmation_type,

        # LLM 服务（优先级：参数 > workflow_state DB > None）
        "llm_config_id": llm_config_id or workflow_state.llm_config_id,
        "llm_model_name": llm_model_name or workflow_state.llm_model_name,

        # 预加载：角色和关系（从 DB 获取最新数据）
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
    }

    # 从数据库预加载已持久化的角色（带 id）
    if db is not None:
        from app.models.character import Character, Relation

        db_characters = db.query(Character).filter(
            Character.project_id == project.id
        ).order_by(Character.id).all()

        if db_characters:
            state["characters"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "role": c.role,
                    "appearance": c.appearance or "",
                    "personality": c.personality or "",
                    "backstory": c.backstory or "",
                    "catchphrase": c.catchphrase or "",
                    "habit_action": c.habit_action or "",
                    "deep_fear": c.deep_fear or "",
                    "core_motivation": c.core_motivation or "",
                    "growth_arc": c.growth_arc or "",
                    "signature_item": c.signature_item or "",
                }
                for c in db_characters
            ]

        # 预加载关系
        db_relations = db.query(Relation).filter(
            Relation.project_id == project.id
        ).all()

        if db_relations:
            state["relations"] = [
                {
                    "id": r.id,
                    "character_a_id": r.character_a_id,
                    "character_b_id": r.character_b_id,
                    "relation_type": r.relation_type,
                    "trust_level": r.trust_level,
                    "current_status": r.current_status or "",
                    "direction": r.direction or "双向",
                }
                for r in db_relations
            ]

        # 预加载演变计划和记录（通过 Relation join 查询，EvolutionPlan/Record 无 project_id）
        relation_ids = [r.id for r in db_relations]
        if relation_ids:
            from app.models.character import EvolutionPlan, EvolutionRecord

            db_plans = db.query(EvolutionPlan).filter(
                EvolutionPlan.relation_id.in_(relation_ids)
            ).order_by(EvolutionPlan.trigger_chapter).all()

            db_records = db.query(EvolutionRecord).filter(
                EvolutionRecord.relation_id.in_(relation_ids)
            ).order_by(EvolutionRecord.chapter_number).all()

            # 批量构建：id → Character 映射（O(1) 查找）
            char_map = {c.id: c for c in db_characters}

            # 批量构建：relation_id → (character_a_name, character_b_name)
            relation_name_map = {}
            for r in db_relations:
                a = char_map.get(r.character_a_id)
                b = char_map.get(r.character_b_id)
                relation_name_map[r.id] = (a.name if a else "未知", b.name if b else "未知")

            if db_plans:
                state["evolution_plans"] = [
                    {
                        "chapter_number": p.trigger_chapter,
                        "character_name": "、".join(relation_name_map.get(p.relation_id, ("未知", "未知"))),
                        "changes": f"{p.status_before or ''} → {p.status_after}",
                    }
                    for p in db_plans
                ]

            if db_records:
                state["evolution_records"] = [
                    {
                        "chapter_number": r.chapter_number,
                        "character_name": "、".join(relation_name_map.get(r.relation_id, ("未知", "未知"))),
                        "actual_changes": r.content,
                    }
                    for r in db_records
                ]

    # 预加载 prompts（过渡方案：统一 SSE 端点和 LangGraph 节点的 prompt 获取）
    # TODO: _prompts 应通过 LangGraph config 传递而非 state 字段，
    # 重构时移入 config["configurable"]["prompts"]，节点通过 config 获取
    if db is not None:
        try:
            state["_prompts"] = _build_prompts_dict(db)
        except Exception as e:
            logger.warning(f"Failed to load custom prompts, using defaults: {e}")
            from app.agents.prompts import DEFAULT_PROMPTS
            state["_prompts"] = DEFAULT_PROMPTS

    return state


def _build_prompts_dict(db: Session) -> dict[str, str | dict]:
    """构建预加载的 prompts 字典（所有节点共享）

    chapter_content_generation, review, rewrite 为 dict 格式 {"system": ..., "user": ...}，
    system 模板始终使用默认值（角色定位+规则+禁用词+上下文），
    user 模板可由用户自定义（DB 中存储）。
    """
    from app.services.prompt_loader import get_system_prompt
    from app.agents.prompts import DEFAULT_PROMPTS

    # dict 格式的 prompt：system 固定默认值，user 可自定义
    default_cc = DEFAULT_PROMPTS["chapter_content_generation"]
    default_review = DEFAULT_PROMPTS["review"]
    default_rewrite = DEFAULT_PROMPTS["rewrite"]

    return {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
        "chapter_outline_generation": get_system_prompt(db, "chapter_outline_generation"),
        "arc_outline_generation": get_system_prompt(db, "arc_outline_generation"),
        "chapter_content_generation": {
            "system": default_cc["system"] if isinstance(default_cc, dict) else default_cc,
            "user": get_system_prompt(db, "chapter_content_generation"),
        },
        "review": {
            "system": default_review["system"],
            "user": get_system_prompt(db, "review"),
        },
        "rewrite": {
            "system": default_rewrite["system"],
            "user": get_system_prompt(db, "rewrite"),
        },
    }


def get_latest_checkpoint(project_id: int, thread_id: str = "default", db: Session = None) -> Optional[dict]:
    """
    获取项目的最新检查点状态。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID
        db: 数据库会话（必须传入）

    Returns:
        检查点状态字典，如果不存在则返回 None
    """
    if db is None:
        raise ValueError("db session is required")

    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == thread_id
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        return record.checkpoint.get("channel_values", {})
    return None


def delete_project_checkpoints(project_id: int, thread_id: str = "default", db: Session = None) -> int:
    """
    删除项目的所有检查点。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID
        db: 数据库会话（必须传入）

    Returns:
        删除的记录数
    """
    if db is None:
        raise ValueError("db session is required")

    count = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == thread_id
    ).delete()
    db.commit()
    return count


# ========== API Endpoints ==========

@router.post("/{project_id}/workflow/run")
async def run_workflow(
    project_id: int,
    request: WorkflowRunRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    启动或恢复工作流（SSE 流式）。

    使用 LangGraph 的 astream_events 进行流式传输，
    发送以下 SSE 事件：
    - node_start: 节点开始执行
    - chunk: 内容片段
    - node_done: 节点执行完成
    - waiting: 等待用户确认
    - done: 工作流完成
    - error: 错误
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    user_settings = get_user_settings_or_raise(current_user, db)

    # 获取或创建 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    # 获取 LLM 配置
    llm_config_id = None
    llm_model_name = None
    if request:
        llm_config_id = request.llm_config_id
        llm_model_name = request.llm_model_name

    # 持久化 LLM 配置到 workflow_state（确保所有端点使用同一模型）
    if llm_config_id or llm_model_name:
        workflow_state.llm_config_id = llm_config_id
        workflow_state.llm_model_name = llm_model_name
        db.commit()

    # 构建初始状态（预加载 DB 数据，含 _prompts）
    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id, llm_model_name, db=db)

    # 创建带检查点的图（复用 db 会话）
    graph = create_novel_graph_with_checkpointer(project_id, "default")

    # 配置（仅包含 thread_id，prompts 已放入 state）
    config = {
        "configurable": {
            "thread_id": "default",
        }
    }

    # 创建 SSE 流生成器（使用共享函数）
    def stream_generator():
        return stream_workflow_events(graph, config, initial_state)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{project_id}/workflow/confirm")
async def confirm_workflow(
    project_id: int,
    request: WorkflowConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    确认当前节点并继续工作流。

    用于在 step_by_step 或 hybrid 模式下，
    用户确认大纲或章节大纲后继续执行。
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if not checkpoint_state:
        # Fallback：从 WorkflowState 确认（replan-chapter-outlines 场景）
        workflow_state = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id,
            WorkflowState.thread_id == "main"
        ).first()

        if workflow_state and workflow_state.waiting_for_confirmation:
            confirmation_type = workflow_state.confirmation_type

            if confirmation_type == "chapter_outlines":
                # 确认所有章节大纲
                from app.models.outline import ChapterOutline
                chapter_outlines = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id
                ).all()
                for co in chapter_outlines:
                    co.confirmed = True

                workflow_state.waiting_for_confirmation = False
                workflow_state.confirmation_type = None
                workflow_state.stage = "writing"
                db.commit()

                return {"message": "Chapter outlines confirmed", "confirmation_type": "chapter_outlines"}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workflow to confirm"
        )

    # 检查是否正在等待确认
    if not checkpoint_state.get("waiting_for_confirmation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not waiting for confirmation"
        )

    # 更新状态：清除等待确认标志
    checkpoint_state["waiting_for_confirmation"] = False

    # 应用用户修改（如果有）
    if request:
        if request.outline_title:
            checkpoint_state["outline_title"] = request.outline_title
        if request.outline_summary:
            checkpoint_state["outline_summary"] = request.outline_summary
        if request.chapter_outlines:
            checkpoint_state["chapter_outlines"] = request.chapter_outlines

    # 更新确认状态
    confirmation_type = checkpoint_state.get("confirmation_type")
    if confirmation_type == "outline":
        checkpoint_state["outline_confirmed"] = True
    elif confirmation_type == "chapter_outlines":
        checkpoint_state["chapter_outlines_confirmed"] = True

    checkpoint_state["confirmation_type"] = None

    # 更新数据库中的检查点（使用传入的 db 会话）
    record = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id,
        WorkflowCheckpoint.thread_id == "default"
    ).order_by(WorkflowCheckpoint.updated_at.desc()).first()

    if record:
        checkpoint_data = record.checkpoint.copy()
        checkpoint_data["channel_values"] = checkpoint_state
        record.checkpoint = checkpoint_data

    # 同步更新大纲和项目
    if confirmation_type == "outline":
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if outline:
            outline.title = checkpoint_state.get("outline_title", outline.title)
            outline.summary = checkpoint_state.get("outline_summary", outline.summary)
            outline.confirmed = True

    # 同步更新角色（characters）
    if confirmation_type == "characters":
        from app.models.character import Character

        characters_data = checkpoint_state.get("characters", [])
        if characters_data:
            # 删除旧角色，创建新角色
            db.query(Character).filter(Character.project_id == project_id).delete()
            for char_data in characters_data:
                char = Character(
                    project_id=project_id,
                    name=char_data.get("name", "未命名"),
                    role=char_data.get("role", "配角"),
                    personality=char_data.get("personality", ""),
                    core_motivation=char_data.get("core_motivation", ""),
                    growth_arc=char_data.get("growth_arc", ""),
                )
                db.add(char)
            logger.info(f"Persisted {len(characters_data)} characters to DB for project {project_id}")

    # 同步更新关系（relations）
    if confirmation_type == "relations":
        from app.models.character import Relation

        relations_data = checkpoint_state.get("relations", [])
        if relations_data:
            # 删除旧关系，创建新关系
            db.query(Relation).filter(Relation.project_id == project_id).delete()
            for rel_data in relations_data:
                rel = Relation(
                    project_id=project_id,
                    character_a_id=rel_data.get("character_a_id"),
                    character_b_id=rel_data.get("character_b_id"),
                    relation_type=rel_data.get("relation_type", "陌生"),
                    trust_level=rel_data.get("trust_level", 50),
                    current_status=rel_data.get("current_status", ""),
                    direction=rel_data.get("direction", "双向"),
                )
                db.add(rel)
            logger.info(f"Persisted {len(relations_data)} relations to DB for project {project_id}")

    # 提交所有数据库更改
    db.commit()

    # 通过 LangGraph 恢复执行
    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    async def stream_generator():
        return stream_workflow_events(graph, config, None)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{project_id}/workflow/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前工作流状态。

    返回检查点状态信息，包括：
    - 是否有检查点
    - 当前阶段
    - 是否等待确认
    - 完整状态数据
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if checkpoint_state:
        return WorkflowStateResponse(
            project_id=project_id,
            has_checkpoint=True,
            stage=checkpoint_state.get("stage"),
            waiting_for_confirmation=checkpoint_state.get("waiting_for_confirmation", False),
            confirmation_type=checkpoint_state.get("confirmation_type"),
            current_state=checkpoint_state
        )
    else:
        # 无检查点，从 WorkflowState 获取状态
        workflow_state = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id,
            WorkflowState.thread_id == "main"
        ).first()

        if workflow_state:
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                stage=workflow_state.stage,
                waiting_for_confirmation=workflow_state.waiting_for_confirmation,
                confirmation_type=workflow_state.confirmation_type,
                current_state=None
            )
        else:
            # 无 WorkflowState，返回默认状态
            return WorkflowStateResponse(
                project_id=project_id,
                has_checkpoint=False,
                stage="inspiration",
                waiting_for_confirmation=False,
                confirmation_type=None,
                current_state=None
            )


@router.post("/{project_id}/workflow/cancel")
async def cancel_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    取消当前工作流。

    删除项目的所有检查点，工作流将无法恢复。
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 删除检查点
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return {
        "message": "Workflow cancelled",
        "deleted_checkpoints": deleted_count
    }


class WorkflowCleanupResponse(BaseModel):
    """工作流清理响应"""
    message: str
    deleted: int


@router.post("/{project_id}/workflow/cleanup", response_model=WorkflowCleanupResponse)
async def cleanup_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    清理工作流检查点（不删业务数据）。

    用于规划生成失败后的重试清理。
    """
    # 验证项目所有权
    get_project_for_user(project_id, current_user.id, db)

    # 删除检查点
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return WorkflowCleanupResponse(
        message="Checkpoints cleaned up",
        deleted=deleted_count,
    )


@router.post("/{project_id}/workflow/replan")
async def replan_workflow(
    project_id: int,
    request: WorkflowReplanRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新生成规划（大纲+人物+关系）。

    清理旧的检查点、大纲生成数据、人物、关系、章节大纲，
    然后重新启动工作流从大纲生成开始。
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    # 1. 清理检查点
    delete_project_checkpoints(project_id, "default", db)

    # 2. 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.stage = "inspiration"
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None
        workflow_state.current_chapter = 1

    # 3. 更新灵感采集数据（重新规划时前端传入最新表单数据）
    if request:
        if request.collected_info:
            current_info = dict(outline.collected_info or {})
            current_info.update(request.collected_info)
            outline.collected_info = current_info
        if request.inspiration_template:
            outline.inspiration_template = request.inspiration_template

    # 4. 重置大纲生成字段（保留 collected_info 和 inspiration_template）
    outline.title = None
    outline.summary = None
    outline.plot_points = []
    outline.characters = []
    outline.world_setting = None
    outline.emotional_curve = None
    outline.confirmed = False
    outline.chapter_count_suggested = 0
    outline.chapter_count_confirmed = False

    # 5. 删除旧的人物和关系
    from app.models.character import Character, Relation
    from app.models.outline import ChapterOutline

    # 先删关系（外键依赖人物），再删人物
    db.query(Relation).filter(Relation.project_id == project_id).delete()
    db.query(Character).filter(Character.project_id == project_id).delete()

    # 6. 删除章节大纲（cascade 会自动删除关联的 Chapter）
    db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).delete()

    # 提交所有清理
    db.commit()
    db.refresh(outline)

    # 7. 构建初始状态
    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    llm_config_id = None
    llm_model_name = None
    if request:
        llm_config_id = request.llm_config_id
        llm_model_name = request.llm_model_name

    # 持久化 LLM 配置到 workflow_state
    if llm_config_id or llm_model_name:
        workflow_state.llm_config_id = llm_config_id
        workflow_state.llm_model_name = llm_model_name
        db.commit()

    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id, llm_model_name, db=db)

    # 8. 创建带检查点的图并启动工作流
    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    def stream_generator():
        return stream_workflow_events(graph, config, initial_state)

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{project_id}/workflow/replan-chapter-outlines")
async def replan_chapter_outlines(
    project_id: int,
    request: WorkflowReplanChapterOutlinesRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新生成章节大纲（保留大纲、人物、关系数据）。

    清理章节大纲和已写正文，保留大纲/人物/关系，
    直接调用 generate_chapter_outlines_stream 流式生成。
    生成完成后设置 WorkflowState.waiting_for_confirmation=True，
    通过 confirm 端点确认（不依赖检查点）。
    """
    from app.models.outline import ChapterOutline
    from app.api.chapters import _stream_chapter_outlines_sse
    from app.agents.state import STAGE_CHAPTER_OUTLINES

    # 1. 验证项目
    project = get_project_for_user(project_id, current_user.id, db)

    # 2. 验证大纲已确认
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before regenerating chapter outlines"
        )

    # 3. 删除 ChapterOutline（级联删 Chapter）
    db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).delete()

    # 4. 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.stage = STAGE_CHAPTER_OUTLINES
        workflow_state.current_chapter = 1
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

    # 5. 删除检查点
    delete_project_checkpoints(project_id, "default", db)
    db.commit()
    db.refresh(outline)

    # 6. 构建初始状态
    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    llm_config_id = None
    llm_model_name = None
    if request:
        llm_config_id = request.llm_config_id
        llm_model_name = request.llm_model_name

    # 持久化 LLM 配置到 workflow_state
    if llm_config_id or llm_model_name:
        workflow_state.llm_config_id = llm_config_id
        workflow_state.llm_model_name = llm_model_name
        db.commit()

    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id, llm_model_name, db=db)

    # 7. 调用共享 SSE 流式函数
    async def stream_generator():
        async for sse_event in _stream_chapter_outlines_sse(initial_state, project_id, db):
            yield sse_event

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class UpdateStageRequest(BaseModel):
    """更新工作流阶段请求"""
    stage: str


@router.put("/{project_id}/workflow/stage")
async def update_workflow_stage(
    project_id: int,
    request: UpdateStageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新工作流阶段。

    用于手动切换工作流阶段，例如：
    - 灵感采集完成后切换到大纲生成
    - 章节大纲确认后切换到写作
    """
    from app.utils.workflow import get_or_create_workflow_state

    # 验证项目所有权
    get_project_for_user(project_id, current_user.id, db)

    # 获取或创建工作流状态
    workflow_state = get_or_create_workflow_state(db, project_id)

    # 更新阶段
    workflow_state.stage = request.stage
    db.commit()

    return {
        "message": "Stage updated",
        "stage": request.stage
    }


# ========== Export ==========
__all__ = ["router"]
