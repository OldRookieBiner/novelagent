"""Info collection node"""

from typing import Dict, Any
import json

from app.agents.state import NovelState, STAGE_OUTLINE_GENERATING
from app.agents.prompts import INFO_COLLECTION_SYSTEM_PROMPT
from app.services.llm import LLMService


def parse_collected_info(response: str, current_info: Dict[str, str]) -> Dict[str, str]:
    """Parse collected info from response"""
    # Simple parsing - extract info from response
    # This is a simplified implementation
    info = current_info.copy()

    # Look for key information in the response
    keywords = {
        "genre": ["题材", "类型", "武侠", "科幻", "都市", "言情", "悬疑", "奇幻"],
        "theme": ["主题", "主线", "核心"],
        "main_characters": ["主角", "人物", "角色"],
        "world_setting": ["背景", "时代", "世界观"],
        "style_preference": ["风格", "字数", "篇幅"]
    }

    # Check if info is sufficient
    if "信息已充足" in response:
        return info, True

    return info, False


async def info_collection_node(state: NovelState, llm: LLMService) -> NovelState:
    """Handle info collection"""

    # Format current collected info
    collected_info = state.get("collected_info", {})
    info_str = "\n".join([f"- {k}: {v}" for k, v in collected_info.items()]) or "（尚未收集任何信息）"

    # Build system prompt
    system_prompt = INFO_COLLECTION_SYSTEM_PROMPT.format(collected_info=info_str)

    # Build messages
    messages = state.get("messages", [])
    last_user_message = state.get("last_user_message", "")

    if last_user_message:
        messages = messages + [{"role": "user", "content": last_user_message}]

    # Get response
    response = await llm.chat_with_system(system_prompt, messages)

    # Parse collected info
    updated_info, is_sufficient = parse_collected_info(response, collected_info)

    # Build new state
    new_messages = messages + [{"role": "assistant", "content": response}]

    new_state: NovelState = {
        **state,
        "collected_info": updated_info,
        "messages": new_messages,
        "last_assistant_message": response,
    }

    # Check if we should move to next stage
    if is_sufficient:
        new_state["stage"] = STAGE_OUTLINE_GENERATING

    return new_state