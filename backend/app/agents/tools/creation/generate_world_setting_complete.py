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
    """生成并保存完整的世界观设定，含分级规则。

    当用户需要一次性创建完整世界观时使用。包括红色（不可违反）、黄色（重要参考）、绿色（可灵活调整）三级规则。

    Args:
            core_concept: 世界观核心概念
            red_rules: JSON 字符串列表，不可违反的规则
            yellow_rules: JSON 字符串列表，可违反但有代价的规则
            green_rules: JSON 字符串列表，装饰性规则
            key_locations: JSON 字符串列表，关键地点及描述
            history: 世界历史/背景故事（可选）
            social_structure: 社会/政治结构描述（可选）
            magic_system: 魔法/力量体系描述（可选）
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
