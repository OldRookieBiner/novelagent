"""角色生成节点 - 从大纲提取角色并写入数据库"""

import re

from app.agents.state import NovelState, STAGE_CHARACTERS
from app.agents.constants import NODE_TEMPERATURES
from app.utils.llm import get_llm_from_state_async


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


def extract_characters_from_outline(state: dict) -> list[dict]:
    """从大纲角色列表提取人物设定（用于 API 端点）

    将 outline_characters 中的简略格式转为带 ID 的完整格式。
    """
    from app.database import SessionLocal
    from app.models.character import Character

    project_id = state.get("project_id")
    if not project_id:
        return []

    db = SessionLocal()
    try:
        # 删除已有角色
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
                motivation=c.get("motivation", ""),
                arc=c.get("arc", ""),
            )
            db.add(char)
            db.flush()
            characters.append({
                "id": char.id,
                "name": name,
                "role": c.get("role", "配角"),
                "personality": c.get("personality", ""),
                "motivation": c.get("motivation", ""),
                "growth_arc": c.get("arc", ""),
            })
        db.commit()
        return characters
    except Exception:
        db.rollback()
        return []
    finally:
        db.close()


async def create_characters_from_outline_node(state: NovelState, config: dict = None) -> NovelState:
    """LangGraph 节点：根据大纲通过独立 LLM 调用生成角色

    签名： (state: NovelState, config: dict) -> NovelState

    读取大纲摘要和世界观背景，使用 character_generation prompt
    调用 LLM 生成角色列表。生成后立即写入数据库。

    Prompt 从 state["_prompts"] 获取（由 WorkflowOrchestrator 预加载）。
    """
    import logging
    from app.database import SessionLocal
    from app.models.character import Character

    logger = logging.getLogger(__name__)

    project_id = state.get("project_id")
    if not project_id:
        logger.warning("character_gen_node: project_id missing from state, cannot generate characters")
        return {**state, "characters": [], "stage": STAGE_CHARACTERS, "waiting_for_confirmation": False, "confirmation_type": None}
    outline_summary = state.get("outline_summary", "")
    world_era = (state.get("outline_world_setting") or {}).get("era", "未指定")

    characters = []

    try:
        # 获取 LLM 服务
        llm = await get_llm_from_state_async(state)

        # 从 state 获取预加载的 prompts（统一使用 get_prompts_from_state）
        from app.agents.nodes.utils import get_prompts_from_state, get_prompt_template, safe_format
        system_template, user_template = get_prompts_from_state(state, "character_generation")
        prompt_template = get_prompt_template(system_template, user_template)
        logger.info(f"character_gen_node: Using prompt from state, template_length={len(prompt_template)}")

        # 获取情节节点和情感曲线
        plot_points = state.get("outline_plot_points", [])
        plot_points_str = "\n".join([
            f"{i+1}. {p.get('event', '')} | 冲突: {p.get('conflict', '')} | 钩子: {p.get('hook', '')}"
            for i, p in enumerate(plot_points)
        ]) if plot_points else "未提供"

        emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

        prompt = safe_format(prompt_template,
            outline_summary=outline_summary,
            world_era=world_era,
            plot_points=plot_points_str,
            emotional_curve=emotional_curve,
        )

        logger.info(f"character_gen_node: Calling LLM with prompt length={len(prompt)}")

        # 调用 LLM 生成人物
        response = await llm.chat([{"role": "user", "content": prompt}], temperature=NODE_TEMPERATURES["character_generation"])

        logger.info(f"character_gen_node: LLM response length={len(response)}, preview={response[:200] if response else 'EMPTY'}")

        # 解析响应
        parsed_characters = parse_character_generation_response(response)

        logger.info(
            f"character_gen_node: LLM generated {len(parsed_characters)} characters"
        )

        if not parsed_characters:
            logger.warning(
                f"character_gen_node: No characters parsed from LLM response. "
                f"Response format may not match expected pattern."
            )
        else:
            # 立即写入数据库
            db = SessionLocal()
            try:
                # 删除已有角色
                db.query(Character).filter(Character.project_id == project_id).delete()

                # 创建新角色
                for char_data in parsed_characters:
                    char = Character(
                        project_id=project_id,
                        name=char_data["name"],
                        role=char_data["role"],
                        personality=char_data["personality"],
                        core_motivation=char_data["core_motivation"],
                        growth_arc=char_data["growth_arc"],
                    )
                    db.add(char)
                    db.flush()  # 获取 ID
                    characters.append({
                        "id": char.id,
                        "name": char.name,
                        "role": char.role,
                        "personality": char.personality,
                        "core_motivation": char.core_motivation,
                        "growth_arc": char.growth_arc,
                    })

                db.commit()
                logger.info(f"character_gen_node: Persisted {len(characters)} characters to DB")
            except Exception as db_error:
                db.rollback()
                logger.error(f"character_gen_node: Failed to persist characters: {db_error}")
            finally:
                db.close()

    except Exception as e:
        logger.warning(
            f"character_gen_node: LLM call failed ({e}), "
            f"character list will be empty"
        )

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
        # 角色生成完成后直接继续执行关系生成，无需等待确认
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }

    return new_state
