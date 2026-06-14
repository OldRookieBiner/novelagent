"""更新角色属性工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_character(
    character_id: int,
    name: str | None = None,
    role: str | None = None,
    personality: str | None = None,
    catchphrase: str | None = None,
    habit_action: str | None = None,
    deep_fear: str | None = None,
    core_motivation: str | None = None,
    growth_arc: str | None = None,
    appearance: str | None = None,
    backstory: str | None = None,
    signature_item: str | None = None,
) -> dict:
    """更新已有角色的属性。None 表示不修改，传入具体值则更新。要清空字段需传入空字符串 ""。

    Args:
        character_id: 角色 ID
        name: 角色名
        role: 角色定位
        personality: 性格特征
        catchphrase: 口头禅
        habit_action: 习惯动作
        deep_fear: 深层恐惧
        core_motivation: 核心动机
        growth_arc: 成长弧线
        appearance: 外貌描写
        backstory: 背景故事
        signature_item: 标志性物品
    """
    kb = _kb()

    # 获取当前值用于对比
    before = {}
    chars = kb.characters.list_characters()
    for c in chars:
        if c["id"] == character_id:
            before = c
            break

    if not before:
        return {"error": f"角色 ID {character_id} 不存在"}

    # 构建更新数据（只包含非 None 的字段）
    update_data = {}
    for field in ("name", "role", "personality", "catchphrase", "habit_action",
                  "deep_fear", "core_motivation", "growth_arc", "appearance",
                  "backstory", "signature_item"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "character_id": character_id}

    updated = kb.characters.update_character(character_id, update_data)

    # 构建变更对比
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}

    return {
        "character_id": character_id,
        "name": updated.get("name", before.get("name")),
        "updated_fields": list(changes.keys()),
        "changes": changes,
        "message": f"角色「{updated.get('name', before.get('name'))}」已更新 {len(changes)} 个字段",
    }
