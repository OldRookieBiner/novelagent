"""LangGraph 工作流定义 - 小说创作流程"""

from typing import Literal
from langgraph.graph import StateGraph, END

from app.agents.state import (
    NovelState,
)
from app.agents.nodes.outline_generation import outline_generation_node
from app.agents.nodes.chapter_generation import (
    chapter_outlines_node,
    generate_chapter_content_node,
)
from app.agents.nodes.review import review_node
from app.agents.nodes.rewrite import rewrite_node
from app.agents.nodes.wait_confirm import wait_for_confirmation
from app.agents.nodes.character_generation import create_characters_from_outline_node
from app.agents.nodes.relation_generation import generate_relations_node
from app.agents.nodes.volume_arc_planning import volume_arc_planning_node
from app.agents.nodes.chapter_summary import chapter_summary_node


def route_after_outline(
    state: NovelState,
) -> Literal["wait_confirm", "create_characters", "end"]:
    """大纲生成后的路由

    大纲无效时直接终止工作流，避免空大纲导致后续节点崩溃和检查点污染。

    Args:
        state: 当前状态

    Returns:
        "end" - 大纲无效，终止工作流
        "wait_confirm" - 等待用户确认
        "create_characters" - 继续提取角色
    """
    if not state.get("outline_valid", False):
        return "end"
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "create_characters"


def route_after_chapter_outlines(
    state: NovelState,
) -> Literal["wait_confirm", "chapter_content", "end"]:
    """章节大纲生成后的路由

    根据 review_mode 决定是否等待用户确认。
    如果章节大纲为空，直接结束以防止后续节点报错。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "chapter_content" - 继续生成章节正文
        "end" - 无章节大纲，结束工作流
    """
    if not state.get("chapter_outlines"):
        return "end"
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "chapter_content"


def route_after_review(
    state: NovelState,
) -> Literal["rewrite", "next_chapter", "chapter_summary", "wait_confirm", "end"]:
    """审核后的路由

    审核通过且长篇 → 先生成摘要
    审核通过且短/中篇 → 下一章或结束
    """
    # 审核通过
    if state.get("review_result", {}).get("passed", False):
        # 长篇：审核通过后先生成摘要
        if state.get("novel_length") == "long":
            return "chapter_summary"
        # 短/中篇：直接下一章
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


def route_after_characters(
    state: NovelState,
) -> Literal["wait_confirm", "generate_relations"]:
    """角色创建后的路由"""
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "generate_relations"


def route_after_relations(
    state: NovelState,
) -> Literal["wait_confirm", "volume_arc", "chapter_outlines", "end"]:
    """关系生成后的路由

    长篇小说（novel_length == "long"）进入弧/卷规划，
    短/中篇直接进入章节大纲。
    """
    if state.get("chapter_count", 0) <= 0:
        return "end"
    if not state.get("characters"):
        return "end"
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    # 长篇走弧/卷规划
    if state.get("novel_length") == "long":
        return "volume_arc"
    return "chapter_outlines"


def route_after_volume_arc(
    state: NovelState,
) -> Literal["wait_confirm", "chapter_outlines", "end"]:
    """弧/卷规划后的路由

    首次执行 → 暂停等确认
    confirm 恢复后 → 继续章节大纲
    arcs 为空（LLM 解析失败）→ 结束，避免无弧数据时章节大纲节点行为异常
    """
    if state.get("waiting_for_confirmation"):
        return "wait_confirm"
    if not state.get("arcs"):
        return "end"
    return "chapter_outlines"


def route_after_summary(
    state: NovelState,
) -> Literal["next_chapter", "end"]:
    """摘要生成后的路由"""
    if state.get("current_chapter", 0) < state.get("chapter_count", 0):
        return "next_chapter"
    return "end"


