"""节点共享工具函数"""


def _format_chapter_outline_str(chapter_outline: dict) -> str:
    """格式化章节大纲为提示词用字符串"""
    return f"""
章节名：{chapter_outline.get("title", "")}
场景：{chapter_outline.get("scene", "")}
人物：{chapter_outline.get("characters", "")}
情节：{chapter_outline.get("plot", "")}
冲突：{chapter_outline.get("conflict", "")}
转折：{chapter_outline.get("turning_point", "无")}
钩子：{chapter_outline.get("hook", "")}
"""


def format_characters_info(state: dict) -> str:
    """格式化人物设定信息为提示词用字符串

    优先使用详细人物设定(characters 字段)，回退到大纲人物设定，
    最后回退到灵感采集信息。
    """
    detailed_characters = state.get("characters", [])
    characters = state.get("outline_characters", [])
    info = state.get("collected_info", {})

    if detailed_characters:
        chars_str = "【详细人物设定】\n"
        for c in detailed_characters:
            chars_str += f"- {c.get('name', '')}（{c.get('role', '配角')}）：\n"
            if c.get("appearance"):
                chars_str += f"  外貌：{c.get('appearance')}\n"
            if c.get("personality"):
                chars_str += f"  性格：{c.get('personality')}\n"
            if c.get("background"):
                chars_str += f"  背景：{c.get('background')}\n"
            if c.get("skills"):
                chars_str += f"  能力：{c.get('skills')}\n"
            if c.get("goals"):
                chars_str += f"  目标：{c.get('goals')}\n"
        return chars_str
    elif characters:
        return "\n".join(
            [
                f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
                for c in characters
            ]
        )
    else:
        return info.get("customProtagonist") or info.get("protagonist", "未指定")


def format_relations_info(state: dict, current_chapter: int) -> str:
    """格式化人物关系为提示词用字符串

    兼容两种字段命名：
    - 旧格式：character1/character2/relationship_type/description
    - 新格式：character_a_id/character_b_id/relation_type/current_status
    """
    relations = state.get("relations", [])
    if not relations:
        return ""

    # 构建 ID→名字映射（解决关系数据只有 ID 没有名字的问题）
    characters = state.get("characters", [])
    id_to_name = {c.get("id"): c.get("name", "") for c in characters if c.get("id")}

    relations_str = "\n【人物关系】\n"
    for r in relations:
        # 兼容两种字段命名：旧格式优先
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
    """格式化人物演变历史和规划为提示词用字符串

    Returns:
        (evolution_str, evolution_plans_str)
    """
    evolution_records = state.get("evolution_records", [])
    evolution_plans = state.get("evolution_plans", [])

    evolution_str = ""
    if evolution_records:
        evolution_str = "\n【人物演变（历史）】\n"
        for e in evolution_records[-3:]:
            evolution_str += (
                f"- 第{e.get('chapter_number', '')}章：{e.get('actual_changes', '')}\n"
            )

    evolution_plans_str = ""
    if evolution_plans:
        nearby_plans = [
            p
            for p in evolution_plans
            if abs(p.get("chapter_number", 0) - current_chapter) <= 2
        ]
        if nearby_plans:
            evolution_plans_str = "\n【即将发生的关系变化】\n"
            for p in nearby_plans:
                evolution_plans_str += (
                    f"- 第{p.get('chapter_number', 0)}章：{p.get('changes', '')}\n"
                )

    return evolution_str, evolution_plans_str


def format_world_setting(state: dict) -> str:
    """格式化世界观设定为提示词用字符串"""
    world_setting = state.get("outline_world_setting", {})
    info = state.get("collected_info", {})

    if world_setting:
        return f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        return info.get("customWorldSetting") or info.get("worldSetting", "未指定")


def parse_words_per_chapter(collected_info: dict | None) -> tuple[int, str]:
    """解析每章最低字数

    新格式返回 (min_words, display_text)，不再返回上下限区间。
    兼容旧 range 格式 "2000-2500"，取下限作为最低字数。

    Args:
        collected_info: 灵感采集信息字典

    Returns:
        (最低字数, 显示文本)
    """
    DEFAULT_MIN = 3000
    DEFAULT_DISPLAY = "3000字起"

    if not collected_info:
        return DEFAULT_MIN, DEFAULT_DISPLAY

    wpc_str = collected_info.get("wordsPerChapter", "")
    custom_val = collected_info.get("customWordsPerChapter")

    # custom 模式
    if wpc_str == "custom":
        if custom_val and isinstance(custom_val, int) and custom_val > 0:
            return custom_val, f"{custom_val}字起"
        return DEFAULT_MIN, DEFAULT_DISPLAY

    # 纯数字格式（新格式）
    if wpc_str:
        try:
            val = int(wpc_str)
            if val > 0:
                return val, f"{val}字起"
        except (ValueError, TypeError):
            pass

    # 兼容旧数据：range 格式 "2000-2500"，取下限作为最低字数
    if "-" in str(wpc_str):
        try:
            lower = int(str(wpc_str).split("-")[0].strip())
            if lower > 0:
                return lower, f"{lower}字起"
        except (ValueError, IndexError):
            pass

    return DEFAULT_MIN, DEFAULT_DISPLAY

def get_prompts_from_state(state: dict, key: str) -> tuple[str, str]:
    """从 state["_prompts"] 获取 system/user 模板

    支持 dict 格式 {"system": ..., "user": ...} 和旧字符串格式。
    旧字符串格式时 system 返回空串，整个模板作为 user message。

    Args:
        state: LangGraph 状态字典
        key: prompt 键名（如 "review", "rewrite", "chapter_content_generation"）

    Returns:
        (system_template, user_template)
    """
    prompts = state.get("_prompts", {})
    prompt_data = prompts.get(key) if prompts else None

    if prompt_data and isinstance(prompt_data, dict):
        return prompt_data.get("system", ""), prompt_data.get("user", "")
    elif prompt_data and isinstance(prompt_data, str):
        # 旧格式兼容：整个模板作为 user message
        return "", prompt_data
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        default = DEFAULT_PROMPTS.get(key, {})
        if isinstance(default, dict):
            return default.get("system", ""), default.get("user", "")
        return "", default or ""


def find_chapter_by_number(written_chapters: list[dict], current_chapter: int) -> dict | None:
    """根据 current_chapter 查找已写章节内容

    优先查找 current_chapter - 1（因为 current_chapter 已递增，指向下一个待写章节），
    如果没找到则回退到 current_chapter。

    Args:
        written_chapters: 已写章节列表
        current_chapter: 当前章节号（通常已递增 1）

    Returns:
        找到的章节字典，没有则返回 None
    """
    # 先尝试 current_chapter - 1（已写入的当前章节）
    for chapter in written_chapters:
        if chapter.get("chapter_number") == current_chapter - 1:
            return chapter

    # 回退：尝试 current_chapter
    for chapter in written_chapters:
        if chapter.get("chapter_number") == current_chapter:
            return chapter

    return None


def find_chapter_outline_by_number(chapter_outlines: list[dict], current_chapter: int) -> dict | None:
    """根据 current_chapter 查找章节大纲

    优先查找 current_chapter - 1，如果没有则回退到 current_chapter。

    Args:
        chapter_outlines: 章节大纲列表
        current_chapter: 当前章节号（通常已递增 1）

    Returns:
        找到的大纲字典，没有则返回 None
    """
    # 先尝试 current_chapter - 1
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter - 1:
            return outline

    # 回退：尝试 current_chapter
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter:
            return outline

    return None

