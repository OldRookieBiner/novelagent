"""Free Operation Agent graph definition

Uses LangGraph create_react_agent with phase-aware cognitive tools.
Shares KnowledgeBaseService with the main writing loop.

Phase 4 集成：动态工具注册表 + 工具调用后 hooks + 请求级缓存 + 成本控制。
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.tools.registry_v2 import ToolRegistry
from app.agents.tools.hooks import run_post_hooks
from app.agents.tools.cache import ToolResultCache
from app.agents.tools.registry import get_cost_tier, PERCEPTION_TOOL_NAMES
from app.agents.tools.utils import _truncate_result
from app.agents.tool_context import (
    get_project_id, get_tool_cache, set_tool_cache,
    get_budget_tracker, get_llm_call_count, increment_llm_call_count, reset_llm_call_count,
)
from app.agents.constants import AGENT_TEMPERATURES
from app.agents.constants import Phase
from app.utils.llm import resolve_llm_service

import logging

logger = logging.getLogger(__name__)

# 单轮连续 LLM 工具调用上限
_MAX_LLM_CALLS_PER_TURN = 3


def _get_llm_from_service(llm_service, phase: str | None = None, max_output_tokens: int | None = None) -> ChatOpenAI:
    """将 LLMService 转换为 LangChain ChatOpenAI。

    温度按阶段动态切换：
    - incubation: 0.7（创意发散）
    - structure: 0.6（结构设计）
    - writing: 0.5（果断执行工具）
    - revision: 0.4（严谨审查）
    未传入 phase 或找不到映射时 fallback 0.5。
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
    """包装工具函数，添加缓存检查、成本控制和 post-hook 调用。

    三层成本控制（优先级从高到低）：
    1. BudgetTracker 降级 — 预算不足时拦截 LLM 工具
    2. 计数器 — 单轮连续 LLM 调用超限时拦截
    3. 感知工具输出截短 — 预算紧张时压缩输出

    缓存：感知类工具命中缓存时直接返回。
    Hooks：写入类工具成功后触发自动检查链。
    """
    original_fn = tool.coroutine if hasattr(tool, 'coroutine') else None
    if original_fn is None:
        return tool

    tool_name = tool.name
    is_perception = tool_name in PERCEPTION_TOOL_NAMES

    async def wrapped_fn(*args, **kwargs):
        cost_tier = get_cost_tier(tool_name)

        # ---- 成本控制 1: BudgetTracker 降级 ----
        if cost_tier == "llm":
            bt = get_budget_tracker()
            if bt and bt.should_throttle_llm_tool():
                return {
                    "skipped": True,
                    "reason": "Token 预算不足（剩余 < 20%），建议先使用感知工具收集信息",
                    "tool_name": tool_name,
                }

        # ---- 成本控制 2: 连续 LLM 调用计数器 ----
        if cost_tier == "llm":
            current_count = get_llm_call_count()
            if current_count >= _MAX_LLM_CALLS_PER_TURN:
                return {
                    "skipped": True,
                    "reason": f"本轮已调用 {current_count} 次 LLM 工具，达到上限。建议先使用感知工具收集信息，下轮再调用。",
                    "tool_name": tool_name,
                }
            increment_llm_call_count()

        # ---- 缓存检查（仅感知工具）----
        if is_perception:
            cache = get_tool_cache()
            if cache:
                cached = cache.get(tool_name, kwargs)
                if cached is not None:
                    logger.debug("Tool cache hit: %s", tool_name)
                    return cached

        # ---- 执行原始工具 ----
        result = await original_fn(*args, **kwargs)

        # ---- 成本控制 3: 感知工具输出截短 ----
        if is_perception and isinstance(result, dict) and "error" not in result:
            bt = get_budget_tracker()
            if bt and bt.should_throttle_llm_tool():
                result = _truncate_result(result, max_items=5, max_str_len=100)

        # ---- LLM 工具 token 消耗追踪 ----
        if cost_tier == "llm" and isinstance(result, dict):
            bt = get_budget_tracker()
            if bt and "token_usage" in result:
                try:
                    bt.llm_tool_tokens_used += result["token_usage"].get("total_tokens", 0)
                except (TypeError, AttributeError):
                    pass

        # ---- 缓存写入（仅感知工具）----
        if is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                cache.set(tool_name, kwargs, result)

        # ---- 缓存失效（写入工具执行后）----
        if not is_perception and isinstance(result, dict) and "error" not in result:
            cache = get_tool_cache()
            if cache:
                cache.invalidate_by_prefix([f"{name}:" for name in PERCEPTION_TOOL_NAMES])

        # ---- Post-hooks ----
        if isinstance(result, dict) and "error" not in result:
            pid = get_project_id()
            if pid is not None:
                try:
                    result = await run_post_hooks(tool_name, result, pid)
                except Exception as e:
                    logger.warning("Post-hook chain failed for %s: %s", tool_name, e)

        return result

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
        project_id: 项目 ID（用于动态工具注册表）
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

    # 包装工具：添加缓存 + 成本控制 + hooks
    tools = [_wrap_tool_with_hooks_and_cache(t) for t in tools]

    # 初始化请求级缓存
    cache = ToolResultCache()
    set_tool_cache(cache)

    # 重置 LLM 调用计数器
    reset_llm_call_count()

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
