"""预期节奏曲线节点"""

from app.agents.state import NovelState
from app.agents.prompts import RHYTHM_CURVE_PROMPT
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def rhythm_curve_node(state: NovelState) -> NovelState:
    """生成预期节奏曲线"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)
    plot_blocks = kb.get_plot_blocks()
    blocks_text = "\n".join([f"- {b.title}：{b.expected_mood or '未设定'}" for b in plot_blocks])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "rhythm_curve")

    if user_template:
        prompt_text = safe_format(user_template, plot_blocks=blocks_text)
    else:
        prompt_text = safe_format(RHYTHM_CURVE_PROMPT, plot_blocks=blocks_text)

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.5):
        response += chunk

    return {}
