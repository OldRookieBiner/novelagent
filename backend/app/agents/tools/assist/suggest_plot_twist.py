"""反转建议工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def suggest_plot_twist(current_chapter: int) -> dict:
    """Suggest a plot twist based on rhythm curve, character arcs, and foreshadowings.

    Use when the user wants ideas for a surprising turn in the story.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    timeline = kb.timelines.list_timeline()
    foreshadowings = kb.foreshadowings.list_foreshadowings(status="active")
    characters = kb.characters.list_characters()
    block = kb.plots.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.get("tension_score"):
                recent_tension.append(t["tension_score"])

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f["id"] for f in foreshadowings[:3]],
        })

    for c in characters:
        core_mot = c.get("core_motivation", "")
        if core_mot and len(core_mot) > 10:
            char_name = c["name"]
            twist_types.append({
                "type": "角色反转",
                "reason": f"角色「{char_name}」的动机可以制造意想不到的转折",
                "character_id": c["id"],
                "character_name": char_name,
            })
            break

    return {
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:3],
    }
