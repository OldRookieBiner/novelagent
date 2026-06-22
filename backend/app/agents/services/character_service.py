# backend/app/agents/services/character_service.py
"""人物设定服务

为 agent_tools.py 提取共享的业务逻辑。
所有函数都是 async def，保持接口一致性。
写操作返回 changes 列表用于审计追踪。
"""

from sqlalchemy.orm import Session
from app.models.character import Character


async def read_characters(db: Session, project_id: int) -> list[dict]:
    """读取项目所有人物设定"""
    characters = (
        db.query(Character)
        .filter(Character.project_id == project_id)
        .order_by(Character.id)
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "personality": c.personality,
            "catchphrase": c.catchphrase,
            "habit_action": c.habit_action,
            "deep_fear": c.deep_fear,
            "core_motivation": c.core_motivation,
            "growth_arc": c.growth_arc,
            "appearance": c.appearance,
            "backstory": c.backstory,
            "signature_item": c.signature_item,
        }
        for c in characters
    ]


async def create_character(db: Session, project_id: int, data: dict) -> dict:
    """创建新人物，返回创建结果"""
    name = data.get("name", "").strip()
    if not name:
        return {"error": "人物名不能为空"}

    character = Character(
        project_id=project_id,
        name=name,
        role=data.get("role", "配角"),
        personality=data.get("personality"),
        catchphrase=data.get("catchphrase"),
        habit_action=data.get("habit_action"),
        deep_fear=data.get("deep_fear"),
        core_motivation=data.get("core_motivation"),
        growth_arc=data.get("growth_arc"),
        appearance=data.get("appearance"),
        backstory=data.get("backstory"),
        signature_item=data.get("signature_item"),
        knowledge_boundary=data.get("knowledge_boundary"),
        speech_style=data.get("speech_style"),
        speech_samples=data.get("speech_samples"),
    )

    try:
        db.add(character)
        db.commit()
        db.refresh(character)
    except Exception:
        db.rollback()
        return {"error": "创建人物失败"}

    return {
        "success": True,
        "message": f"人物「{name}」已创建",
        "character": {
            "id": character.id,
            "name": character.name,
            "role": character.role,
        },
    }


async def update_character(db: Session, project_id: int, character_id: int, updates: dict) -> dict:
    """更新人物设定，返回 changes 审计列表"""
    character = (
        db.query(Character)
        .filter(
            Character.project_id == project_id,
            Character.id == character_id,
        )
        .first()
    )
    if not character:
        return {"error": "人物不存在"}

    changes = []
    field_labels = {
        "name": "姓名",
        "role": "角色",
        "personality": "性格",
        "catchphrase": "口头禅",
        "habit_action": "习惯动作",
        "deep_fear": "深层恐惧",
        "core_motivation": "核心动机",
        "growth_arc": "成长弧线",
        "appearance": "外貌",
        "backstory": "背景故事",
        "signature_item": "标志性物品",
        "knowledge_boundary": "知识边界",
        "speech_style": "语言风格",
        "speech_samples": "对话样本",
    }

    for key, value in updates.items():
        if hasattr(character, key):
            old_val = getattr(character, key)
            if old_val != value:
                setattr(character, key, value)
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
