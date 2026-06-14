"""创建风格约束工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_style_constraints(
    style_anchor: str = "",
    taboo_words: str = "[]",
    forbidden_patterns: str = "[]",
    abstract_rules: str = "[]",
) -> dict:
    """创建或更新小说的风格约束。

    当用户需要定义写作风格规则时使用。包括禁忌词、禁止模式和抽象规则。

    Args:
            style_anchor: 体现目标风格的参考文本片段
            taboo_words: JSON 字符串列表，禁用词
            forbidden_patterns: JSON 字符串列表，禁用句式
            abstract_rules: JSON 字符串列表，抽象风格规则
    """
    kb = _kb()

    taboo, taboo_warn = parse_json_param(taboo_words, [], "taboo_words")

    patterns, patterns_warn = parse_json_param(forbidden_patterns, [], "forbidden_patterns")

    rules, rules_warn = parse_json_param(abstract_rules, [], "abstract_rules")

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
