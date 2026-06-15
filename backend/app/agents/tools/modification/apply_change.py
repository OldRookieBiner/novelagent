"""应用变更提议工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


# new_value 白名单过滤 - 防止幻影参数通过 Store setattr 静默丢失
_ALLOWED_KEYS = {
    "world_setting": {"core_concept", "tiered_settings", "key_locations"},
    "character": {"name", "role", "personality", "catchphrase", "habit_action", "deep_fear", "core_motivation", "growth_arc", "appearance", "backstory", "signature_item"},
    "foreshadowing": {"content", "level", "appearance_count", "status", "planted_chapter", "expected_resolve_chapter", "resolved_chapter", "related_characters"},
    "style": {"taboo_words", "forbidden_patterns", "style_anchor", "abstract_rules"},
    "outline": {"title", "summary", "plot_points", "characters", "world_setting", "emotional_curve", "collected_info", "inspiration_template", "messages", "chapter_count_suggested", "chapter_count_confirmed", "confirmed"},
    "relation": {"character_a_id", "character_b_id", "relation_type", "direction", "current_status", "trust_level"},
    "outline_adjustment": {"title", "summary", "plot_points", "characters", "world_setting", "emotional_curve", "collected_info", "inspiration_template", "messages", "chapter_count_suggested", "chapter_count_confirmed", "confirmed"},
}


@tool
async def apply_change(change_id: int) -> dict:
    """应用已确认的变更提议到知识库。

    当用户确认了某个设定变更、大纲调整或章节重写提议后，
    使用此工具将变更实际应用到知识库中。

    注意：chapter_rewrite 类型不直接应用，而是返回提示引导使用 rewrite_chapter 工具。

    Args:
        change_id: 变更提议的 ID
    """
    kb = _kb()

    # 1. 获取变更记录
    change = kb.changes.get(change_id)
    if change is None:
        return {"error": f"变更 ID {change_id} 不存在"}

    # 2. 检查状态是否为 proposed
    if change.get("status") != "proposed":
        return {"error": f"变更状态为「{change.get('status')}」，只能应用 proposed 状态的变更"}

    target_type = change.get("target_type")
    target_id = change.get("target_id")
    new_value = change.get("new_value", {})

    # 3. 特殊处理 chapter_rewrite - 引导使用 rewrite_chapter
    if target_type == "chapter_rewrite":
        return {
            "action": "redirect",
            "message": "章节重写需要使用 rewrite_chapter 工具执行",
            "change_id": change_id,
            "hint": f"rewrite_chapter(chapter_number={new_value.get('chapter_number')}, reason='{new_value.get('reason', '')}')",
        }

    # 4. 特殊处理 outline_adjustment - 调用大纲更新，忽略 target_id（固定为 0）
    if target_type == "outline_adjustment":
        # outline_adjustment 的 new_value 包含变更描述，需要更新大纲
        try:
            kb.outlines.update(new_value)
            kb.changes.update(change_id, {"status": "applied", "author_decision": "proceed"})
            return {
                "action": "applied",
                "change_id": change_id,
                "message": f"大纲调整已应用（变更描述：{change.get('description', '')[:50]}...）",
            }
        except Exception as e:
            return {"error": f"大纲调整应用失败: {str(e)}"}

    # 5. 根据 target_type 应用变更
    # 过滤 new_value 的 key，只保留模型允许的列名
    allowed_keys = _ALLOWED_KEYS.get(target_type, set())
    filtered_keys = []
    if allowed_keys:
        filtered_new_value = {}
        for k, v in new_value.items():
            if k in allowed_keys:
                filtered_new_value[k] = v
            else:
                filtered_keys.append(k)
        new_value = filtered_new_value

    if not new_value:
        return {"error": f"变更内容为空或所有字段都被过滤（filtered_keys: {filtered_keys}）"}

    try:
        if target_type == "world_setting":
            ws = kb.world_setting.get()
            if ws:
                kb.world_setting.update(new_value)
            else:
                kb.world_setting.create(new_value)
        elif target_type == "character":
            kb.characters.update_character(target_id, new_value)
        elif target_type == "foreshadowing":
            kb.foreshadowings.update(target_id, new_value)
        elif target_type == "style":
            kb.styles.update_constraints(new_value)
        elif target_type == "relation":
            kb.characters.update_relation(target_id, new_value)
        else:
            return {"error": f"不支持的 target_type: {target_type}"}

        # 6. 更新变更状态为 applied
        kb.changes.update(change_id, {"status": "applied", "author_decision": "proceed"})

        result = {
            "action": "applied",
            "change_id": change_id,
            "target_type": target_type,
            "target_id": target_id,
            "message": f"{target_type} 变更已应用到 ID {target_id}",
        }
        if filtered_keys:
            result["filtered_keys"] = filtered_keys
            result["warning"] = f"以下非模型字段被过滤: {filtered_keys}"
        return result

    except Exception as e:
        return {"error": f"变更应用失败: {str(e)}"}
