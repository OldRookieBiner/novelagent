"""风格约束设定节点"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import STYLE_SETUP_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def style_setup_node(state: NovelState) -> NovelState:
    """设定风格约束（禁忌词/风格锚点/禁用句式）"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    world_setting = kb.get_world_setting()
    outline_text = outline.summary if outline else ""
    world_text = world_setting.core_concept if world_setting else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "style_setup")

    if user_template:
        prompt_text = safe_format(user_template,
            outline=outline_text,
            world_setting=world_text,
            user_preference="",
        )
    else:
        prompt_text = safe_format(STYLE_SETUP_PROMPT,
            outline=outline_text,
            world_setting=world_text,
            user_preference="",
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.5):
        response += chunk

    constraints = kb.create_style_constraints({
        "taboo_words": [],
        "forbidden_patterns": [],
        "style_anchor": response,
        "abstract_rules": [],
    })

    return {
        "style_constraints_id": constraints.id,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.STYLE.value,
    }
