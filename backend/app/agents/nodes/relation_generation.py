"""关系生成节点 - AI 基于角色生成关系网络"""

import re
from sqlalchemy.orm import Session

from app.models.character import Relation
from app.agents.state import NovelState, STAGE_RELATIONS
from app.utils.llm import get_llm_from_state_async
from app.database import SessionLocal


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


async def generate_relations_node(state: NovelState, config: dict = None) -> NovelState:
    """LangGraph 节点：从角色生成关系网络

    签名：(state: NovelState, config: dict) -> NovelState

    从数据库读取已持久化的角色（带 id），生成关系后立即写入数据库。

    Args:
        state: 当前工作流状态（需包含 project_id）
        config: LangGraph 配置字典（可选）

    Returns:
        更新后的 NovelState（包含 relations 和 stage）
    """
    import logging
    from app.database import SessionLocal
    from app.models.character import Character, Relation

    logger_rn = logging.getLogger(__name__)
    project_id = state["project_id"]

    # 从数据库读取已持久化的角色（带 id）
    db = SessionLocal()
    try:
        db_characters = db.query(Character).filter(
            Character.project_id == project_id
        ).order_by(Character.id).all()

        characters_with_id = [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "personality": c.personality or "",
                "core_motivation": c.core_motivation or "",
            }
            for c in db_characters
        ]
    finally:
        db.close()

    if len(characters_with_id) < 2:
        logger_rn.info(
            f"relation_gen_node: only {len(characters_with_id)} characters for project {project_id}, skipping"
        )
        return {
            **state,
            "stage": STAGE_RELATIONS,
            "relations": [],
            # 规划阶段完成，等待用户确认
            "waiting_for_confirmation": True,
            "confirmation_type": "relations",
        }

    # 构建角色列表文本
    characters_lines = []
    for c in characters_with_id:
        characters_lines.append(
            f"- {c['name']}（{c.get('role', '配角')}）：{c.get('personality', '')}，{c.get('core_motivation', '')}"
        )

    characters_text = "\n".join(characters_lines)

    # 获取世界观时代背景
    world_setting = state.get("outline_world_setting", {}) or {}
    world_era = world_setting.get("era", "未指定")

    # 获取大纲概述
    outline_summary = state.get("outline_summary", "未提供")

    # 获取情节节点和情感曲线
    plot_points = state.get("outline_plot_points", [])
    plot_points_str = "\n".join([
        f"{i+1}. {p.get('event', '')} | 冲突: {p.get('conflict', '')}"
        for i, p in enumerate(plot_points)
    ]) if plot_points else "未提供"

    emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

    # 从 state 获取预加载的 prompts
    prompts = state.get("_prompts", {})
    if prompts and "relation_generation" in prompts:
        prompt = prompts["relation_generation"].format(
            characters_text=characters_text,
            world_era=world_era,
            outline_summary=outline_summary,
            plot_points=plot_points_str,
            emotional_curve=emotional_curve,
        )
        logger_rn.info(f"relation_gen_node: Using prompt from state, length={len(prompt)}")
    else:
        # 回退：使用默认 prompt
        from app.agents.prompts import DEFAULT_PROMPTS
        default_prompt = DEFAULT_PROMPTS.get("relation_generation", "")
        if default_prompt:
            prompt = default_prompt.format(
                characters_text=characters_text,
                world_era=world_era,
                outline_summary=outline_summary,
                plot_points=plot_points_str,
                emotional_curve=emotional_curve,
            )
            logger_rn.info(f"relation_gen_node: Using DEFAULT_PROMPTS fallback, length={len(prompt)}")
        else:
            prompt = f"基于以下角色生成关系网络：\n{characters_text}\n世界观：{world_era}\n大纲：{outline_summary}"
            logger_rn.warning("relation_gen_node: No relation_generation prompt found, using minimal fallback")

    # 调用 LLM
    llm = await get_llm_from_state_async(state)
    response = await llm.chat([{"role": "user", "content": prompt}])

    logger_rn.info(f"relation_gen_node: LLM response length={len(response)}, preview={response[:300] if response else 'EMPTY'}")

    # 解析响应
    relations_data = parse_relations_response(response, characters_with_id)

    logger_rn.info(
        f"relation_gen_node: parsed {len(relations_data)} relations for project {project_id}"
    )

    # 立即写入数据库
    if relations_data:
        db = SessionLocal()
        try:
            # 删除旧关系
            db.query(Relation).filter(Relation.project_id == project_id).delete()

            # 创建新关系
            for rel_data in relations_data:
                rel = Relation(
                    project_id=project_id,
                    character_a_id=rel_data["character_a_id"],
                    character_b_id=rel_data["character_b_id"],
                    relation_type=rel_data["relation_type"],
                    trust_level=rel_data["trust_level"],
                    current_status=rel_data["current_status"],
                    direction=rel_data["direction"],
                )
                db.add(rel)

            db.commit()
            logger_rn.info(f"relation_gen_node: Persisted {len(relations_data)} relations to DB")
        except Exception as db_error:
            db.rollback()
            logger_rn.error(f"relation_gen_node: Failed to persist relations: {db_error}")
        finally:
            db.close()

    return {
        **state,
        "relations": relations_data,
        "stage": STAGE_RELATIONS,
        # 规划阶段完成，等待用户确认
        "waiting_for_confirmation": True,
        "confirmation_type": "relations",
    }
