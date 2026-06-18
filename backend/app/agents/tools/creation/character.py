"""创建/更新角色工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff


@tool
async def create_character(
    character_id: int = 0,
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
    """创建新角色或更新已有角色. 提供 character_id 时为更新模式.

    - character_id=0(默认): 创建新角色(name 和 role 必填)
    - character_id>0: 更新指定 ID 的角色. None 表示不修改, 空字符串 "" 表示清空字段

    Args:
        character_id: 角色 ID(非零时更新已有角色)
        name: 角色名
        role: 角色定位 - 可选值: 主角, 核心反派, 重要配角, 配角
        personality: 性格特征描述
        catchphrase: 口头禅或典型语言风格
        habit_action: 习惯动作或姿态
        deep_fear: 深层恐惧
        core_motivation: 驱动角色行动的核心动机
        growth_arc: 成长弧线/角色发展轨迹
        appearance: 外貌描写
        backstory: 背景故事
        signature_item: 标志性物品或配饰
    """
    kb = _kb()

    if character_id:
        # --- 更新路径 ---
        before = kb.characters.get_character(character_id)
        if not before:
            return {"error": f"角色 ID {character_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "name", "role", "personality", "catchphrase", "habit_action",
            "deep_fear", "core_motivation", "growth_arc", "appearance",
            "backstory", "signature_item",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "character_id": character_id}

        updated = kb.characters.update_character(character_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "character_id": character_id,
            "name": updated.get("name", before.get("name")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"角色「{updated.get('name')}」已更新 {len(changes)} 个字段",
        }
    else:
        # --- 创建路径 ---
        if not name or not role:
            return {"error": "创建角色时 name 和 role 为必填字段"}

        data = {"name": name, "role": role}
        for key, val in [
            ("personality", personality), ("catchphrase", catchphrase),
            ("habit_action", habit_action), ("deep_fear", deep_fear),
            ("core_motivation", core_motivation), ("growth_arc", growth_arc),
            ("appearance", appearance), ("backstory", backstory),
            ("signature_item", signature_item),
        ]:
            if val:
                data[key] = val
        char = kb.characters.create_character(data)
        return {
            "action": "created",
            "id": char["id"],
            "name": char["name"],
            "role": char["role"],
            "message": f"角色「{name}」已创建并写入知识库",
        }