def create_novel_graph(checkpointer=None):
    """
    创建小说创作工作流图。

    节点流程：
    1. 灵感收集（前端表单） → 生成大纲
    2. 生成大纲 → 提取角色
    3. 提取角色 → 等待确认（条件）
    4. 生成关系 → 等待确认（条件）
    5. 长篇：弧/卷规划 → 等待确认（条件）→ 章节大纲
    6. 生成章节大纲 → 等待确认（条件）
    7. 生成章节正文 → 审核
    8. 审核通过 → 长篇：生成摘要 → 下一章或完成；短/中篇：下一章或完成
    9. 审核不通过 → 重写或等待用户决定

    Args:
        checkpointer: 可选的检查点保存器

    Returns:
        CompiledStateGraph 实例
    """
    # 创建图
    graph = StateGraph(NovelState)

    # 添加节点
    # 所有节点已适配 LangGraph 签名 (state) -> state
    graph.add_node("outline_generation_node", outline_generation_node)
    graph.add_node("chapter_outlines_node", chapter_outlines_node)
    graph.add_node("generate_chapter_content_node", generate_chapter_content_node)
    graph.add_node("review_node", review_node)
    graph.add_node("rewrite_node", rewrite_node)
    graph.add_node(
        "create_characters_from_outline_node", create_characters_from_outline_node
    )
    graph.add_node("generate_relations_node", generate_relations_node)
    graph.add_node("volume_arc_planning_node", volume_arc_planning_node)
    graph.add_node("chapter_summary_node", chapter_summary_node)

    # 设置入口点
    graph.set_entry_point("outline_generation_node")

    # 添加边
    # 大纲 → 角色提取（条件路由）
    graph.add_conditional_edges(
        "outline_generation_node",
        route_after_outline,
        {
            "wait_confirm": END,
            "create_characters": "create_characters_from_outline_node",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "create_characters_from_outline_node",
        route_after_characters,
        {"wait_confirm": END, "generate_relations": "generate_relations_node"},
    )

    # 关系 → 弧/卷规划（长篇）或章节大纲（短/中篇）
    graph.add_conditional_edges(
        "generate_relations_node",
        route_after_relations,
        {
            "wait_confirm": END,
            "volume_arc": "volume_arc_planning_node",
            "chapter_outlines": "chapter_outlines_node",
            "end": END,
        },
    )

    # 弧/卷规划 → 等待确认或章节大纲
    graph.add_conditional_edges(
        "volume_arc_planning_node",
        route_after_volume_arc,
        {"wait_confirm": END, "chapter_outlines": "chapter_outlines_node", "end": END},
    )

    # 章节大纲 → 章节正文（条件路由）
    graph.add_conditional_edges(
        "chapter_outlines_node",
        route_after_chapter_outlines,
        {"wait_confirm": END, "chapter_content": "generate_chapter_content_node", "end": END},
    )

    # 章节正文 → 审核
    graph.add_edge("generate_chapter_content_node", "review_node")

    # 审核 → 重写/下一章/摘要/完成（条件路由）
    graph.add_conditional_edges(
        "review_node",
        route_after_review,
        {
            "rewrite": "rewrite_node",
            "next_chapter": "generate_chapter_content_node",
            "chapter_summary": "chapter_summary_node",
            "wait_confirm": END,
            "end": END,
        },
    )

    # 摘要 → 下一章或完成
    graph.add_conditional_edges(
        "chapter_summary_node",
        route_after_summary,
        {"next_chapter": "generate_chapter_content_node", "end": END},
    )

    # 重写 → 审核
    graph.add_edge("rewrite_node", "review_node")

    return graph.compile(checkpointer=checkpointer)


def create_novel_graph_with_checkpointer(
    project_id: int, thread_id: str = "default"
):
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

    checkpointer = get_checkpoint_saver(project_id, thread_id)

    return create_novel_graph(checkpointer=checkpointer)


# 导出的公共 API
__all__ = [
    "create_novel_graph",
    "create_novel_graph_with_checkpointer",
    "route_after_outline",
    "route_after_characters",
    "route_after_chapter_outlines",
    "route_after_relations",
    "route_after_review",
    "route_after_volume_arc",
    "route_after_summary",
]
