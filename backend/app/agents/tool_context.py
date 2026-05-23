# backend/app/agents/tool_context.py
"""Agent tool 运行时上下文

使用 contextvars 在 async 环境中安全传递请求级别的上下文，
避免全局变量在并发请求间交叉污染。
"""

from contextvars import ContextVar

# 当前请求的模型配置 ID
_current_model_config_id: ContextVar[int | None] = ContextVar('model_config_id', default=None)

# 当前请求的用户 ID
_current_user_id: ContextVar[int | None] = ContextVar('user_id', default=None)


def set_tool_context(model_config_id: int | None = None, user_id: int | None = None):
    """设置当前请求的 tool 上下文，返回重置 token 列表"""
    tokens = []
    if model_config_id is not None:
        tokens.append(_current_model_config_id.set(model_config_id))
    if user_id is not None:
        tokens.append(_current_user_id.set(user_id))
    return tokens


def reset_tool_context(tokens: list):
    """重置 tool 上下文（请求结束时调用）"""
    for token in tokens:
        token.var.reset(token)


def get_model_config_id() -> int | None:
    """获取当前请求的模型配置 ID"""
    return _current_model_config_id.get()


def get_user_id() -> int | None:
    """获取当前请求的用户 ID"""
    return _current_user_id.get()
