"""创建子情节工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_subplot(
    name: str,
    characters: str = "[]",
    current_status: str = "developing",
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """Create a new subplot (支线) in the novel.

    Use when the user wants to add a subplot or secondary storyline.
    This directly writes to the knowledge base.

    Args:
        name: Subplot name (e.g., "皇室阴谋线", "师徒恩怨线")
        characters: JSON string list of character names involved
        current_status: Current subplot status - one of: hint (暗示), developing (发展中), pending_intersection (待交汇), resolved (已解决)
        raised_in_chapter: Chapter number where this subplot is first introduced
        planned_intersection_chapter: Chapter number where this subplot intersects with the main plot
        expected_resolution_chapter: Chapter number where this subplot resolves
    """
    import json as _json
    kb = _kb()

    try:
        chars = _json.loads(characters) if isinstance(characters, str) else characters
    except _json.JSONDecodeError:
        chars = []

    data = {"name": name, "characters": chars, "current_status": current_status}
    if raised_in_chapter is not None:
        data["raised_in_chapter"] = raised_in_chapter
    if planned_intersection_chapter is not None:
        data["planned_intersection_chapter"] = planned_intersection_chapter
    if expected_resolution_chapter is not None:
        data["expected_resolution_chapter"] = expected_resolution_chapter

    s = kb.plots.create_subplot(data)
    return {
        "action": "created",
        "id": s["id"],
        "name": name,
        "message": f"支线「{name}」已创建并写入知识库",
    }
