"""生成大纲工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id


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
    import json as _json
    from app.agents.services.outline_service import (
        update_outline,
    )
    from app.database import SessionLocal

    try:
        points = _json.loads(plot_points) if isinstance(plot_points, str) else plot_points
    except _json.JSONDecodeError:
        points = []

    try:
        curve = _json.loads(emotional_curve) if isinstance(emotional_curve, str) else emotional_curve
    except _json.JSONDecodeError:
        curve = []

    try:
        char_list = _json.loads(characters) if isinstance(characters, str) else characters
    except _json.JSONDecodeError:
        char_list = []

    project_id = get_project_id()
    db = SessionLocal()
    committed = False
    try:
        result = await update_outline(
            db,
            project_id,
            {
                "title": title,
                "summary": summary,
                "chapter_count_suggested": chapter_count,
                "chapter_count_confirmed": chapter_count,
                "plot_points": points,
                "emotional_curve": curve,
                "characters": char_list,
                "confirmed": True,
            },
        )
        if "error" in result:
            db.rollback()
            return result
        db.commit()
        committed = True
        return {
            "action": "created",
            "title": title,
            "chapter_count": chapter_count,
            "plot_point_count": len(points),
            "message": f"大纲「{title}」已创建并写入知识库，共 {chapter_count} 章、{len(points)} 个情节节点",
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass
