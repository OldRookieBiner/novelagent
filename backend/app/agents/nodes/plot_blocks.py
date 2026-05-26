"""情节块展开节点

基于大纲和问题链展开情节块，解析并持久化到 DB。
"""

import re
import logging

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import PLOT_BLOCKS_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)

# 解析情节块行格式：- 标题 | 起始章 | 结束章 | 必须事件 | 预期情绪
_RE_BLOCK_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(\d+)\s*[-~]\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)(?:\n|$)",
)


def parse_plot_blocks_response(response: str) -> list[dict]:
    """解析 LLM 返回的情节块列表

    格式：- 标题 | 起始章-结束章 | 必须事件(逗号分隔) | 预期情绪
    """
    blocks = []
    for line in response.splitlines():
        m = _RE_BLOCK_LINE.search(line)
        if not m:
            continue
        title = m.group(1).strip()
        chapter_start = int(m.group(2))
        chapter_end = int(m.group(3))
        must_happen_str = m.group(4).strip()
        expected_mood = m.group(5).strip()

        if not title:
            continue

        must_happen = [e.strip() for e in must_happen_str.split(",") if e.strip()]

        blocks.append({
            "title": title,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "must_happen": must_happen,
            "expected_mood": expected_mood,
            "questions_to_answer": [],
            "questions_to_raise": [],
        })

    return blocks


async def plot_blocks_node(state: NovelState) -> NovelState:
    """展开情节块"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    outline_text = outline.summary if outline else ""

    # 读取已有问题链
    questions = kb.get_plot_questions()
    questions_text = "\n".join([
        f"- {q.question_text}（{q.status}）"
        for q in questions
    ]) if questions else "（问题链设计阶段输出）"

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "plot_blocks")

    if user_template:
        prompt_text = safe_format(user_template,
            question_chain=questions_text,
            outline=outline_text,
        )
    else:
        prompt_text = safe_format(PLOT_BLOCKS_PROMPT,
            question_chain=questions_text,
            outline=outline_text,
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.7
    ):
        response += chunk

    # 解析情节块并持久化
    parsed = parse_plot_blocks_response(response)
    logger.info(f"plot_blocks_node: Parsed {len(parsed)} plot blocks")

    for block_data in parsed:
        kb.create_plot_block(block_data)

    return {**state}
