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
    """格式化人物关系为提示词用字符串"""
    relations = state.get("relations", [])
    if not relations:
        return ""

    relations_str = "\n【人物关系】\n"
    for r in relations:
        relations_str += f"- {r.get('character1', '')} 与 {r.get('character2', '')}：{r.get('relationship_type', '')}"
        if r.get("description"):
            relations_str += f"（{r.get('description')}）"
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
