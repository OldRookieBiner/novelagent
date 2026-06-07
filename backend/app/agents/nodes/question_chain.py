"""问题链设计节点（逆向规划核心）

基于大纲设计问题链，解析并持久化到 DB。
"""

import re
import logging

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.prompts import QUESTION_CHAIN_PROMPT
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)

# 解析问题行格式：- 问题 | 状态(pending/answered) | 提出章节 | 回答章节(可选)
_RE_QUESTION_LINE = re.compile(
    r"[-•]\s*(.+?)\s*\|\s*(pending|answered|closed)\s*\|\s*(\d+)(?:\s*\|\s*(\d+))?(?:\n|$)",
    re.IGNORECASE,
)


def parse_question_chain_response(response: str) -> list[dict]:
    """解析 LLM 返回的问题链

    格式：- 问题文本 | 状态 | 提出章节 | 回答章节(可选)
    """
    questions = []
    for line in response.splitlines():
        m = _RE_QUESTION_LINE.search(line)
        if not m:
            continue
        question_text = m.group(1).strip()
        status = m.group(2).strip().lower()
        raised_chapter = int(m.group(3))
        answered_chapter = int(m.group(4)) if m.group(4) else None

        if not question_text:
            continue

        if status not in ("pending", "answered", "closed"):
            status = "pending"

        questions.append({
            "question_text": question_text,
            "status": status,
            "raised_in_chapter": raised_chapter,
            "answered_in_chapter": answered_chapter,
        })

    return questions


async def question_chain_design_node(state: NovelState) -> NovelState:
    """设计问题链（龙头凤尾 + 情节块的问题链）"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    outline_text = outline.summary if outline else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "question_chain")

    if user_template:
        prompt_text = safe_format(user_template, outline=outline_text)
    else:
        prompt_text = safe_format(QUESTION_CHAIN_PROMPT, outline=outline_text)

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.7
    ):
        response += chunk

    # 解析问题链并持久化
    parsed = parse_question_chain_response(response)
    logger.info(f"question_chain_design_node: Parsed {len(parsed)} questions")

    for q_data in parsed:
        kb.create_plot_question(q_data)

    return {
        "phase": Phase.STRUCTURE.value,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.STRUCTURE.value,
    }
