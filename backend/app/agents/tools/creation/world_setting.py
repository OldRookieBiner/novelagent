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
        core_concept: The core concept of the world
        tiered_settings: JSON string with tiered rules: {"red": [...], "yellow": [...], "green": [...]}
        key_locations: JSON string list of key locations
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

    existing = kb.world_setting.get()
    if existing:
        # 合并策略：只更新用户显式传入的字段
        update_data = {"core_concept": core_concept}
        if tiered_settings != "{}" or tiered:
            update_data["tiered_settings"] = tiered
        else:
            update_data["tiered_settings"] = existing.get("tiered_settings") or {}
        if key_locations != "[]" or locations:
            update_data["key_locations"] = locations
        else:
            update_data["key_locations"] = existing.get("key_locations") or []
        updated = kb.world_setting.update_by_id(existing["id"], update_data)
        return {"action": "updated", "id": updated["id"], "core_concept": core_concept[:100]}
    else:
        created = kb.world_setting.create({
            "core_concept": core_concept,
            "tiered_settings": tiered,
            "key_locations": locations,
        })
        return {"action": "created", "id": created["id"], "core_concept": core_concept[:100]}
