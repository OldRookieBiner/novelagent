"""伏笔-回收地图规划节点"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import FORESHADOWING_PLAN_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


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
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.7):
        response += chunk

    # 伏笔解析和入库在确认后由确认回调处理
    # 此节点只生成文本供用户确认
    return {
        **state,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.FORESHADOWING_PLAN.value,
    }
