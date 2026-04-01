# core/conversation.py
"""对话历史管理"""

from typing import List, Dict, Optional


class Conversation:
    """管理单次会话的对话历史"""

    def __init__(self):
        self.history: List[Dict[str, str]] = []

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.history.append({"role": "assistant", "content": content})

    def get_history(self) -> List[Dict[str, str]]:
        """获取完整对话历史"""
        return self.history.copy()

    def get_last_user_message(self) -> Optional[str]:
        """获取最后一条用户消息"""
        for msg in reversed(self.history):
            if msg["role"] == "user":
                return msg["content"]
        return None

    def clear(self) -> None:
        """清空对话历史"""
        self.history = []

    def to_dict(self) -> List[Dict[str, str]]:
        """序列化为字典列表"""
        return self.history.copy()

    def from_dict(self, data: List[Dict[str, str]]) -> None:
        """从字典列表恢复"""
        self.history = data.copy()