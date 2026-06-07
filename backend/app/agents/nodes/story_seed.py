"""故事种子生成节点

基于创意对话的成果，生成故事种子文档。
生成后持久化到 DB（Project.story_seed），遵循 LangGraph 规范：
state 只存流程控制 + ID 引用，不缓存 DB 业务数据。
"""

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.prompts import STORY_SEED_PROMPT
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def story_seed_node(state: NovelState) -> NovelState:
    """生成故事种子并持久化到 DB"""
    project_id = state["project_id"]
    messages = state.get("inspiration_messages", [])

    # 提取对话摘要
    conversation_summary = _summarize_conversation(messages)

    llm = await get_llm_from_state_async(state)

    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "story_seed")

    if user_template:
        prompt_text = safe_format(user_template, conversation_summary=conversation_summary)
    else:
        prompt_text = safe_format(STORY_SEED_PROMPT, conversation_summary=conversation_summary)

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.7):
        response += chunk

    # 持久化到 DB，而非存入 state
    kb = KnowledgeBaseService(project_id)
    kb.update_story_seed(response)

    return {
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.STORY_SEED.value,
    }


def _summarize_conversation(messages: list[dict]) -> str:
    """将对话消息压缩为摘要文本"""
    if not messages:
        return "（无对话内容）"
    parts = []
    for msg in messages:
        role = "用户" if msg.get("role") == "user" else "Agent"
        content = msg.get("content", "")
        # 截断过长的消息
        if len(content) > 500:
            content = content[:500] + "..."
        parts.append(f"{role}：{content}")
    return "\n".join(parts)
