"""伏笔建议工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def suggest_foreshadowing(current_chapter: int) -> dict:
    """Suggest foreshadowing placement based on current plot block.

    Analyzes the current plot block and existing foreshadowing map
    to suggest new foreshadowings that fit the story structure.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    block = kb.plots.get_current_plot_block(current_chapter)
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]

    if not block:
        return {"suggestion": "当前没有情节块信息，建议先完成结构设计"}

    suggestions = []
    for question in (block.get("questions_to_raise") or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
        })

    if len(active) < 3 and block.get("chapter_end") and block.get("chapter_start"):
        span = block["chapter_end"] - block["chapter_start"]
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
            })

    return {
        "current_chapter": current_chapter,
        "plot_block": block.get("title") if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }
