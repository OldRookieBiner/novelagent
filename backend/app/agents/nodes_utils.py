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
