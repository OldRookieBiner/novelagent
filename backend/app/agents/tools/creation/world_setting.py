"""创建世界观工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_world_setting(
    core_concept: str,
    tiered_settings: str = "{}",
    key_locations: str = "[]",
) -> dict:
    """Create or update the world setting for the novel.

    Use when the user asks to set up or modify the world/setting of their novel.
    If a world setting already exists, it will be updated.

    Args:
        core_concept: The core concept of the world (e.g., "一个以灵力为基石的修仙世界，灵力枯竭导致文明衰败")
        tiered_settings: JSON string with tiered rules: {"red": [...], "yellow": [...], "green": [...]}
                         red = 🔴不可违反的核心规则, yellow = 🟡可突破但有代价, green = 🟢装饰性设定
        key_locations: JSON string list of key locations (e.g., ["天枢城", "灵脉深渊"])
    """
    import json as _json
    kb = _kb()

    try:
        tiered = _json.loads(tiered_settings) if isinstance(tiered_settings, str) else tiered_settings
    except _json.JSONDecodeError:
        tiered = {}

    try:
        locations = _json.loads(key_locations) if isinstance(key_locations, str) else key_locations
    except _json.JSONDecodeError:
        locations = []

    existing = kb.get_world_setting()
    if existing:
        # 合并策略：只更新用户显式传入的字段，避免"仅改 core_concept 却清空 tiered_settings"
        update_data = {"core_concept": core_concept}
        # 只有当 LLM 显式传入了 tiered_settings 时才覆盖
        if tiered_settings != "{}" or tiered:
            update_data["tiered_settings"] = tiered
        else:
            update_data["tiered_settings"] = existing.tiered_settings or {}
        # 只有当 LLM 显式传入了 key_locations 时才覆盖
        if key_locations != "[]" or locations:
            update_data["key_locations"] = locations
        else:
            update_data["key_locations"] = existing.key_locations or []
        updated = kb.update_world_setting(existing.id, update_data)
        return {"action": "updated", "id": updated.id, "core_concept": core_concept[:100]}
    else:
        created = kb.create_world_setting({
            "core_concept": core_concept,
            "tiered_settings": tiered,
            "key_locations": locations,
        })
        return {"action": "created", "id": created.id, "core_concept": core_concept[:100]}
