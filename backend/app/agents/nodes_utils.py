"""旧版节点工具函数（从 nodes/utils.py 迁移）

仅供 Agent 工具和 agents/services 使用。
这些函数接受 dict 参数（旧版 NovelState 格式），由调用方（如 _build_state_for_review）构造。
"""


def format_characters_info(state: dict) -> str:
    """格式化人物设定信息为提示词用字符串"""
    detailed_characters = state.get("characters", [])
    characters = state.get("outline_characters", [])
    info = state.get("collected_info", {})

    if detailed_characters:
        chars_str = "【详细人物设定】\n"
        for c in detailed_characters:
            chars_str += f"- {c.get('name', '')}（{c.get('role', '配角')}）：\n"
            for field in ("appearance", "personality", "backstory", "catchphrase",
                          "habit_action", "deep_fear", "core_motivation", "growth_arc", "signature_item"):
                val = c.get(field)
                if val:
                    labels = {
                        "appearance": "外貌", "personality": "性格", "backstory": "背景",
                        "catchphrase": "口头禅", "habit_action": "习惯动作", "deep_fear": "深层恐惧",
                        "core_motivation": "核心动机", "growth_arc": "成长弧线", "signature_item": "标志性物品",
                    }
                    chars_str += f"  {labels[field]}：{val}\n"
        return chars_str
    elif characters:
        return "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        return info.get("customProtagonist") or info.get("protagonist", "未指定")


def format_relations_info(state: dict, current_chapter: int) -> str:
    """格式化人物关系为提示词用字符串"""
    relations = state.get("relations", [])
    if not relations:
        return ""

    characters = state.get("characters", [])
    id_to_name = {c.get("id"): c.get("name", "") for c in characters if c.get("id")}

    relations_str = "\n【人物关系】\n"
    for r in relations:
        name_a = r.get("character1") or id_to_name.get(r.get("character_a_id"), "未知")
        name_b = r.get("character2") or id_to_name.get(r.get("character_b_id"), "未知")
        rel_type = r.get("relationship_type") or r.get("relation_type", "")
        desc = r.get("description") or r.get("current_status", "")
        relations_str += f"- {name_a} 与 {name_b}：{rel_type}"
        if desc:
            relations_str += f"（{desc}）"
        relations_str += "\n"
    return relations_str


def format_evolution_info(state: dict, current_chapter: int) -> tuple:
    """格式化人物演变历史和规划

    Returns: (evolution_str, evolution_plans_str)
    """
    evolution_records = state.get("evolution_records", [])
    evolution_plans = state.get("evolution_plans", [])

    evolution_str = ""
    if evolution_records:
        evolution_str = "\n【人物演变（历史）】\n"
        for e in evolution_records[-3:]:
            evolution_str += f"- 第{e.get('chapter_number', '')}章：{e.get('actual_changes', '')}\n"

    evolution_plans_str = ""
    if evolution_plans:
        nearby_plans = [
            p for p in evolution_plans
            if abs(p.get("chapter_number", 0) - current_chapter) <= 2
        ]
        if nearby_plans:
            evolution_plans_str = "\n【即将发生的关系变化】\n"
            for p in nearby_plans:
                evolution_plans_str += f"- 第{p.get('chapter_number', 0)}章：{p.get('changes', '')}\n"

    return evolution_str, evolution_plans_str


def format_world_setting(state: dict) -> str:
    """格式化世界观设定为提示词用字符串"""
    world_setting = state.get("outline_world_setting", {})
    info = state.get("collected_info", {})
    if world_setting:
        return f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        return info.get("customWorldSetting") or info.get("worldSetting", "未指定")


