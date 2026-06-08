"""Free Operation Agent graph definition

Uses LangGraph create_react_agent with phase-aware cognitive tools.
Shares KnowledgeBaseService with the main writing loop.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.constants import AGENT_TEMPERATURES
from app.agents.constants import Phase
from app.utils.llm import resolve_llm_service


def _get_llm_from_service(llm_service, phase: str | None = None) -> ChatOpenAI:
    """Convert LLMService to LangChain ChatOpenAI for tool calling.

    温度按阶段动态切换：
    - incubation: 0.7（创意发散）
    - structure: 0.6（结构设计）
    - writing: 0.5（果断执行工具）
    - revision: 0.4（严谨审查）
    未传入 phase 或找不到映射时 fallback 0.5。
    """
    temperature = AGENT_TEMPERATURES.get(phase, 0.5) if phase else 0.5
    return ChatOpenAI(
        model=llm_service.model,
        api_key=llm_service.api_key,
        base_url=llm_service.base_url,
        temperature=temperature,
    )


# Phase -> tool list mapping
_PHASE_TOOLS = {
    Phase.INCUBATION.value: INCUBATION_TOOLS,
    Phase.STRUCTURE.value: STRUCTURE_TOOLS,
    Phase.WRITING.value: WRITING_TOOLS,
    Phase.REVISION.value: WRITING_TOOLS,
}


def create_agent_graph(
    model_config_id: int | None = None,
    user_id: int | None = None,
    phase: str | None = None,
    model_name: str | None = None,
):
    """Create a Free Operation Agent graph instance.

    Args:
        model_config_id: Model config ID for LLM selection
        user_id: User ID for LLM service resolution
        phase: Current creation phase (determines available tools)
        model_name: Specific model name within the config (for coding_plan providers)
    """
    llm_service = resolve_llm_service(model_config_id, user_id, model_name)
    llm = _get_llm_from_service(llm_service, phase)

    # Select tools by phase
    tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
