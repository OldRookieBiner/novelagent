"""创建风格约束工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_style_constraints(
    style_anchor: str = "",
    taboo_words: str = "[]",
    forbidden_patterns: str = "[]",
    abstract_rules: str = "[]",
) -> dict:
    """Create or update style constraints for the novel.

    Use when the user describes writing style requirements, forbidden words,
    or style rules they want to enforce.

    Args:
        style_anchor: Reference text snippet that embodies the desired style
        taboo_words: JSON string list of forbidden words
        forbidden_patterns: JSON string list of forbidden sentence patterns
        abstract_rules: JSON string list of abstract style rules
    """
    import json as _json
    kb = _kb()

    try:
        taboo = _json.loads(taboo_words) if isinstance(taboo_words, str) else taboo_words
    except _json.JSONDecodeError:
        taboo = []

    try:
        patterns = _json.loads(forbidden_patterns) if isinstance(forbidden_patterns, str) else forbidden_patterns
    except _json.JSONDecodeError:
        patterns = []

    try:
        rules = _json.loads(abstract_rules) if isinstance(abstract_rules, str) else abstract_rules
    except _json.JSONDecodeError:
        rules = []

    existing = kb.styles.get_constraints()
    if existing:
        update_data = {}
        if taboo:
            update_data["taboo_words"] = taboo
        if patterns:
            update_data["forbidden_patterns"] = patterns
        if rules:
            update_data["abstract_rules"] = rules
        if style_anchor:
            update_data["style_anchor"] = style_anchor
        if update_data:
            updated = kb.styles.update_constraints_by_id(existing["id"], update_data)
            return {"action": "updated", "id": updated["id"], "message": "风格约束已更新"}
        return {"action": "unchanged", "message": "没有需要更新的内容"}
    else:
        created = kb.styles.create_constraints({
            "style_anchor": style_anchor,
            "taboo_words": taboo,
            "forbidden_patterns": patterns,
            "abstract_rules": rules,
        })
        return {"action": "created", "id": created["id"], "message": "风格约束已创建并写入知识库"}
