"""生成完整世界观工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def generate_world_setting_complete(
    core_concept: str,
    red_rules: str = "[]",
    yellow_rules: str = "[]",
    green_rules: str = "[]",
    key_locations: str = "[]",
    history: str = "",
    social_structure: str = "",
    magic_system: str = "",
) -> dict:
    """Generate and save a complete world setting with tiered rules.

    Creates the full world setting in one call, including tiered rules
    (red=unbreakable, yellow=breakable-with-cost, green=decorative),
    key locations, and optional lore sections.

    Args:
        core_concept: Core concept of the world (1-2 sentences explaining how this world works)
        red_rules: JSON string list of unbreakable rules (e.g., ["灵力来源于血脉，不可后天获得"])
        yellow_rules: JSON string list of breakable-with-cost rules (e.g., ["可以跨越位面，但会消耗寿命"])
        green_rules: JSON string list of decorative rules (e.g., ["修仙者有独特的灵纹"])
        key_locations: JSON string list of key locations with descriptions
                       (e.g., [{"name": "天枢城", "desc": "修仙界最大城市，灵脉交汇处", "plot_role": "主角起点"}])
        history: World history / backstory (optional)
        social_structure: Social/political structure description (optional)
        magic_system: Magic/power system description (optional)
    """
    import json as _json

    try:
        red = _json.loads(red_rules) if isinstance(red_rules, str) else red_rules
    except _json.JSONDecodeError:
        red = []

    try:
        yellow = _json.loads(yellow_rules) if isinstance(yellow_rules, str) else yellow_rules
    except _json.JSONDecodeError:
        yellow = []

    try:
        green = _json.loads(green_rules) if isinstance(green_rules, str) else green_rules
    except _json.JSONDecodeError:
        green = []

    try:
        locations = _json.loads(key_locations) if isinstance(key_locations, str) else key_locations
    except _json.JSONDecodeError:
        locations = []

    kb = _kb()

    tiered = {}
    if red:
        tiered["red"] = red
    if yellow:
        tiered["yellow"] = yellow
    if green:
        tiered["green"] = green

    data = {
        "core_concept": core_concept,
        "tiered_settings": tiered,
        "key_locations": locations,
    }
    if history:
        data["history"] = history
    if social_structure:
        data["social_structure"] = social_structure
    if magic_system:
        data["magic_system"] = magic_system

    existing = kb.get_world_setting()
    if existing:
        updated = kb.update_world_setting(existing.id, data)
        return {
            "action": "updated",
            "id": updated.id,
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已更新（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }
    else:
        created = kb.create_world_setting(data)
        return {
            "action": "created",
            "id": created.id,
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已创建（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }
