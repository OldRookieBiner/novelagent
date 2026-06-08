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
    """Create a relationship between two characters.

    Use when the user describes a relationship between characters they've created.
    This directly writes to the knowledge base.

    Args:
        character_a_id: ID of the first character
        character_b_id: ID of the second character
        relation_type: Type of relationship - one of: 信任, 敌对, 感情, 合作, 利用, 陌生
        direction: Direction of the relationship - one of: 双向, 单向A→B, 单向B→A
        current_status: Description of the current relationship status (optional)
        trust_level: Trust level from 0 to 100, default 50
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

    relation = kb.create_relation(data)
    return {
        "action": "created",
        "id": relation.id,
        "relation_type": relation_type,
        "direction": direction,
        "message": f"角色关系「{relation_type}」已创建并写入知识库",
    }
