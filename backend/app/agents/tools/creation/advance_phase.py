"""推进阶段工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def advance_phase() -> dict:
    """Advance the creation phase based on knowledge base completeness.

    Checks the current phase and knowledge base state to determine if
    the project is ready to advance to the next creation phase:
    - incubation → structure: when outline + characters + world setting exist
    - structure → writing: when plot blocks + foreshadowings exist
    - writing → revision: when all planned chapters are written

    Only advances if completeness criteria are met. Returns current and
    suggested phase with a reason.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    from app.database import SessionLocal
    from app.models.workflow_state import WorkflowState
    from app.agents.constants import Phase

    kb = _kb()

    # 读取当前阶段
    db = SessionLocal()
    try:
        ws = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id
        ).first()
        current_phase = ws.stage if ws else Phase.INCUBATION
    finally:
        db.close()

    # 检查知识库完整度
    outline = kb.get_outline()
    characters = kb.get_characters()
    world_setting = kb.get_world_setting()
    plot_blocks = kb.get_plot_blocks()
    foreshadowings = kb.get_foreshadowings()
    timeline = kb.get_timeline()

    suggested_phase = current_phase
    reason = ""

    if current_phase == Phase.INCUBATION:
        has_outline = outline and (outline.title or outline.summary)
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
        has_foreshadowing = len(foreshadowings) >= 1
        if has_blocks:
            suggested_phase = Phase.WRITING
            reason = "情节块已规划，可进入写作阶段"
        else:
            reason = "结构阶段尚未完成，缺少情节块规划"

    elif current_phase == Phase.WRITING:
        total_chapters = 0
        if outline:
            total_chapters = outline.chapter_count_confirmed or outline.chapter_count_suggested or 0
        written = len(timeline) if timeline else 0
        if total_chapters > 0 and written >= total_chapters:
            suggested_phase = Phase.REVISION
            reason = f"全部 {total_chapters} 章已写完，可进入修订阶段"
        else:
            reason = f"写作阶段进行中（{written}/{total_chapters} 章）"

    elif current_phase == Phase.REVISION:
        reason = "已在修订阶段"

    # 如果可以推进，更新 DB
    advanced = suggested_phase != current_phase
    if advanced:
        db = SessionLocal()
        try:
            ws = db.query(WorkflowState).filter(
                WorkflowState.project_id == project_id
            ).first()
            if ws:
                ws.stage = suggested_phase
                db.commit()
        except Exception as e:
            db.rollback()
            return {"error": f"更新阶段失败: {e}"}
        finally:
            db.close()

    phase_labels = {
        Phase.INCUBATION: "创意孵化",
        Phase.STRUCTURE: "结构设计",
        Phase.WRITING: "写作中",
        Phase.REVISION: "修订中",
    }

    return {
        "current_phase": current_phase,
        "suggested_phase": suggested_phase,
        "advanced": advanced,
        "reason": reason,
        "current_phase_label": phase_labels.get(current_phase, current_phase),
        "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
    }
