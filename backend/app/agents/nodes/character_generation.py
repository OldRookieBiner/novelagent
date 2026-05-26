"""角色生成节点 — 创作智能体版本

基于大纲生成角色，解析并持久化到 DB。
"""

import re
import logging
from typing import Optional

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHARACTER_GENERATION_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


def _map_role(outline_role: str) -> str:
    """将大纲中的角色标签映射到 Character 模型的 role 枚举值"""
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
        characters.append({
            "name": name,
            "role": _map_role(role_label),
            "personality": (personality or "").strip()[:500],
            "core_motivation": (motivation or "").strip()[:500],
            "growth_arc": (arc or "").strip()[:500],
        })
    return characters


async def character_generation_node(state: NovelState) -> NovelState:
    """基于大纲生成角色

    流程：
    1. 从 DB 读取大纲摘要
    2. 调用 LLM 生成角色列表
    3. 解析并持久化到 DB（Character 模型）
    """
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    # 从 DB 读取大纲
    outline = kb.get_outline()
    outline_text = outline.summary if outline else ""

    # 从大纲中提取世界观
    world_era = ""
    if outline and outline.world_setting:
        world_era = outline.world_setting.get("era", "未指定")

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "character_generation")

    if user_template:
        prompt_text = safe_format(user_template,
            outline_summary=outline_text,
            world_era=world_era,
        )
    else:
        prompt_text = safe_format(CHARACTER_GENERATION_PROMPT,
            outline_summary=outline_text,
            world_era=world_era,
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.7
    ):
        response += chunk

    # 解析角色
    parsed_characters = parse_character_generation_response(response)
    logger.info(f"character_generation_node: Parsed {len(parsed_characters)} characters")

    # 持久化到 DB
    for char_data in parsed_characters:
        kb.create_character(char_data)

    return {
        **state,
        "phase": Phase.INCUBATION.value,
    }


# ========== 旧版兼容导出 ==========

# 旧版别名
create_characters_from_outline_node = character_generation_node


def extract_characters_from_outline(state: dict) -> list[dict]:
    """从大纲角色列表提取人物设定（旧版 API 兼容）

    将 outline_characters 中的简略格式转为带 ID 的完整格式。
    """
    from app.database import SessionLocal
    from app.models.character import Character

    project_id = state.get("project_id")
    if not project_id:
        return []

    db = SessionLocal()
    committed = False
    try:
        db.query(Character).filter(Character.project_id == project_id).delete()
        db.flush()

        outline_characters = state.get("outline_characters", [])
        characters = []
        for i, c in enumerate(outline_characters):
            name = c.get("name", f"角色{i+1}")
            char = Character(
                project_id=project_id,
                name=name,
                role=c.get("role", "配角"),
                personality=c.get("personality", ""),
                core_motivation=c.get("motivation", ""),
                growth_arc=c.get("arc", ""),
            )
            db.add(char)
            db.flush()
            characters.append({
                "id": char.id,
                "name": name,
                "role": c.get("role", "配角"),
                "personality": c.get("personality", ""),
                "core_motivation": c.get("motivation", ""),
                "growth_arc": c.get("arc", ""),
            })
        db.commit()
        committed = True
        return characters
    except Exception:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass
