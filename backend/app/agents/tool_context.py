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
