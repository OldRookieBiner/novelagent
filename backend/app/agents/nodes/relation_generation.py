"""关系生成节点 - AI 基于角色生成关系网络"""

import re
from sqlalchemy.orm import Session

from app.models.character import Relation
from app.agents.state import NovelState, STAGE_RELATIONS
from app.services.prompt_loader import get_system_prompt
from app.utils.llm import get_llm_from_state_async


# 预编译正则：解析 - 角色A | 角色B | 关系类型 | 信任度 | 描述 | 发展方向
RE_RELATION_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
)


def parse_relations_response(response: str, characters: list[dict]) -> list[dict]:
    """从 AI 响应中解析关系列表

    格式：- 角色A名 | 角色B名 | 关系类型 | 信任度 | 描述 | 发展方向

    Args:
        response: AI 原始响应文本
        characters: 已创建的角色列表 [{id, name, ...}]

    Returns:
        解析后的关系列表 [{character_a_id, character_b_id, relation_type, trust_level, current_status, direction}]
    """
    name_to_id = {c["name"]: c["id"] for c in characters}
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
        # 忽略 group(6) 发展方向字段（relation 表无对应列）

        # 根据角色名查找 id
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

        relations.append(
            {
                "character_a_id": char_a_id,
                "character_b_id": char_b_id,
                "relation_type": rel_type,
                "trust_level": trust_level,
                "current_status": description,
                "direction": "双向",
            }
        )

    return relations


def write_relations_to_db(
    project_id: int, relations_data: list[dict], db: Session
) -> list[dict]:
    """将解析好的关系列表写入数据库

    Args:
        project_id: 项目 ID
        relations_data: parse_relations_response 的输出
        db: 数据库会话（必须由调用方提供）

    Returns:
        已创建的关系列表
    """
    if not relations_data:
        return []

    # 删除已有关系
    db.query(Relation).filter(Relation.project_id == project_id).delete()

    created = []
    for r in relations_data:
        rel = Relation(
            project_id=project_id,
            character_a_id=r["character_a_id"],
            character_b_id=r["character_b_id"],
            relation_type=r["relation_type"],
            trust_level=r["trust_level"],
            current_status=r["current_status"],
            direction=r["direction"],
        )
        db.add(rel)
        db.flush()
        created.append(
            {
                "id": rel.id,
                "character_a_id": rel.character_a_id,
                "character_b_id": rel.character_b_id,
                "relation_type": rel.relation_type,
                "trust_level": rel.trust_level,
                "current_status": rel.current_status,
                "direction": rel.direction,
            }
        )

    return created


async def generate_relations_node(state: NovelState) -> NovelState:
    """LangGraph 节点：从角色生成关系网络

    签名：(state: NovelState) -> NovelState

    此节点仅负责调用 LLM 并解析关系数据，不写入数据库。
    DB 写入由 workflow API 的 astream_events 持久化流程统一处理。

    Args:
        state: 当前工作流状态（需包含 characters、project_id）

    Returns:
        更新后的 NovelState（包含 relations 和 stage）
    """
    import logging
    from app.database import SessionLocal

    characters = state.get("characters", [])
    if len(characters) < 2:
        # 少于两个角色则跳过关系生成
        return {**state, "stage": STAGE_RELATIONS, "relations": []}

    # 构建角色列表文本
    characters_lines = []
    for c in characters:
        characters_lines.append(
            f"- {c['name']}（{c.get('role', '配角')}）：{c.get('personality', '')}，{c.get('core_motivation', '')}"
        )

    characters_text = "\n".join(characters_lines)

    # 获取世界观时代背景
    world_setting = state.get("outline_world_setting", {}) or {}
    world_era = world_setting.get("era", "未指定")

    # 获取大纲概述
    outline_summary = state.get("outline_summary", "未提供")

    # 加载 Prompt（需要独立的 DB 会话，因为 LangGraph 节点中没有共享 session）
    db = SessionLocal()
    try:
        prompt = get_system_prompt(db, "relation_generation").format(
            characters_text=characters_text,
            world_era=world_era,
            outline_summary=outline_summary,
        )
    finally:
        db.close()

    # 调用 LLM
    llm = await get_llm_from_state_async(state)
    response = await llm.chat([{"role": "user", "content": prompt}])

    # 解析响应（仅提取数据，不写 DB）
    relations_data = parse_relations_response(response, characters)

    logging.getLogger(__name__).info(
        f"relation_gen_node: parsed {len(relations_data)} relations"
    )

    new_state: NovelState = {
        **state,
        "relations": relations_data,
        "stage": STAGE_RELATIONS,
    }

    return new_state
