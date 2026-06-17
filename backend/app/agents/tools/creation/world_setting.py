"""创建世界观工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_world_setting(
    core_concept: str,
    tiered_settings: str = "{}",
    key_locations: str = "[]",
) -> dict:
    """创建或更新小说的世界观设定。

    当用户需要建立故事世界的规则和设定时使用。支持分级规则（红色/黄色/绿色）和关键地点。

    与 generate_world_setting_complete 的区别：
    - create_world_setting：适合逐字段更新，参数少，每次只更新指定字段
    - generate_world_setting_complete：适合一次性创建完整世界观，参数更多（含历史/社会/魔法体系）
    如果已有世界观，本工具会合并更新而非覆盖。

    Args:
        core_concept: 世界观核心概念
        tiered_settings: JSON 字符串，分级设定（含 red/yellow/green 三级）
        key_locations: JSON 字符串列表，关键地点
    """
    kb = _kb()

    tiered, tiered_warn = parse_json_param(tiered_settings, {}, "tiered_settings")

    locations, locations_warn = parse_json_param(key_locations, [], "key_locations")

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
