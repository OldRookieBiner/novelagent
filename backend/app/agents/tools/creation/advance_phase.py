"""推进阶段工具

根因修复（P0-3）：使用 get_or_create_workflow_state（基于 unique 约束 + upsert）
保证 WorkflowState 行的唯一性，彻底消除并发创建多行的问题。
不再需要双重检查模式（rollback+begin+re-query），因为数据库约束保证原子性。
"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def advance_phase(direction: str = "forward") -> dict:
    """推进或回退创作阶段。

    direction="forward"：根据知识库完整度判断是否可以进入下一阶段。
    direction="backward"：回退到上一阶段（Writing→Structure，Structure→Incubation）。

    Args:
        direction: 方向 - "forward"(推进) 或 "backward"(回退)
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    from app.database import SessionLocal
    from app.agents.constants import Phase
    from app.utils.workflow import get_or_create_workflow_state

    kb = _kb()

    # 阶段标签
    phase_labels = {
        Phase.INCUBATION: "创意孵化",
        Phase.STRUCTURE: "结构设计",
        Phase.WRITING: "写作中",
        Phase.REVISION: "修订中",
    }

    # 回退映射
    backward_map = {
        Phase.WRITING: Phase.STRUCTURE,
        Phase.STRUCTURE: Phase.INCUBATION,
    }

    # 1. 无锁读取当前阶段（仅用于判断，不持锁）
    db_read = SessionLocal()
    try:
        ws_read = get_or_create_workflow_state(db_read, project_id)
        current_phase = ws_read.stage
    finally:
        db_read.close()

    # 2. 计算目标阶段
    if direction == "backward":
        if current_phase not in backward_map:
            return {
                "current_phase": current_phase,
                "suggested_phase": current_phase,
                "advanced": False,
                "direction": direction,
                "reason": f"当前阶段「{phase_labels.get(current_phase, current_phase)}」不可回退",
                "current_phase_label": phase_labels.get(current_phase, current_phase),
                "suggested_phase_label": phase_labels.get(current_phase, current_phase),
            }
        suggested_phase = backward_map[current_phase]
        reason = f"从「{phase_labels.get(current_phase, current_phase)}」回退到「{phase_labels.get(suggested_phase, suggested_phase)}」"

    else:
        # direction == "forward" — 检查知识库完整度
        suggested_phase, reason = _evaluate_forward(
            current_phase, kb
        )

    # 3. 如果需要变更，获取行锁并写入
    advanced = suggested_phase != current_phase
    if advanced:
        db = SessionLocal()
        try:
            ws = get_or_create_workflow_state(db, project_id)

            # 获取行锁后再次确认阶段未被并发推进
            db.refresh(ws, with_for_update=True)
            actual_phase = ws.stage

            if actual_phase != current_phase:
                db.rollback()
                return {
                    "current_phase": actual_phase,
                    "suggested_phase": suggested_phase,
                    "advanced": False,
                    "direction": direction,
                    "reason": "并发更新检测：阶段已被其他请求更新",
                    "current_phase_label": phase_labels.get(actual_phase, actual_phase),
                    "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
                }

            ws.stage = suggested_phase
            db.commit()
        except Exception as e:
            db.rollback()
            return {"error": f"{'回退' if direction == 'backward' else '推进'}阶段失败: {e}"}
        finally:
            db.close()

    return {
        "current_phase": current_phase,
        "suggested_phase": suggested_phase,
        "advanced": advanced,
        "direction": direction,
        "reason": reason,
        "current_phase_label": phase_labels.get(current_phase, current_phase),
        "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
    }


def _evaluate_forward(current_phase: str, kb) -> tuple:
    """评估推进条件，返回 (suggested_phase, reason)"""
    from app.agents.constants import Phase

    outline = kb.outlines.get()
    characters = kb.characters.list_characters()
    world_setting = kb.world_setting.get()
    plot_blocks = kb.plots.list_plot_blocks()
    timeline = kb.timelines.list_timeline()

    suggested_phase = current_phase
    reason = ""

    if current_phase == Phase.INCUBATION:
        has_outline = outline and (outline.get("title") or outline.get("summary"))
        has_characters = len(characters) >= 1
        has_world = world_setting is not None
        if has_outline and has_characters and has_world:
            suggested_phase = Phase.STRUCTURE
            reason = "大纲、人物、世界观已就绪，可进入结构设计阶段"
        else:
            missing = []
            if not has_outline:
                missing.append("大纲")
            if not has_characters:
                missing.append("人物")
            if not has_world:
                missing.append("世界观")
            reason = f"孵化阶段尚未完成，缺少：{'、'.join(missing)}"

    elif current_phase == Phase.STRUCTURE:
        has_blocks = len(plot_blocks) >= 1
        if has_blocks:
            suggested_phase = Phase.WRITING
            reason = "情节块已规划，可进入写作阶段"
        else:
            reason = "结构阶段尚未完成，缺少情节块规划"

    elif current_phase == Phase.WRITING:
        total_chapters = 0
        if outline:
            total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0
        written = len(timeline) if timeline else 0
        if total_chapters > 0 and written >= total_chapters:
            suggested_phase = Phase.REVISION
            reason = f"全部 {total_chapters} 章已写完，可进入修订阶段"
        else:
            reason = f"写作阶段进行中（{written}/{total_chapters} 章）"

    elif current_phase == Phase.REVISION:
        reason = "已在修订阶段"

    return suggested_phase, reason
