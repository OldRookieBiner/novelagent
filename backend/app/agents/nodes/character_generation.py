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


def parse_character_generation_response(response: str) -> list[dict]:
    """解析 LLM 返回的角色格式

    支持 Markdown 格式（CHARACTER_GENERATION_PROMPT 默认输出）：
    ## 角色名
    - **角色定位**：主角
    - **核心动机**：xxx
    - **人物弧**：从xxx到xxx
    - **说话风格**：xxx
    """
    characters = []
    
    # 移除 ** 粗体标记（避免干扰正则）
    response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)

    # 匹配从 ## 或 ### 开始到下一个 ## 或 ### 或文档结尾
    section_pattern = r'(?:^|\n)(#{1,3})\s*([^\n#]+?)(?:\n)(.*?)(?=(?:^#{1,3})|\Z)'
    
    for match in re.finditer(section_pattern, response, re.DOTALL | re.MULTILINE):
        name = match.group(2).strip()
        if not name:
            continue
        
        section = match.group(3)
        
        # 提取角色定位
        role = "配角"
        role_match = re.search(r'角色定位[：:]\s*([^\n]+)', section)
        if role_match:
            role = _map_role(role_match.group(1))
        
        # 提取核心动机
        motivation = ""
        mot_match = re.search(r'核心动机[：:]\s*([^\n]+)', section)
        if mot_match:
            motivation = mot_match.group(1).strip()[:500]
        
        # 提取人物弧
        arc = ""
        arc_match = re.search(r'人物弧[：:]\s*([^\n]+)', section)
        if arc_match:
            arc = arc_match.group(1).strip()[:500]
        
        # 提取核心冲突（如果没有动机，用冲突替代）
        conflict = ""
        conflict_match = re.search(r'核心冲突[：:]\s*([^\n]+)', section)
        if conflict_match:
            conflict = conflict_match.group(1).strip()[:500]
        
        # 提取说话风格作为性格
        personality = ""
        pers_match = re.search(r'(?:说话风格|性格)[：:]\s*([^\n]+)', section)
        if pers_match:
            personality = pers_match.group(1).strip()[:500]
        
        # 如果没有找到动机但有冲突，将其作为动机
        if not motivation and conflict:
            motivation = conflict
        
        characters.append({
            "name": name,
            "role": role,
            "personality": personality,
            "core_motivation": motivation,
            "growth_arc": arc,
        })

    # 如果 Markdown 解析失败，���试管道分隔格式
    if not characters:
        pipe_pattern = re.compile(
            r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)"
        )
        for line in response.splitlines():
            m = pipe_pattern.search(line)
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

    logger.info(f"character_generation_node: Parsed {len(characters)} characters from response")
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
        "phase": Phase.INCUBATION.value,
    }


# ========== 旧版兼容导出 ==========

# 旧版别名
create_characters_from_outline_node = character_generation_node


def extract_characters_from_outline(state: dict) -> list[dict]:
    """从大纲角色列表提取人物设定（旧版 API 兼容）

    将 outline_characters 中的简略格式转为带 ID 的完整格式。
    """
    from app.models.character import Character
    from app.agents.services.knowledge_base import KnowledgeBaseService

    project_id = state.get("project_id")
    if not project_id:
        return []

    kb = KnowledgeBaseService(project_id)
    try:
        with kb.session() as db:
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
            return characters
    except Exception:
        return []
