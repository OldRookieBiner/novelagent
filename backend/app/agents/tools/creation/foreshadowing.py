"""创建伏笔工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_foreshadowing(
    content: str,
    level: str = "hint",
    planted_chapter: int | None = None,
    expected_resolve_chapter: int | None = None,
    related_characters: str = "[]",
) -> dict:
    """在小说中创建新的伏笔条目。

    当用户需要埋设伏笔时使用。伏笔会在后续章节中被追踪和回收。

    Args:
            content: Description of the foreshadowing element
            level: Foreshadowing level - one of: hint (暗示), strengthened (强化), revealed (揭示)
            planted_chapter: Chapter number where the foreshadowing is planted
            expected_resolve_chapter: Chapter number where the foreshadowing is expected to be resolved
            related_characters: JSON string list of related character names
    """
    kb = _kb()

    characters, characters_warn = parse_json_param(related_characters, [], "related_characters")

    data = {
        "content": content,
        "level": level,
        "related_characters": characters,
    }
    if planted_chapter is not None:
        data["planted_chapter"] = planted_chapter
    if expected_resolve_chapter is not None:
        data["expected_resolve_chapter"] = expected_resolve_chapter

    f = kb.foreshadowings.create(data)
    return {
        "action": "created",
        "id": f["id"],
        "content": content[:80],
        "level": level,
        "message": f"伏笔已创建并写入知识库",
    }
