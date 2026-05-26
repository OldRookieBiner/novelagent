"""对话式创意孵化节点

多轮对话节点：Agent 和用户来回几轮后，提炼信息写入 state。
通过 waiting_for_confirmation + confirmation_type=inspiration_dialogue 实现暂停/恢复。
"""

from app.agents.state import NovelState, Phase, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import INSPIRATION_DIALOGUE_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def inspiration_dialogue_node(state: NovelState) -> NovelState:
    """对话式创意孵化

    逻辑：
    1. 首次进入：设置 waiting_for_confirmation，等待用户输入创意
    2. 用户回复后：将消息追加到 inspiration_messages
    3. 当创意足够充分时：提示用户可以生成故事种子
    """
    project_id = state["project_id"]
    messages = state.get("inspiration_messages", [])
    phase = state.get("phase", "")

    # 首次进入，设置等待用户输入
    if not messages and phase != Phase.INCUBATION.value:
        return {
            **state,
            "phase": Phase.INCUBATION.value,
            "waiting_for_confirmation": True,
            "confirmation_type": ConfirmationType.INSPIRATION_DIALOGUE.value,
        }

    # 获取 LLM 服务
    llm = await get_llm_from_state_async(state)

    # 构建对话历史
    conversation_history = _format_conversation_history(messages)
    user_input = messages[-1].get("content", "") if messages else "开始创作对话"

    # 获取 prompt 模板
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "inspiration_dialogue")

    if user_template:
        prompt_text = safe_format(user_template,
            conversation_history=conversation_history,
            user_input=user_input,
        )
    else:
        prompt_text = safe_format(INSPIRATION_DIALOGUE_PROMPT,
            conversation_history=conversation_history,
            user_input=user_input,
        )

    # 调用 LLM
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.8):
        response += chunk

    # 追加 Agent 回复到消息列表
    new_messages = list(messages) + [{"role": "assistant", "content": response}]

    return {
        **state,
        "phase": Phase.INCUBATION.value,
        "inspiration_messages": new_messages,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.INSPIRATION_DIALOGUE.value,
    }


def _format_conversation_history(messages: list[dict]) -> str:
    """格式化对话历史为文本"""
    if not messages:
        return "（这是第一次对话）"
    parts = []
    for msg in messages:
        role = "用户" if msg.get("role") == "user" else "Agent"
        parts.append(f"{role}：{msg.get('content', '')}")
    return "\n".join(parts)
