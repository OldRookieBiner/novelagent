# backend/app/agents/agent_graph.py

"""AI 搭档 Agent 图定义"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.agent_tools import AGENT_TOOLS
from app.agents.agent_context import build_project_context
from app.utils.llm import resolve_llm_service


def _get_llm_from_service(llm_service) -> ChatOpenAI:
    """将 LLMService 转换为 LangChain ChatOpenAI 兼容对象

    复用 LLMService 的 api_key/base_url/model 配置，
    保留 provider 级别的连接信息，但 tool calling 走 LangChain 协议。
    注意：这里不使用 LLMService 的 chat/chat_stream 方法，
    因为 create_react_agent 内部管理 LLM 调用。
    """
    return ChatOpenAI(
        model=llm_service.model,
        api_key=llm_service.api_key,
        base_url=llm_service.base_url,
        temperature=0.7,
    )


def create_agent_graph(model_config_id: int = None, user_id: int = None):
    """创建 Agent 图实例"""
    llm_service = resolve_llm_service(model_config_id, user_id)
    llm = _get_llm_from_service(llm_service)

    graph = create_react_agent(
        model=llm,
        tools=AGENT_TOOLS,
    )
    return graph
