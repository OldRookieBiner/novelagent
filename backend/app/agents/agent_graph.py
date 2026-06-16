"""Free Operation Agent graph definition

Uses LangGraph create_react_agent with phase-aware cognitive tools.
Shares KnowledgeBaseService with the main writing loop.

Phase 4 集成：动态工具注册表 + 工具调用后 hooks + 请求级缓存。
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.tools.registry_v2 import ToolRegistry
from app.agents.tools.hooks import run_post_hooks
from app.agents.tools.cache import ToolResultCache
from app.agents.tool_context import get_project_id, get_tool_cache, set_tool_cache
from app.agents.constants import AGENT_TEMPERATURES
from app.agents.constants import Phase
from app.utils.llm import resolve_llm_service

import logging

logger = logging.getLogger(__name__)


def _get_llm_from_service(llm_service, phase: str | None = None, max_output_tokens: int | None = None) -> ChatOpenAI:
    """将 LLMService 转换为 LangChain ChatOpenAI。

    温度按阶段动态切换：
    - incubation: 0.7（创意发散）
    - structure: 0.6（结构设计）
    - writing: 0.5（果断执行工具）
    - revision: 0.4（严谨审查）
    未传入 phase 或找不到映射时 fallback 0.5。

    Args:
        llm_service: LLM 服务实例
        phase: 当前创作阶段
        max_output_tokens: 输出 token 上限
    """
    temperature = AGENT_TEMPERATURES.get(phase, 0.5) if phase else 0.5
    kwargs = {
        "model": llm_service.model,
        "api_key": llm_service.api_key,
        "base_url": llm_service.base_url,
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        kwargs["max_tokens"] = max_output_tokens
    return ChatOpenAI(**kwargs)


# 静态降级映射（project_id 不可用时使用）
_PHASE_TOOLS = {
    Phase.INCUBATION.value: INCUBATION_TOOLS,
    Phase.STRUCTURE.value: STRUCTURE_TOOLS,
    Phase.WRITING.value: WRITING_TOOLS,
    Phase.REVISION.value: WRITING_TOOLS,
}


def _wrap_tool_with_hooks_and_cache(tool):
    """包装工具函数，添加缓存检查和 post-hook 调用。

    缓存：感知类工具（perception）命中缓存时直接返回。
    Hooks：写入类工具（creation）成功后触发自动检查链。
    """
    original_fn = tool.coroutine if hasattr(tool, 'coroutine') else None
    if original_fn is None:
        # 同步工具不包装
        return tool

    tool_name = tool.name
    is_perception = tool_name in (
        "knowledge_search", "foreshadowing_check",
        "consistency_scan", "style_analysis",
        "rhythm_analysis", "progress_report",
    )

    async def wrapped_fn(*args, **kwargs):
        # 缓存检查（仅感知工具）
        if is_perception:
            cache = get_tool_cache()
            if cache:
                cached = cache.get(tool_name, kwargs)
                if cached is not None:
                    logger.debug("Tool cache hit: %s", tool_name)
                    return cached

        # 执行原始工具
        result = await original_fn(*args, **kwargs)

        # 缓存写入（仅感知工具）
        if is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                cache.set(tool_name, kwargs, result)

        # 缓存失效（写入工具执行后，清除相关感知缓存）
        if not is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                # 写入操作使所有感知缓存失效
                cache.invalidate_by_prefix([
                    "knowledge_search:", "consistency_scan:",
                    "style_analysis:", "rhythm_analysis:",
                    "progress_report:", "foreshadowing_check:",
                ])

        # Post-hooks（仅注册了 hook 的工具）
        if isinstance(result, dict) and "error" not in result:
            pid = get_project_id()
            if pid is not None:
                try:
                    result = await run_post_hooks(tool_name, result, pid)
                except Exception as e:
                    logger.warning("Post-hook chain failed for %s: %s", tool_name, e)

        return result

    # 替换工具的 coroutine
    tool.coroutine = wrapped_fn
    return tool


def create_agent_graph(
    model_config_id: int | None = None,
    user_id: int | None = None,
    phase: str | None = None,
    model_name: str | None = None,
    max_output_tokens: int | None = None,
    project_id: int | None = None,
):
    """创建 Free Operation Agent 图实例。

    Args:
        model_config_id: 模型配置 ID
        user_id: 用户 ID
        phase: 当前创作阶段（决定可用工具集）
        model_name: 指定模型名称
        max_output_tokens: 输出 token 上限
        project_id: 项目 ID（用于动态工具注册表，不传则降级为静态注册表）
    """
    llm_service = resolve_llm_service(model_config_id, user_id, model_name)
    llm = _get_llm_from_service(llm_service, phase, max_output_tokens)

    # 选择工具集：优先使用动态注册表
    if project_id and phase:
        try:
            registry = ToolRegistry(project_id, phase)
            tools = registry.get_tools()
        except Exception:
            logger.warning("动态注册表失败，降级为静态注册表")
            tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)
    else:
        tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)

    # 包装工具：添加缓存 + hooks
    tools = [_wrap_tool_with_hooks_and_cache(t) for t in tools]

    # 初始化请求级缓存
    cache = ToolResultCache()
    set_tool_cache(cache)

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
