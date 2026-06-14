"""创建关系工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_relation(
    character_a_id: int,
    character_b_id: int,
    relation_type: str,
    direction: str = "双向",
    current_status: str = "",
    trust_level: int = 50,
) -> dict:
    """创建两个角色之间的关系。

    当用户需要定义角色之间的关系时使用。关系会随着情节推进而演变。

    Args:
            character_a_id: 第一个角色的 ID
            character_b_id: 第二个角色的 ID
            relation_type: Type of relationship - one of: 信任, 敌对, 感情, 合作, 利用, 陌生
            direction: Direction of the relationship - one of: 双向, 单向A→B, 单向B→A
            current_status: 当前关系状态描述（可选）
            trust_level: 信任等级 0-100，默认 50
    """
    kb = _kb()

    data = {
        "character_a_id": character_a_id,
        "character_b_id": character_b_id,
        "relation_type": relation_type,
        "direction": direction,
        "trust_level": trust_level,
    }
    if current_status:
        data["current_status"] = current_status

    relation = kb.characters.create_relation(data)
    return {
        "action": "created",
        "id": relation["id"],
        "relation_type": relation_type,
        "direction": direction,
        "message": f"角色关系「{relation_type}」已创建并写入知识库",
    }
