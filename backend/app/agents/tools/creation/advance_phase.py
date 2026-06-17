"""推进阶段工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def advance_phase(direction: str = "forward") -> dict:
    """推进或回退创作阶段.

    direction="forward": 根据知识库完整度判断是否可以进入下一阶段.
    direction="backward": 回退到上一阶段(Writing->Structure, Structure->Incubation).

    Args:
        direction: 方向 - "forward"(推进) 或 "backward"(回退)
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    kb = _kb()

    # 阶段标签: 使用字符串 key 与 current_phase 类型一致
    phase_labels = {
        "incubation": "创意孵化",
        "structure": "结构设计",
        "writing": "写作中",
        "revision": "修订中",
    }

    # 1. 读取当前阶段
    current_phase = kb.workflows.get_current_phase()

    # 2. 计算目标阶段(逻辑不变, 仍在工具层)
    if direction == "backward":
        # 使用字符串 key/value, 与 WorkflowStore.advance() 保持一致
        backward_map = {
            "writing": "structure",
            "structure": "incubation",
        }
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
        suggested_phase, reason = _evaluate_forward(current_phase, kb)

    # 3. 执行带锁写入
    advanced = suggested_phase != current_phase
    if advanced:
        result = kb.workflows.advance(direction, expected_current=current_phase)
        if result.get("conflict"):
            actual = result.get("current_phase", current_phase)
            return {
                "current_phase": actual,
                "suggested_phase": suggested_phase,
                "advanced": False,
                "direction": direction,
                "reason": "并发更新检测: 阶段已被其他请求更新",
                "current_phase_label": phase_labels.get(actual, actual),
                "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
            }

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
    """评估推进条件, 返回 (suggested_phase, reason).

    current_phase 和返回值均为字符串(如 "incubation"/"structure"),
    与 WorkflowStore 和 advance_phase 工具层保持一致.
    """
    outline = kb.outlines.get()
    characters = kb.characters.list_characters()
    world_setting = kb.world_setting.get()
    plot_blocks = kb.plots.list_plot_blocks()
    timeline = kb.timelines.list_timeline()

    suggested_phase = current_phase
    reason = ""

    if current_phase == "incubation":
        has_outline = outline and (outline.get("title") or outline.get("summary"))
        has_characters = len(characters) >= 1
        has_world = world_setting is not None
        if has_outline and has_characters and has_world:
            suggested_phase = "structure"
            reason = "大纲、人物、世界观已就绪, 可进入结构设计阶段"
        else:
            missing = []
            if not has_outline:
                missing.append("大纲")
            if not has_characters:
                missing.append("人物")
            if not has_world:
                missing.append("世界观")
            reason = f"孵化阶段尚未完成, 缺少: {'、'.join(missing)}"

    elif current_phase == "structure":
        has_blocks = len(plot_blocks) >= 1
        if has_blocks:
            suggested_phase = "writing"
            reason = "情节块已规划, 可进入写作阶段"
        else:
            reason = "结构阶段尚未完成, 缺少情节块规划"

    elif current_phase == "writing":
        total_chapters = 0
        if outline:
            total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0
        written = len(timeline) if timeline else 0
        if total_chapters > 0 and written >= total_chapters:
            suggested_phase = "revision"
            reason = f"全部 {total_chapters} 章已写完, 可进入修订阶段"
        else:
            reason = f"写作阶段进行中({written}/{total_chapters} 章)"

    elif current_phase == "revision":
        reason = "已在修订阶段"

    return suggested_phase, reason
