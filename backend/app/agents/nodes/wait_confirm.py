"""等待用户确认节点"""

from typing import Literal
from app.agents.state import NovelState


def wait_for_confirmation(state: NovelState) -> Literal["wait", "continue"]:
    """
    检查是否需要等待用户确认。

    根据工作流模式和当前阶段决定是否暂停。

    Returns:
        "wait" - 需要等待用户确认
        "continue" - 可以继续执行
    """
    workflow_mode = state.get("review_mode", "hybrid")  # 使用 review_mode 作为工作流模式
    confirmation_type = state.get("confirmation_type")

    # 如果已经在等待确认，返回 wait
    if state.get("waiting_for_confirmation"):
        return "wait"

    # step_by_step 模式：每个节点都需要确认
    if workflow_mode == "step_by_step":
        if confirmation_type:
            return "wait"

    # hybrid 模式：大纲和章节大纲需要确认
    elif workflow_mode == "hybrid":
        if confirmation_type in ["outline", "chapter_outlines"]:
            return "wait"

    # auto 模式：只有审核不通过需要确认
    elif workflow_mode == "auto":
        if confirmation_type == "review_failed":
            return "wait"

    return "continue"


def set_waiting_state(state: NovelState, confirmation_type: str) -> NovelState:
    """
    设置等待确认状态。

    Args:
        state: 当前状态
        confirmation_type: 确认类型（outline | chapter_outlines | review_failed）

    Returns:
        更新后的状态
    """
    return {
        **state,
        "waiting_for_confirmation": True,
        "confirmation_type": confirmation_type
    }


def clear_waiting_state(state: NovelState) -> NovelState:
    """
    清除等待确认状态。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    return {
        **state,
        "waiting_for_confirmation": False,
        "confirmation_type": None
    }
