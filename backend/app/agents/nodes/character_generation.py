"""角色生成节点 - 从大纲提取角色并写入数据库"""

import re
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


# 预编译正则：解析管道分隔的人物格式
# 格式：- 角色定位 | 姓名 | 性格 | 核心动机 | 成长弧线
_RE_CHARACTER_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
)


def parse_character_generation_response(response: str) -> list[dict]:
    """解析 LLM 返回的管道分隔角色格式

    格式：- 角色定位 | 姓名 | 性格 | 核心动机 | 成长弧线

    Args:
        response: LLM 返回的原始文本

    Returns:
        角色列表 [{"name": ..., "role": ..., "personality": ..., ...}, ...]
    """
    characters = []
    for line in response.splitlines():
        m = _RE_CHARACTER_LINE.search(line)
        if not m:
            continue
        role_label, name, personality, motivation, arc = m.groups()
        name = (name or "").strip()
        if not name:
            continue
        characters.append(
            {
                "name": name,
                "role": _map_role(role_label),
                "personality": (personality or "").strip()[:500],
                "core_motivation": (motivation or "").strip()[:500],
                "growth_arc": (arc or "").strip()[:500],
            }
        )
    return characters


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
    """LangGraph 节点：根据大纲通过独立 LLM 调用生成角色

    签名： (state: NovelState) -> NovelState

    读取大纲摘要和世界观背景，使用 character_generation prompt
    调用 LLM 生成角色列表。不再依赖 state["outline_characters"]。

    注意：数据库 session 由 workflow API 中 astream_events 的 persist 逻辑管理，
    此节点仅负责生成数据，不自行创建/提交 session。
    """
    import logging
    from app.database import SessionLocal
    from app.services.prompt_loader import get_system_prompt
    from app.utils.llm import get_llm_from_state_async

    logger = logging.getLogger(__name__)

    outline_summary = state.get("outline_summary", "")
    world_era = (state.get("outline_world_setting") or {}).get("era", "未指定")

    characters = []

    try:
        # 获取 LLM 服务
        llm = await get_llm_from_state_async(state)

        # 获取人物生成 prompt
        db = SessionLocal()
        try:
            prompt = get_system_prompt(db, "character_generation").format(
                outline_summary=outline_summary,
                world_era=world_era,
            )
        finally:
            db.close()

        # 调用 LLM 生成人物
        response = await llm.chat([{"role": "user", "content": prompt}])

        # 解析响应
        characters = parse_character_generation_response(response)

        logger.info(
            f"character_gen_node: LLM generated {len(characters)} characters"
        )

    except Exception as e:
        logger.warning(
            f"character_gen_node: LLM call failed ({e}), "
            f"character list will be empty"
        )

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }

    return new_state
