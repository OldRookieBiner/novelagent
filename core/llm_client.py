# core/llm_client.py
"""LLM API 调用封装，支持 OpenAI 兼容接口"""

import requests
from typing import List, Dict, Optional
from config import MODEL_CONFIGS, CURRENT_MODEL


class LLMClient:
    """统一的 LLM API 调用客户端"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or CURRENT_MODEL
        self.config = MODEL_CONFIGS[self.model_name]

        if not self.config["api_key"]:
            raise ValueError(f"API Key 未配置，请在 config.py 中设置 {self.model_name} 的 api_key")

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        发送对话请求，返回回复内容

        Args:
            messages: 对话历史，格式 [{"role": "user/assistant", "content": "..."}]
            temperature: 生成温度

        Returns:
            assistant 的回复内容
        """
        url = f"{self.config['api_base']}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config["model"],
            "messages": messages,
            "temperature": temperature
        }

        response = requests.post(url, headers=headers, json=payload, timeout=600)

        if response.status_code != 200:
            raise Exception(f"API 请求失败: {response.status_code} - {response.text}")

        # 确保使用 UTF-8 解码
        response.encoding = 'utf-8'

        try:
            data = response.json()
        except Exception as e:
            # 如果 JSON 解析失败，尝试获取原始文本
            raw_text = response.text
            raise Exception(f"API 返回数据解析失败: {e}, 原始响应: {raw_text[:200]}")

        if "choices" not in data or len(data["choices"]) == 0:
            raise Exception(f"API 返回数据格式异常: {data}")

        content = data["choices"][0]["message"]["content"]
        return content

    def chat_with_system(self, system_prompt: str, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        带 system prompt 的对话请求

        Args:
            system_prompt: 系统提示词
            messages: 用户和助手的对话历史
            temperature: 生成温度

        Returns:
            assistant 的回复内容
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        return self.chat(full_messages, temperature)


# 全局客户端实例
_client: Optional[LLMClient] = None

def get_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client