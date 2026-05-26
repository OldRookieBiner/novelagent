"""角色弧与风格一致性检查节点"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHARACTER_ARC_REVIEW_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def character_arc_review_node(state: NovelState) -> NovelState:
    """角色弧验证 + 逐章风格检查 + 开场钩子闭环"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    characters = kb.get_characters()
    style = kb.get_style_constraints()
    snapshots = kb.get_style_snapshots()

    chars_text = "\n".join([f"- {c.name}：弧线={c.growth_arc or '未设定'}" for c in characters])
    style_text = f"禁忌词：{style.taboo_words}" if style else ""
    stats_text = "\n".join([f"第{s.chapter_number}章：对话{s.dialogue_ratio:.0%}" for s in snapshots[-10:]])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "character_arc_review")

    if user_template:
        prompt_text = safe_format(user_template,
            characters=chars_text,
            style_constraints=style_text,
            style_stats=stats_text,
        )
    else:
        prompt_text = safe_format(CHARACTER_ARC_REVIEW_PROMPT,
            characters=chars_text,
            style_constraints=style_text,
            style_stats=stats_text,
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.2):
        response += chunk

    return {**state}
