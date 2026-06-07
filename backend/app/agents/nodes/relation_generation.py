"""关系生成节点 — 创作智能体版本

基于已生成的角色，AI 生成关系网络并持久化到 DB。
"""

import re
import logging

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHARACTER_GENERATION_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)

# 预编译正则：解析 - 角色A | 角色B | 关系类型 | 信任度 | 描述 | 发展方向
RE_RELATION_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
)


def parse_relations_response(response: str, name_to_id: dict[str, int]) -> list[dict]:
    """从 AI 响应中解析关系列表

    格式：- 角色A名 | 角色B名 | 关系类型 | 信任度 | 描述 | 发展方向

    Args:
        response: AI 原始响应文本
        name_to_id: 角色名→ID映射

    Returns:
        解析后的关系列表
    """
    relations = []
    for line in response.strip().split("\n"):
        match = RE_RELATION_LINE.search(line)
        if not match:
            continue

        name_a = match.group(1).strip()
        name_b = match.group(2).strip()
        rel_type = match.group(3).strip()
        trust_str = match.group(4).strip()
        description = match.group(5).strip()
        direction = match.group(6).strip()

        char_a_id = name_to_id.get(name_a)
        char_b_id = name_to_id.get(name_b)

        if not char_a_id or not char_b_id or char_a_id == char_b_id:
            continue

        # 验证关系类型
        valid_types = ["信任", "敌对", "感情", "合作", "利用", "陌生"]
        if rel_type not in valid_types:
            rel_type = "陌生"

        try:
            trust_level = max(0, min(100, int(trust_str)))
        except ValueError:
            trust_level = 50

        relations.append({
            "character_a_id": char_a_id,
            "character_b_id": char_b_id,
            "relation_type": rel_type,
            "trust_level": trust_level,
            "current_status": description,
            "direction": direction,
        })

    return relations


async def relation_generation_node(state: NovelState) -> NovelState:
    """基于角色生成关系网络

    流程：
    1. 从 DB 读取角色列表
    2. 调用 LLM 生成关系
    3. 解析并持久化到 DB（Relation 模型）
    """
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    characters = kb.get_characters()
    if not characters:
        logger.warning("relation_generation_node: No characters found, skipping")
        return {"phase": Phase.INCUBATION.value}

    # 构建角色信息和 name→id 映射
    chars_text = "\n".join([
        f"- {c.name}（{c.role}）：{c.personality or ''}"
        for c in characters
    ])
    name_to_id = {c.name: c.id for c in characters}

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "relation_generation")

    if user_template:
        prompt_text = safe_format(user_template, characters=chars_text)
    else:
        # 简化 fallback prompt
        prompt_text = (
            f"基于以下角色列表，生成人物关系网络。"
            f"每行格式：- 角色A | 角色B | 关系类型 | 信任度(0-100) | 描述 | 发展方向\n\n"
            f"角色列表：\n{chars_text}"
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.6
    ):
        response += chunk

    # 解析关系
    parsed_relations = parse_relations_response(response, name_to_id)
    logger.info(f"relation_generation_node: Parsed {len(parsed_relations)} relations")

    # 持久化到 DB（使用 KB session 管理器）
    from app.models.character import Relation

    with kb.session() as db:
        for rel_data in parsed_relations:
            try:
                relation = Relation(
                    project_id=project_id,
                    character_a_id=rel_data["character_a_id"],
                    character_b_id=rel_data["character_b_id"],
                    relation_type=rel_data["relation_type"],
                    trust_level=rel_data["trust_level"],
                    current_status=rel_data["current_status"],
                )
                db.add(relation)
            except Exception as e:
                logger.warning(f"relation_generation_node: Failed to persist relation: {e}")

    return {
        "phase": Phase.INCUBATION.value,
    }


# ========== 旧版兼容导出 ==========

# 旧版别名
generate_relations_node = relation_generation_node


def write_relations_to_db(project_id: int, relations: list[dict], db=None) -> list[dict]:
    """将关系列表写入数据库（旧版 API 兼容）

    Args:
        project_id: 项目 ID
        relations: 关系列表 [{character_a_id, character_b_id, relation_type, ...}]
        db: 可选的 DB session（如果不提供则创建独立 session）

    Returns:
        写入后的关系列表（带 id）
    """
    from app.models.character import Relation
    from app.agents.services.knowledge_base import KnowledgeBaseService

    should_close = False
    if db is None:
        kb = KnowledgeBaseService(project_id)
        db_ctx = kb.session()
        db = db_ctx.__enter__()
        should_close = True

    committed = False
    try:
        result = []
        for rel_data in relations:
            relation = Relation(
                project_id=project_id,
                character_a_id=rel_data.get("character_a_id"),
                character_b_id=rel_data.get("character_b_id"),
                relation_type=rel_data.get("relation_type", "陌生"),
                trust_level=rel_data.get("trust_level", 50),
                current_status=rel_data.get("current_status", ""),
            )
            db.add(relation)
            db.flush()
            result.append({
                "id": relation.id,
                "character_a_id": relation.character_a_id,
                "character_b_id": relation.character_b_id,
                "relation_type": relation.relation_type,
            })
        db.commit()
        committed = True
        return result
    except Exception:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        return []
    finally:
        if should_close:
            try:
                db.close()
            except Exception:
                pass
