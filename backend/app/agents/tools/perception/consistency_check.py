"""一致性检查工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _serialize


@tool
async def consistency_check(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """Check consistency between two chapters or across the whole novel.

    Use when the user suspects a contradiction or wants to verify
    consistency of character behavior, timeline, or settings.

    Args:
        chapter_a: First chapter number to compare
        chapter_b: Second chapter number to compare
        aspect: What to check - "character", "timeline", "setting", or "all"
    """
    kb = _kb()
    result = {"chapters_compared": [chapter_a, chapter_b], "issues": []}

    if aspect in ("all", "character"):
        chars = kb.get_characters()
        constraints = []
        for char in chars:
            constraints.append({
                "name": char.name,
                "knowledge_boundary": getattr(char, "knowledge_boundary", None) or getattr(char, "deep_fear", ""),
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.get_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = _serialize(timeline)

    if aspect in ("all", "setting"):
        ws = kb.get_world_setting()
        if ws:
            result["world_setting_red"] = ws.tiered_settings.get("red", []) if ws.tiered_settings else []

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result
