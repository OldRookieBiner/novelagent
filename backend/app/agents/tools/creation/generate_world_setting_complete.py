"""生成完整世界观工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


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

    Creates the full world setting in one call, including tiered rules,
    key locations, and optional lore sections.

    Args:
        core_concept: Core concept of the world
        red_rules: JSON string list of unbreakable rules
        yellow_rules: JSON string list of breakable-with-cost rules
        green_rules: JSON string list of decorative rules
        key_locations: JSON string list of key locations with descriptions
        history: World history / backstory (optional)
        social_structure: Social/political structure description (optional)
        magic_system: Magic/power system description (optional)
    """

    red, red_warn = parse_json_param(red_rules, [], "red_rules")

    yellow, yellow_warn = parse_json_param(yellow_rules, [], "yellow_rules")

    green, green_warn = parse_json_param(green_rules, [], "green_rules")

    locations, locations_warn = parse_json_param(key_locations, [], "key_locations")

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

    existing = kb.world_setting.get()
    if existing:
        updated = kb.world_setting.update_by_id(existing["id"], data)
        return {
            "action": "updated",
            "id": updated["id"],
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已更新（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }
    else:
        created = kb.world_setting.create(data)
        return {
            "action": "created",
            "id": created["id"],
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已创建（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }
