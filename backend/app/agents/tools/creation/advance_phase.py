"""推进阶段工具

R20 修正：先通过 KB 读取完整度判断（KB 用独立 session，不需要行锁），
判断完成后再获取行锁写入，最小化行锁持有时间。
G1 增强：支持 direction=backward 进行阶段回退。
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
    from app.models.workflow_state import WorkflowState
    from app.agents.constants import Phase

    kb = _kb()

    # 阶段标签（提前定义，G1 要求）
    phase_labels = {
        Phase.INCUBATION: "创意孵化",
        Phase.STRUCTURE: "结构设计",
        Phase.WRITING: "写作中",
        Phase.REVISION: "修订中",
    }

    # G1: 回退逻辑
    if direction == "backward":
        # 回退映射
        backward_map = {
            Phase.WRITING: Phase.STRUCTURE,
            Phase.STRUCTURE: Phase.INCUBATION,
        }

        # 1. 无锁读取当前阶段
        db_read = SessionLocal()
        try:
            ws_read = db_read.query(WorkflowState).filter(
                WorkflowState.project_id == project_id
            ).first()
            current_phase = ws_read.stage if ws_read else Phase.INCUBATION
        finally:
            db_read.close()

        # 2. 检查是否可以回退
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

        # 3. 获取行锁并写入
        db = SessionLocal()
        try:
            ws = db.query(WorkflowState).filter(
                WorkflowState.project_id == project_id
            ).with_for_update().first()

            actual_phase = ws.stage if ws else Phase.INCUBATION
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

            if not ws:
                ws = WorkflowState(project_id=project_id, stage=suggested_phase)
                db.add(ws)
            else:
                ws.stage = suggested_phase
            db.commit()
            advanced = True
        except Exception as e:
            db.rollback()
            return {"error": f"回退阶段失败: {e}"}
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

    # 原有的推进逻辑 (direction == "forward")
    # 1. 无锁读取当前阶段（仅用于判断，不持锁）
    db_read = SessionLocal()
    try:
        ws_read = db_read.query(WorkflowState).filter(
            WorkflowState.project_id == project_id
        ).first()
        current_phase = ws_read.stage if ws_read else Phase.INCUBATION
    finally:
        db_read.close()

    # 2. 检查知识库完整度（通过 KB facade，每次调用使用独立 session）
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

    # 3. 如果可以推进，获取行锁并写入（最小化锁持有时间）
    advanced = suggested_phase != current_phase
    if advanced:
        db = SessionLocal()
        try:
            ws = db.query(WorkflowState).filter(
                WorkflowState.project_id == project_id
            ).with_for_update().first()

            # 双重检查：获取锁后确认阶段未被并发推进
            actual_phase = ws.stage if ws else Phase.INCUBATION
            if actual_phase != current_phase:
                db.rollback()
                return {
                    "current_phase": actual_phase,
                    "suggested_phase": suggested_phase,
                    "advanced": False,
                    "direction": direction,
                    "reason": "并发推进检测：阶段已被其他请求更新",
                    "current_phase_label": phase_labels.get(actual_phase, actual_phase),
                    "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
                }

            if not ws:
                ws = WorkflowState(project_id=project_id, stage=suggested_phase)
                db.add(ws)
            else:
                ws.stage = suggested_phase
            db.commit()
        except Exception as e:
            db.rollback()
            return {"error": f"推进阶段失败: {e}"}
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
