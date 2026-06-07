"""支线网络生成节点

基于情节块和角色生成支线网络，解析并持久化到 DB。
"""

import re
import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import SUBPLOT_NETWORK_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)

# 解析支线行格式：- 支线名 | 涉及角色 | 当前状态 | 提出章节 | 交汇章节 | 预期解决章节
_RE_SUBPLOT_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*(\d+)?\s*\|\s*(\d+)?(?:\n|$)",
)


def parse_subplot_response(response: str) -> list[dict]:
    """解析 LLM 返回的支线列表

    格式：- 支线名 | 涉及角色(逗号分隔) | 当前状态 | 提出章节 | 交汇章节 | 预期解决章节
    """
    subplots = []
    for line in response.splitlines():
        m = _RE_SUBPLOT_LINE.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        characters_str = m.group(2).strip()
        current_status = m.group(3).strip()
        raised_chapter = int(m.group(4))
        intersection_chapter = int(m.group(5)) if m.group(5) else None
        resolution_chapter = int(m.group(6)) if m.group(6) else None

        if not name:
            continue

        characters = [c.strip() for c in characters_str.split(",") if c.strip()]

        subplots.append({
            "name": name,
            "characters": characters,
            "current_status": current_status,
            "raised_in_chapter": raised_chapter,
            "planned_intersection_chapter": intersection_chapter,
            "expected_resolution_chapter": resolution_chapter,
        })

    return subplots


async def subplot_network_node(state: NovelState) -> NovelState:
    """生成支线网络"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    characters = kb.get_characters()
    chars_text = "\n".join([f"- {c.name}：{c.role}" for c in characters])

    # 读取情节块
    plot_blocks = kb.get_plot_blocks()
    blocks_text = "\n".join([f"- {b.title}（{b.chapter_start}-{b.chapter_end}）" for b in plot_blocks])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "subplot_network")

    if user_template:
        prompt_text = safe_format(user_template,
            plot_blocks=blocks_text,
            characters=chars_text,
        )
    else:
        prompt_text = safe_format(SUBPLOT_NETWORK_PROMPT,
            plot_blocks=blocks_text,
            characters=chars_text,
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.6
    ):
        response += chunk

    # 解析支线并持久化
    parsed = parse_subplot_response(response)
    logger.info(f"subplot_network_node: Parsed {len(parsed)} subplots")

    for sp_data in parsed:
        kb.create_subplot(sp_data)

    return {}
