"""工具调用后自动触发链

仅在工具成功时触发。检查结果附在 tool_result 的 auto_check_results 中。
Hook 实现为轻量版，不做完整分析。
R17 修正：Hook 失败时记录到 auto_check_results + logging.warning，不静默吞异常。
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


async def _hook_foreshadowing_check(project_id: int, tool_result: dict) -> dict:
    """伏笔超期检查 hook（轻量版：只检查超期伏笔数量）"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)
    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False, "reason": "无法确定章节号"}
    overdue = kb.foreshadowings.list_overdue(ch_num)
    if overdue:
        return {
            "checked": True,
            "overdue_count": len(overdue),
            "warning": f"有 {len(overdue)} 个伏笔已超过预期回收章节",
            "overdue_ids": [f["id"] for f in overdue[:3]],
        }
    return {"checked": True, "overdue_count": 0}


async def _hook_style_quick_check(project_id: int, tool_result: dict) -> dict:
    """风格快速检查 hook（轻量版：只比较最近 3 章对话比和句长）"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    kb = KnowledgeBaseService(project_id)
    snapshots = kb.styles.list_snapshots(last_n=3)
    if len(snapshots) < 2:
        return {"checked": False, "reason": "快照不足"}

    recent_dialogue = sum(s.get("dialogue_ratio", 0) or 0 for s in snapshots[:3]) / len(snapshots[:3])
    overall = kb.styles.list_snapshots(last_n=10)
    if len(overall) < 3:
        return {"checked": False, "reason": "整体快照不足"}
    overall_dialogue = sum(s.get("dialogue_ratio", 0) or 0 for s in overall) / len(overall)

    drift = abs(recent_dialogue - overall_dialogue) / max(overall_dialogue, 0.01)
    if drift > 0.25:
        return {
            "checked": True,
            "warning": f"最近 3 章对话比 {recent_dialogue:.1%} 偏离整体平均 {overall_dialogue:.1%}",
            "direction": "偏高" if recent_dialogue > overall_dialogue else "偏低",
        }
    return {"checked": True, "drift": "normal"}


async def _hook_rhythm_quick_check(project_id: int, tool_result: dict) -> dict:
    """章节追踪记录完成后快速节奏对比 hook。

    仅挂在 record_chapter_meta 之后：因为 timeline.tension_score 由该工具写入。
    比较情节块的预期张力与本章实际张力，偏差 > 1 给出警告与方向建议。
    """
    from app.agents.services.knowledge_base import KnowledgeBaseService
    from app.agents.tools.utils import _mood_to_tension

    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False, "reason": "无法确定章节号"}

    kb = KnowledgeBaseService(project_id)
    block = kb.plots.get_current_plot_block(ch_num)
    if not block or not block.get("expected_mood"):
        return {"checked": False, "reason": "当前章节无情节块或预期情绪"}

    timeline = kb.timelines.get_by_chapter_number(ch_num)
    if not timeline:
        return {"checked": False, "reason": "当前章节无时间线数据"}

    expected_tension = _mood_to_tension(block["expected_mood"])
    actual_tension = timeline.get("tension_score") or 3
    deviation = abs(actual_tension - expected_tension)

    if deviation > 1:
        direction = "偏低" if actual_tension < expected_tension else "偏高"
        suggestion = (
            "建议在后续章节增加紧迫感事件或冲突密度"
            if actual_tension < expected_tension
            else "建议在后续章节适当放缓节奏，增加呼吸感场景"
        )
        return {
            "checked": True,
            "warning": (
                f"节奏偏差：情节块「{block['title']}」预期情绪「{block['expected_mood']}」"
                f"（张力 {expected_tension}），实际张力 {actual_tension}，{direction}"
            ),
            "suggestion": suggestion,
            "deviation": deviation,
        }

    return {"checked": True, "deviation": deviation, "status": "normal"}


# Hook 注册表
TOOL_HOOKS: dict[str, list[str]] = {
    "generate_chapter_content": ["foreshadowing_check", "style_quick_check"],
    "record_chapter_meta": ["rhythm_quick_check"],
}

_HOOK_FUNCTIONS: dict[str, Callable] = {
    "foreshadowing_check": _hook_foreshadowing_check,
    "style_quick_check": _hook_style_quick_check,
    "rhythm_quick_check": _hook_rhythm_quick_check,
}


async def run_post_hooks(tool_name: str, tool_result: dict, project_id: int) -> dict:
    """工具调用后的自动检查链

    仅在工具成功时触发。检查结果附在 tool_result 的 auto_check_results 中。
    Hook 失败不影响主流程。
    """
    hooks = TOOL_HOOKS.get(tool_name, [])
    if not hooks:
        return tool_result

    auto_results = {}
    for hook_name in hooks:
        try:
            hook_fn = _HOOK_FUNCTIONS[hook_name]
            result = await hook_fn(project_id, tool_result)
            auto_results[hook_name] = result
        except Exception as e:
            logger.warning("Hook %s 执行失败: %s", hook_name, e)
            auto_results[hook_name] = {"checked": False, "error": str(e)}

    tool_result["auto_check_results"] = auto_results
    return tool_result