def safe_format(template: str, **kwargs) -> str:
    """安全格式化模板：转义参数中的花括号，防止 format() 注入。

    LLM 输出和用户输入可能包含 { 或 }，直接传给 str.format() 会引发 KeyError。
    此函数先将参数中的花括号替换为临时占位符，格式化后再恢复。
    """
    if not kwargs:
        return template

    SAFE_LBRACE = "\x00LBRACE\x00"
    SAFE_RBRACE = "\x00RBRACE\x00"
    escaped = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            escaped[key] = value.replace("{", SAFE_LBRACE).replace("}", SAFE_RBRACE)
        else:
            escaped[key] = value

    try:
        result = template.format(**escaped)
    except (KeyError, ValueError, IndexError) as e:
        import re as _re
        placeholders = _re.findall(r"\{(\w+)\}", template)
        missing = [p for p in placeholders if p not in kwargs]
        import logging
        logging.getLogger(__name__).warning(
            f"safe_format failed (first 80 chars): {template[:80]!r}, "
            f"error: {e}, missing keys: {missing}"
        )
        cleaned = _re.sub(r"\{\w+\}", "", template)
        return cleaned

    return result.replace(SAFE_LBRACE, "{").replace(SAFE_RBRACE, "}")


def parse_world_setting_response(response: str) -> dict:
    """解析 WORLD_SETTING_PROMPT 的 LLM 输出

    输出格式：
    ### 核心理念 / 核心概念
    [文本]

    ### 分级设定
    🔴 不可违反 / 🟡 可突破有代价 / 🟢 装饰性

    ### 关键地点
    1. [地点名]：[描述]

    Returns:
        dict with keys: core_concept, tiered_settings, key_locations
    """
    import re as _re

    tiered_settings = {"red": [], "yellow": [], "green": []}
    key_locations = []

    # 提取核心理念
    core_concept = ""
    m = _re.search(
        r'(?:###\s*核心理念|###\s*核心概念|##\s*核心理念)(.*?)(?=\n#{1,3}\s|\Z)',
        response,
        _re.DOTALL,
    )
    if m:
        core_concept = m.group(1).strip()

    if not core_concept:
        core_concept = response.strip()

    # 🔴 不可违反
    red_section = _re.search(
        r'(?:🔴|红色?|不可违反)[^\n]*\n(.*?)(?=(?:🟡|黄色?|可突破)|\n#{1,3}\s|\Z)',
        response,
        _re.DOTALL,
    )
    if red_section:
        items = _re.findall(r'^\s*\d+\.\s*(.+?)$', red_section.group(1), _re.MULTILINE)
        tiered_settings["red"] = [item.strip() for item in items if item.strip()]

    # 🟡 可突破有代价
    yellow_section = _re.search(
        r'(?:🟡|黄色?|可突破|有代价)[^\n]*\n(.*?)(?=(?:🟢|绿色?|装饰)|\n#{1,3}\s|\Z)',
        response,
        _re.DOTALL,
    )
    if yellow_section:
        items = _re.findall(r'^\s*\d+\.\s*(.+?)$', yellow_section.group(1), _re.MULTILINE)
        tiered_settings["yellow"] = [item.strip() for item in items if item.strip()]

    # 🟢 装饰性
    green_section = _re.search(
        r'(?:🟢|绿色?|装饰)[^\n]*\n(.*?)(?=\n#{1,3}\s|\Z)',
        response,
        _re.DOTALL,
    )
    if green_section:
        items = _re.findall(r'^\s*\d+\.\s*(.+?)$', green_section.group(1), _re.MULTILINE)
        tiered_settings["green"] = [item.strip() for item in items if item.strip()]

    # 关键地点
    location_section = _re.search(
        r'(?:###\s*关键地点|##\s*关键地点)[^\n]*\n(.*?)(?=\n#{1,3}\s|\Z)',
        response,
        _re.DOTALL,
    )
    if location_section:
        loc_items = _re.findall(r'^\s*\d+\.\s*(.+?)$', location_section.group(1), _re.MULTILINE)
        key_locations = [loc.strip() for loc in loc_items[:10] if loc.strip()]

    return {
        "core_concept": core_concept,
        "tiered_settings": tiered_settings,
        "key_locations": key_locations,
    }
