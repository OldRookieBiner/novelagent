"""角色生成节点 - 从大纲提取角色并写入数据库"""

from app.database import SessionLocal
from app.models.character import Character
from app.agents.state import NovelState, STAGE_CHARACTERS


def _map_role(outline_role: str) -> str:
    """将大纲中的角色标签映射到 Character 模型的 role 枚举值

    大纲角色标签可能多样化，需要做归一化映射。
    """
    role = (outline_role or "").strip()
    if "主角" in role:
        return "主角"
    if "反派" in role or "敌" in role:
        return "核心反派"
    if "重要" in role or "主要男" in role or "主要女" in role:
        return "重要配角"
    return "配角"


def extract_characters_from_outline(state: NovelState) -> list[dict]:
    """从大纲的 outline_characters 提取角色并写入数据库

    删除项目已有角色（避免重复），然后从 state["outline_characters"]
    创建新角色记录。

    Args:
        state: NovelState（需包含 project_id 和 outline_characters）

    Returns:
        已创建的角色列表 [{id, name, role, ...}]
    """
    project_id = state["project_id"]
    outline_characters = state.get("outline_characters", [])

    if not outline_characters:
        return []

    db = SessionLocal()
    try:
        # 删除已有角色（重新生成场景，避免重复）
        db.query(Character).filter(
            Character.project_id == project_id
        ).delete()

        created = []
        for oc in outline_characters:
            char = Character(
                project_id=project_id,
                name=oc.get("name", "未命名") or "未命名",
                role=_map_role(oc.get("role", "")),
                personality=oc.get("personality", ""),
                core_motivation=oc.get("motivation", ""),
                growth_arc=oc.get("arc", ""),
            )
            db.add(char)
            db.flush()  # 获取 id
            created.append({
                "id": char.id,
                "name": char.name,
                "role": char.role,
                "personality": char.personality,
                "core_motivation": char.core_motivation,
                "growth_arc": char.growth_arc,
            })

        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_characters_from_outline_node(state: NovelState) -> NovelState:
    """LangGraph 节点：从大纲提取角色写入数据库

    签名： (state: NovelState) -> NovelState

    同步节点，无 LLM 调用。
    读取 state["outline_characters"]，批量 INSERT 到 characters 表，
    然后更新 state["characters"] 和 state["stage"]。
    """
    characters = extract_characters_from_outline(state)

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }

    return new_state