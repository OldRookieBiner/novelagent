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


def _strip_control_chars_in_strings(text: str) -> str:
    """转义 JSON 字符串字面量内部的裸控制字符（换行/回车/tab）。

    中文大模型生成长文本（如 500-800 字概述）时，常在字符串值里直接换行，
    产生未转义的控制字符，导致 json.loads 抛 JSONDecodeError。这里在不改变
    可见内容的前提下，把字符串内部的裸 \\n / \\r / \\t 转成合法转义序列。
    仅作用于引号包裹的字符串内部，不触碰结构性空白。
    """
    out = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                continue
            if ch == '"':
                out.append(ch)
                in_str = False
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            out.append(ch)
        else:
            out.append(ch)
            if ch == '"':
                in_str = True
    return "".join(out)


def _repair_json_candidate(candidate: str):
    """对疑似 JSON 的候选串做最小净化后重试解析，全部失败返回 None。

    仅修复中文大模型高频的、不改变语义的瑕疵：
    1. 字符串内部裸换行/回车/tab → 合法转义；
    2. 删除对象/数组结尾的尾随逗号；
    3. 全角引号 “ ” → 半角 "（作为结构定界符的最后一搏）。

    逐级叠加尝试，任一步成功即返回，避免过度改写误伤合法内容。
    """
    import json as _json
    import re as _re

    attempts = []

    # 1: 仅转义字符串内裸控制字符（最常见、最安全）
    step1 = _strip_control_chars_in_strings(candidate)
    attempts.append(step1)

    # 2: 在 1 基础上删尾随逗号（,} / ,]）
    step2 = _re.sub(r",(\s*[}\]])", r"\1", step1)
    attempts.append(step2)

    # 3: 在 2 基础上把全角引号转半角（仅当含全角引号时才尝试）
    if "“" in step2 or "”" in step2:
        step3 = step2.replace("“", '"').replace("”", '"')
        # 全角转半角后可能又产生需要净化的控制字符，重新走一遍
        attempts.append(_strip_control_chars_in_strings(step3))

    for text in attempts:
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            continue
    return None


def extract_json_block(response: str):
    """从 LLM 输出中健壮提取 JSON（对象或数组）

    多级策略，逐级降级：
    1. ```json 代码块中提取
    2. 任意 ``` 代码块中提取
    3. 裸文本中第一个完整的 {...} 或 [...]（括号配对扫描）

    每个候选串先严格 json.loads；失败时再经 _repair_json_candidate 做最小
    净化重试（修复中文大模型高频的裸换行/尾随逗号/全角引号瑕疵）。
    成功返回解析后的 dict / list；失败返回 None（调用方据此降级到旧正则）。
    """
    import json as _json
    import re as _re

    if not response or not response.strip():
        return None

    # 策略 1/2：代码块（优先 ```json，其次任意 ```）
    for pat in (
        r'```json\s*([\[{][\s\S]*?[\]}])\s*```',
        r'```\s*([\[{][\s\S]*?[\]}])\s*```',
    ):
        m = _re.search(pat, response)
        if m:
            candidate = m.group(1)
            try:
                return _json.loads(candidate)
            except _json.JSONDecodeError:
                repaired = _repair_json_candidate(candidate)
                if repaired is not None:
                    return repaired

    # 策略 3：裸文本括号配对扫描（取最先出现的 { 或 [）
    starts = [i for i in (response.find("{"), response.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    open_ch = response[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(response)):
        ch = response[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                candidate = response[start:i + 1]
                try:
                    return _json.loads(candidate)
                except _json.JSONDecodeError:
                    return _repair_json_candidate(candidate)
    return None
