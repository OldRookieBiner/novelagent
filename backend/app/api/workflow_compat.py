"""Legacy workflow compatibility layer

Provides the old build_initial_state function for legacy API endpoints
(chapters.py, outline.py, characters.py) that still use the old
NovelState format with stage/collected_info/outline_* fields.

The new creation agent workflow uses NovelState v2 format.
"""

import logging
from typing import Optional, AsyncIterator

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.outline import Outline
from app.models.model_config import ModelConfig
from app.models.workflow_state import WorkflowState
from app.agents.state import NovelState

logger = logging.getLogger(__name__)

def _derive_novel_length(target_word_count: Optional[int]) -> str:
    """根据 Project 的目标字数推断 novel_length 枚举值

    Args:
        target_word_count: 项目目标字数（整数），None 时默认 100000

    Returns:
        "short" | "medium" | "long"
    """
    target = target_word_count or 100000
    if target >= 500000:
        return "long"
    elif target >= 100000:
        return "medium"
    else:
        return "short"


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
        "current_arc_index": 0,  # 长篇模式弧索引，默认从 0 开始

        # 根据 Project 的目标字数推断 novel_length
        "novel_length": _derive_novel_length(project.novel_length),

        # 大纲有效性标志（有标题或摘要即视为有效）
        "outline_valid": bool(outline and (outline.title or outline.summary)),

        # 审核/重写
        "review_mode": workflow_state.workflow_mode,
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": workflow_state.max_rewrite_count,
        "refinement_enabled": True,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
        "confirmation_type": workflow_state.confirmation_type,

        # LLM 服务（优先级：参数 > workflow_state DB > None）
        "llm_config_id": llm_config_id or workflow_state.llm_config_id,
        "llm_model_name": llm_model_name or workflow_state.llm_model_name,
        "review_llm_config_id": None,  # 审核专用模型配置 ID，由 run_workflow 端点注入

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

    # 预加载上下文窗口大小（节点无 DB Session，需要从 state 获取）
    if db is not None:
        try:
            from app.agents.token_budget import get_context_window

            model_name = state.get("llm_model_name", "")
            model_config_id = state.get("llm_config_id")
            if model_config_id:
                config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
                state["_context_window"] = get_context_window(model_name, model_config=config)
            else:
                state["_context_window"] = get_context_window(model_name)
        except Exception as e:
            logger.warning(f"Failed to load context window, using default: {e}")
            from app.agents.constants import DEFAULT_CONTEXT_WINDOW
            state["_context_window"] = DEFAULT_CONTEXT_WINDOW

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
        # 长篇模式卷弧/弧纲 prompt
        "arc_outline_generation": get_system_prompt(db, "arc_outline_generation"),
        "volume_arc_generation": get_system_prompt(db, "volume_arc_generation"),
        # 章节自检与精修 prompt
        "chapter_self_check": get_system_prompt(db, "chapter_self_check"),
        "chapter_refine": get_system_prompt(db, "chapter_refine"),
        # 灵感对话 prompt
        "inspiration_extraction": get_system_prompt(db, "inspiration_extraction"),
        "inspiration_question": get_system_prompt(db, "inspiration_question"),
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



async def stream_workflow_events(
    graph,
    config: dict,
    initial_state: dict = None,
) -> AsyncIterator[str]:
    """Legacy SSE event stream generator for old workflow endpoints.

    Delegates to the new workflow.stream_workflow_events.
    """
    from app.api.workflow import stream_workflow_events as _new_stream
    async for event in _new_stream(graph, config, initial_state):
        yield event
