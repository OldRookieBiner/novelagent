"""Agent tool runtime context

Uses contextvars to safely pass request-level context in async environments,
preventing cross-contamination between concurrent requests.
"""

from contextvars import ContextVar

# Current request model config ID
_current_model_config_id: ContextVar[int | None] = ContextVar("model_config_id", default=None)

# Current request user ID
_current_user_id: ContextVar[int | None] = ContextVar("user_id", default=None)

# Current request project ID — shared by all cognitive tools
_current_project_id: ContextVar[int | None] = ContextVar("project_id", default=None)


def set_tool_context(
    model_config_id: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
):
    """Set tool context for the current request, return reset tokens"""
    tokens = []
    if model_config_id is not None:
        tokens.append(_current_model_config_id.set(model_config_id))
    if user_id is not None:
        tokens.append(_current_user_id.set(user_id))
    if project_id is not None:
        tokens.append(_current_project_id.set(project_id))
    return tokens


def reset_tool_context(tokens: list):
    """Reset tool context (called when request ends)"""
    for token in tokens:
        token.var.reset(token)


def get_model_config_id() -> int | None:
    return _current_model_config_id.get()


def get_user_id() -> int | None:
    return _current_user_id.get()


def get_project_id() -> int | None:
    return _current_project_id.get()


# 单次 SSE 请求内的工具结果缓存
_current_tool_cache: ContextVar["ToolResultCache | None"] = ContextVar("tool_cache", default=None)


def get_tool_cache():
    """获取当前请求的工具缓存"""
    from app.agents.tools.cache import ToolResultCache
    cache = _current_tool_cache.get()
    return cache


def set_tool_cache(cache) -> None:
    """设置当前请求的工具缓存"""
    _current_tool_cache.set(cache)

# 预加载数据声明 — knowledge_search 感知上下文中已有哪些数据
_loaded_keys: ContextVar[list[str]] = ContextVar("loaded_keys", default=[])


def set_loaded_keys(keys: list[str]) -> None:
    """设置当前请求的预加载数据类型列表"""
    _loaded_keys.set(keys)


def get_loaded_keys() -> list[str]:
    """获取当前请求的预加载数据类型列表"""
    return _loaded_keys.get()


# 单次 SSE 请求内的 LLM 工具调用计数器
_llm_call_count: ContextVar[int] = ContextVar("llm_call_count", default=0)


def get_llm_call_count() -> int:
    """获取当前请求的 LLM 工具调用计数"""
    return _llm_call_count.get()


def increment_llm_call_count() -> int:
    """递增 LLM 工具调用计数，返回递增后的值"""
    current = _llm_call_count.get()
    new_val = current + 1
    _llm_call_count.set(new_val)
    return new_val


def reset_llm_call_count() -> None:
    """重置 LLM 工具调用计数（每次 SSE 请求开始时调用）"""
    _llm_call_count.set(0)


# 请求级 BudgetTracker（用于成本控制）
_current_budget_tracker: ContextVar = ContextVar("budget_tracker", default=None)


def get_budget_tracker():
    """获取当前请求的 BudgetTracker"""
    return _current_budget_tracker.get()


def set_budget_tracker(tracker) -> None:
    """设置当前请求的 BudgetTracker"""
    _current_budget_tracker.set(tracker)
