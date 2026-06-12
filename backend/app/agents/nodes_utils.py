"""节点工具函数

保留 initialization.py 使用的 safe_format 和 parse_world_setting_response。
旧版 format_characters_info / format_relations_info / format_evolution_info / format_world_setting
已迁入 ChapterQuality 服务，接受 KB dict 而非旧版 NovelState dict。
"""


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
