"""创建子情节工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_subplot(
    name: str,
    characters: str = "[]",
    current_status: str = "developing",
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """在小说中创建新的支线。

    当用户需要添加独立于主线的支线故事时使用。支线有自己的状态和进展追踪。

    Args:
        name: 支线名称
        description: 支线描述
        characters: JSON 字符串列表，参与角色名
        plot_block_id: 关联的情节块 ID
    """
    kb = _kb()

    chars, chars_warn = parse_json_param(characters, [], "characters")

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
