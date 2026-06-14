"""生成大纲工具"""

from langchain_core.tools import tool



@tool
async def generate_outline(
    title: str,
    summary: str,
    chapter_count: int,
    plot_points: str = "[]",
    emotional_curve: str = "[]",
    characters: str = "[]",
    world_setting_summary: str = "",
) -> dict:
    """Generate and save the complete novel outline.

    Use this when the user asks to create or update the novel outline.
    This directly writes a full outline to the knowledge base — no approval needed.

    Args:
        title: Novel title (e.g., "星辰陨落之时")
        summary: 500-800 word story overview, must include surface conflict, deep conflict, and theme
        chapter_count: Total planned chapter count
        plot_points: JSON string list of plot points. Each should include:
                     [chapter_range, event, conflict, hook, foreshadowing_id]
        emotional_curve: JSON string list of emotional arc per plot block
        characters: JSON string list of character names in the novel
        world_setting_summary: Brief summary of the world setting (optional)
    """
    from app.agents.tools.utils import _kb, parse_json_param

    points, points_warn = parse_json_param(plot_points, [], "plot_points")

    curve, curve_warn = parse_json_param(emotional_curve, [], "emotional_curve")

    char_list, char_list_warn = parse_json_param(characters, [], "characters")

    kb = _kb()
    try:
        result = kb.outlines.upsert({
            "title": title,
            "summary": summary,
            "chapter_count_suggested": chapter_count,
            "chapter_count_confirmed": chapter_count,
            "plot_points": points,
            "emotional_curve": curve,
            "characters": char_list,
            "confirmed": True,
        })
        return {
            "action": "created",
            "title": title,
            "chapter_count": chapter_count,
            "plot_point_count": len(points),
            "message": f"大纲「{title}」已创建并写入知识库，共 {chapter_count} 章、{len(points)} 个情节节点",
        }
    except Exception as e:
        return {"error": str(e)}
