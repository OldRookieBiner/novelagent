# agents/base.py
"""Agent 基类"""

from typing import Dict, Any, Optional
from core.llm_client import get_client
from core.conversation import Conversation


class BaseAgent:
    """所有 Agent 的基类"""

    def __init__(self, name: str, system_prompt: str = ""):
        self.name = name
        self.system_prompt = system_prompt
        self.conversation = Conversation()
        self.llm_client = get_client()

    def chat(self, user_input: str, system_prompt: str = None) -> str:
        """
        与 LLM 进行对话

        Args:
            user_input: 用户输入
            system_prompt: 可选的系统提示词，覆盖默认值

        Returns:
            LLM 的回复
        """
        self.conversation.add_user_message(user_input)

        system = system_prompt or self.system_prompt
        response = self.llm_client.chat_with_system(
            system,
            self.conversation.get_history()
        )

        self.conversation.add_assistant_message(response)
        return response

    def reset_conversation(self) -> None:
        """重置对话历史"""
        self.conversation.clear()

    def load_conversation(self, history: list) -> None:
        """加载已有的对话历史"""
        self.conversation.from_dict(history)