"""世界观生成节点"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import WORLD_SETTING_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format, parse_world_setting_response


async def world_setting_node(state: NovelState) -> NovelState:
    """生成世界观设定（🔴🟡🟢分级）"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    # 获取大纲
    outline = kb.get_outline()
    outline_text = outline.summary if outline else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "world_setting")

    if user_template:
        prompt_text = safe_format(user_template, outline=outline_text)
    else:
        prompt_text = safe_format(WORLD_SETTING_PROMPT, outline=outline_text)

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.7):
        response += chunk

    # 从 LLM 输出中解析分级设定和关键地点
    parsed = parse_world_setting_response(response)
    world_setting = kb.create_world_setting({
        "core_concept": parsed["core_concept"],
        "tiered_settings": parsed["tiered_settings"],
        "key_locations": parsed["key_locations"],
    })

    return {
        "world_setting_id": world_setting.id,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.WORLD_SETTING.value,
    }
