"""伏笔-回收地图规划节点

基于大纲和角色生成伏笔计划，解析并持久化到 DB。
"""

import re
import logging

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import FORESHADOWING_PLAN_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)

# 解析伏笔行格式：- 伏笔内容 | 等级(hint/strengthened) | 种入章节 | 预期回收章节
_RE_FORESHADOWING_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(hint|strengthened|揭示)\s*\|\s*(\d+)\s*\|\s*(\d+)(?:\s*\|\s*(.+?))?(?:\n|$)",
    re.IGNORECASE,
)


def parse_foreshadowing_response(response: str) -> list[dict]:
    """解析 LLM 返回的伏笔列表

    格式：- 伏笔内容 | 等级 | 种入章节 | 预期回收章节 | 涉及角色(可选)
    """
    foreshadowings = []
    for line in response.splitlines():
        m = _RE_FORESHADOWING_LINE.search(line)
        if not m:
            continue
        content = m.group(1).strip()
        level = m.group(2).strip().lower()
        planted_chapter = int(m.group(3))
        expected_resolve = int(m.group(4))
        characters_str = m.group(5).strip() if m.group(5) else ""

        if not content:
            continue

        # 规范化等级
        if level not in ("hint", "strengthened"):
            level = "hint"

        foreshadowings.append({
            "content": content,
            "level": level,
            "status": "active",
            "appearance_count": 0,
            "planted_chapter": planted_chapter,
            "expected_resolve_chapter": expected_resolve,
            "related_characters": [c.strip() for c in characters_str.split(",") if c.strip()] if characters_str else [],
        })

    return foreshadowings


async def foreshadowing_plan_node(state: NovelState) -> NovelState:
    """规划伏笔-回收地图"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    characters = kb.get_characters()
    outline_text = outline.summary if outline else ""
    chars_text = "\n".join([f"- {c.name}：{c.core_motivation or ''}" for c in characters])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "foreshadowing_plan")

    if user_template:
        prompt_text = safe_format(user_template,
            outline=outline_text,
            characters=chars_text,
        )
    else:
        prompt_text = safe_format(FORESHADOWING_PLAN_PROMPT,
            outline=outline_text,
            characters=chars_text,
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.7
    ):
        response += chunk

    # 解析伏笔并持久化到 DB
    parsed = parse_foreshadowing_response(response)
    logger.info(f"foreshadowing_plan_node: Parsed {len(parsed)} foreshadowings")

    for fs_data in parsed:
        kb.create_foreshadowing(fs_data)

    return {
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.FORESHADOWING_PLAN.value,
    }
