"""支线网络生成节点"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import SUBPLOT_NETWORK_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def subplot_network_node(state: NovelState) -> NovelState:
    """生成支线网络"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    characters = kb.get_characters()
    chars_text = "\n".join([f"- {c.name}：{c.role}" for c in characters])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "subplot_network")

    if user_template:
        prompt_text = safe_format(user_template,
            plot_blocks="（情节块阶段输出）",
            characters=chars_text,
        )
    else:
        prompt_text = safe_format(SUBPLOT_NETWORK_PROMPT,
            plot_blocks="（情节块阶段输出）",
            characters=chars_text,
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.6):
        response += chunk

    return {**state}
