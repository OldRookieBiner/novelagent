"""问题链设计节点（逆向规划核心）"""

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.prompts import QUESTION_CHAIN_PROMPT
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


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
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.7):
        response += chunk

    return {
        **state,
        "phase": Phase.STRUCTURE.value,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.STRUCTURE.value,
    }
