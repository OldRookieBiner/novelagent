# backend/app/agents/services/relation_service.py
"""人物关系服务

为 agent_tools.py 提取共享的业务逻辑。
所有函数都是 async def，保持接口一致性。
read_relations 关联查询 Character 表以获取角色名称。
"""

from sqlalchemy.orm import Session
from app.models.character import Relation, Character


async def read_relations(db: Session, project_id: int) -> list[dict]:
    """读取项目所有人物关系，关联查询角色名称"""
    relations = (
        db.query(Relation)
        .filter(Relation.project_id == project_id)
        .order_by(Relation.id)
        .all()
    )

    # 批量获取所有相关角色名称
    character_ids = set()
    for r in relations:
        character_ids.add(r.character_a_id)
        character_ids.add(r.character_b_id)

    characters = (
        db.query(Character)
        .filter(Character.id.in_(character_ids))
        .all()
    )
    name_map = {c.id: c.name for c in characters}

    return [
        {
            "id": r.id,
            "character_a_id": r.character_a_id,
            "character_a_name": name_map.get(r.character_a_id, "未知"),
            "character_b_id": r.character_b_id,
            "character_b_name": name_map.get(r.character_b_id, "未知"),
            "relation_type": r.relation_type,
            "direction": r.direction,
            "current_status": r.current_status,
            "trust_level": r.trust_level,
        }
        for r in relations
    ]


async def update_relation(db: Session, project_id: int, relation_id: int, updates: dict) -> dict:
    """更新人物关系，返回 changes 审计列表"""
    relation = (
        db.query(Relation)
        .filter(
            Relation.project_id == project_id,
            Relation.id == relation_id,
        )
        .first()
    )
    if not relation:
        return {"error": "关系不存在"}

    changes = []
    field_labels = {
        "relation_type": "关系类型",
        "direction": "方向",
        "current_status": "当前状态",
        "trust_level": "信任度",
    }

    for key, value in updates.items():
        if hasattr(relation, key):
            old_val = getattr(relation, key)
            if old_val != value:
                setattr(relation, key, value)
                label = field_labels.get(key, key)
                if isinstance(value, (list, dict)):
                    changes.append(f"{label}已更新")
                else:
                    old_str = str(old_val)[:50] if old_val else "空"
                    new_str = str(value)[:50] if value else "空"
                    changes.append(f"{label}: {old_str} → {new_str}")

    if changes:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return {"error": "保存失败"}

    return {"success": True, "changes": changes}
