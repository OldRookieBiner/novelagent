"""LangGraph 工作流定义 - 小说创作流程"""

from typing import Literal
from langgraph.graph import StateGraph, END

from app.agents.state import (
    NovelState,
    STAGE_INSPIRATION,
    STAGE_OUTLINE,
    STAGE_CHAPTER_OUTLINES,
    STAGE_WRITING,
    STAGE_REVIEW,
    STAGE_COMPLETE,
)
from app.agents.nodes.outline_generation import outline_generation_node
from app.agents.nodes.chapter_generation import chapter_outlines_node, generate_chapter_content_node
from app.agents.nodes.review import review_node
from app.agents.nodes.rewrite import rewrite_node
from app.agents.nodes.wait_confirm import wait_for_confirmation, set_waiting_state


def route_after_outline(state: NovelState) -> Literal["wait_confirm", "chapter_outlines"]:
    """大纲生成后的路由

    根据 review_mode 决定是否等待用户确认。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "chapter_outlines" - 继续生成章节大纲
    """
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "chapter_outlines"


def route_after_chapter_outlines(state: NovelState) -> Literal["wait_confirm", "chapter_content"]:
    """章节大纲生成后的路由

    根据 review_mode 决定是否等待用户确认。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "chapter_content" - 继续生成章节正文
    """
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "chapter_content"


def route_after_review(state: NovelState) -> Literal["rewrite", "next_chapter", "wait_confirm", "end"]:
    """审核后的路由

    根据审核结果和当前进度决定下一步：
    - 审核通过且有下一章 → 生成下一章
    - 审核通过且全部完成 → 结束
    - 审核不通过且未达最大重写次数 → 重写
    - 审核不通过且已达最大重写次数 → 等待用户决定或继续

    Args:
        state: 当前状态

    Returns:
        下一步动作
    """
    # 审核通过
    if state.get("review_result", {}).get("passed", False):
        # 检查是否还有下一章
        if state.get("current_chapter", 0) < state.get("chapter_count", 0):
            return "next_chapter"
        return "end"  # 全部完成

    # 审核不通过
    # 检查是否达到最大重写次数
    if state.get("rewrite_count", 0) >= state.get("max_rewrite_count", 3):
        # 超过最大重写次数，让用户决定
        if state.get("review_mode") == "auto":
            return "next_chapter"  # auto 模式强制继续
        return "wait_confirm"

    # 需要重写
    return "rewrite"


def create_novel_graph():
    """
    创建小说创作工作流图。

    节点流程：
    1. 灵感收集（前端表单） → 生成大纲
    2. 生成大纲 → 等待确认（条件）
    3. 生成章节大纲 → 等待确认（条件）
    4. 生成章节正文 → 审核
    5. 审核通过 → 下一章或完成
    6. 审核不通过 → 重写或等待用户决定

    Returns:
        StateGraph 实例
    """
    # 创建图
    graph = StateGraph(NovelState)

    # 添加节点
    # 所有节点已适配 LangGraph 签名 (state) -> state
    graph.add_node("generate_outline", outline_generation_node)
    graph.add_node("generate_chapter_outlines", chapter_outlines_node)
    graph.add_node("generate_chapter_content", generate_chapter_content_node)
    graph.add_node("review_chapter", review_node)
    graph.add_node("rewrite_chapter", rewrite_node)

    # 设置入口点
    graph.set_entry_point("generate_outline")

    # 添加边
    # 大纲 → 章节大纲（条件路由）
    graph.add_conditional_edges(
        "generate_outline",
        route_after_outline,
        {
            "wait_confirm": END,  # 等待确认时结束，用户确认后从下一个节点继续
            "chapter_outlines": "generate_chapter_outlines"
        }
    )

    # 章节大纲 → 章节正文（条件路由）
    graph.add_conditional_edges(
        "generate_chapter_outlines",
        route_after_chapter_outlines,
        {
            "wait_confirm": END,
            "chapter_content": "generate_chapter_content"
        }
    )

    # 章节正文 → 审核
    graph.add_edge("generate_chapter_content", "review_chapter")

    # 审核 → 重写/下一章/完成（条件路由）
    graph.add_conditional_edges(
        "review_chapter",
        route_after_review,
        {
            "rewrite": "rewrite_chapter",
            "next_chapter": "generate_chapter_content",  # 回到章节正文生成
            "wait_confirm": END,
            "end": END
        }
    )

    # 重写 → 审核
    graph.add_edge("rewrite_chapter", "review_chapter")

    return graph.compile()


def create_novel_graph_with_checkpointer(project_id: int, thread_id: str = "default"):
    """
    创建带检查点的小说创作工作流图。

    带检查点的图支持暂停/恢复功能，
    用于实现用户确认后继续执行的流程。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID（默认 "default"）

    Returns:
        编译后的 StateGraph 实例
    """
    from app.agents.checkpointer import get_checkpoint_saver

    graph = create_novel_graph()
    checkpointer = get_checkpoint_saver(project_id, thread_id)

    return graph.with_checkpointer(checkpointer)


# 导出的公共 API
__all__ = [
    "create_novel_graph",
    "create_novel_graph_with_checkpointer",
    "route_after_outline",
    "route_after_chapter_outlines",
    "route_after_review",
]
