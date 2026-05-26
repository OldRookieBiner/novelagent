"""情节块展开节点"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import PLOT_BLOCKS_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def plot_blocks_node(state: NovelState) -> NovelState:
    """展开情节块"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    outline_text = outline.summary if outline else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "plot_blocks")

    if user_template:
        prompt_text = safe_format(user_template,
            question_chain="（问题链设计阶段输出）",
            outline=outline_text,
        )
    else:
        prompt_text = safe_format(PLOT_BLOCKS_PROMPT,
            question_chain="（问题链设计阶段输出）",
            outline=outline_text,
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.7):
        response += chunk

    return {
        **state,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.STRUCTURE.value,
    }
