"""角色生成节点 - 从大纲提取角色并写入数据库"""

import asyncio
from sqlalchemy.orm import Session

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


def extract_characters_from_outline(state: NovelState, db: Session) -> list[dict]:
    """从大纲的 outline_characters 提取角色并写入数据库

    删除项目已有角色（避免重复），然后从 state["outline_characters"]
    创建新角色记录。

    Args:
        state: NovelState（需包含 project_id 和 outline_characters）
        db: 数据库会话（由调用方管理生命周期）

    Returns:
        已创建的角色列表 [{id, name, role, ...}]
    """
    project_id = state["project_id"]
    outline_characters = state.get("outline_characters", [])

    if not outline_characters:
        return []

    # 删除已有角色（重新生成场景，避免重复）
    db.query(Character).filter(Character.project_id == project_id).delete()

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
        created.append(
            {
                "id": char.id,
                "name": char.name,
                "role": char.role,
                "personality": char.personality,
                "core_motivation": char.core_motivation,
                "growth_arc": char.growth_arc,
            }
        )

    return created


async def create_characters_from_outline_node(state: NovelState) -> NovelState:
    """LangGraph 节点：从大纲提取角色写入数据库

    签名： (state: NovelState) -> NovelState

    异步节点，DB 操作放入线程池避免阻塞 event loop。
    读取 state["outline_characters"]，批量 INSERT 到 characters 表，
    然后更新 state["characters"] 和 state["stage"]。

    注意：数据库 session 由 workflow API 中 astream_events 的 persist 逻辑管理，
    此节点仅负责提取数据，不自行创建/提交 session。
    """
    # 仅从 state 提取角色数据（不写 DB），DB 写入由 workflow API 的 persist 流程统一处理
    outline_characters = state.get("outline_characters", [])
    characters = []
    for oc in outline_characters:
        characters.append(
            {
                "name": oc.get("name", "未命名") or "未命名",
                "role": _map_role(oc.get("role", "")),
                "personality": oc.get("personality", ""),
                "core_motivation": oc.get("motivation", ""),
                "growth_arc": oc.get("arc", ""),
            }
        )

    import logging
    logging.getLogger(__name__).info(
        f"character_gen_node: outline_chars={len(outline_characters)}, extracted={len(characters)}"
    )

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }

    return new_state
