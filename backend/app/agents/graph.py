"""创作智能体工作流图定义

工作流分为四个阶段，通过 Phase enum 控制：
1. INCUBATION — 创意孵化 + 知识库初建
2. STRUCTURE — 逆向规划 + 结构设计
3. WRITING — 感知→决策→执行→自检循环
4. REVISION — 全书修订

写后自检拆分为5个独立节点（单一职责），深度审查每5章条件触发。

LangGraph human-in_the_loop 模式：
- 需要用户确认时，设置 waiting_for_confirmation=True + confirmation_type
- 图执行到 END 暂停，前端通过 checkpointer thread_id 恢复
- 恢复时调用 graph.invoke(None, config) 或 graph.stream(None, config)
- LangGraph 自动从检查点恢复状态，跳过已完成节点
"""

from typing import Literal
from langgraph.graph import StateGraph, END

from app.agents.state import NovelState, Phase
from app.agents.nodes.inspiration_dialogue import inspiration_dialogue_node
from app.agents.nodes.story_seed import story_seed_node
from app.agents.nodes.world_setting import world_setting_node
from app.agents.nodes.style_setup import style_setup_node
from app.agents.nodes.foreshadowing_plan import foreshadowing_plan_node
from app.agents.nodes.question_chain import question_chain_design_node
from app.agents.nodes.plot_blocks import plot_blocks_node
from app.agents.nodes.subplot_network import subplot_network_node
from app.agents.nodes.rhythm_curve import rhythm_curve_node
from app.agents.nodes.chapter_count_estimate import chapter_count_estimate_node
from app.agents.nodes.context_assembly import context_assembly_node
from app.agents.nodes.chapter_planning import chapter_planning_node
from app.agents.nodes.chapter_writing import chapter_writing_node
from app.agents.nodes.character_consistency import character_consistency_node
from app.agents.nodes.tracking_update import tracking_update_node
from app.agents.nodes.style_check import style_check_node
from app.agents.nodes.scene_update import scene_update_node
from app.agents.nodes.post_write_summary import post_write_summary_node
from app.agents.nodes.deep_review import deep_review_node
from app.agents.nodes.structural_review import structural_review_node
from app.agents.nodes.character_arc_review import character_arc_review_node
from app.agents.nodes.final_polish import final_polish_node
from app.agents.nodes.outline_generation import outline_generation_node
from app.agents.nodes.character_generation import character_generation_node
from app.agents.nodes.relation_generation import relation_generation_node


# ========== 条件路由函数 ==========

def route_after_inspiration(state: NovelState) -> Literal["story_seed"]:
    """创意对话后的路由：对话完成→故事种子

    创意对话通过 waiting_for_confirmation 暂停，
    用户确认后 LangGraph 从检查点恢复，inspiration_dialogue_node
    检测到已有对话历史，返回下一节点。
    """
    return "story_seed"


def route_after_knowledge(state: NovelState) -> Literal["question_chain"]:
    """知识库确认后的路由：确认→结构设计

    foreshadowing_plan_node 完成后如果 waiting_for_confirmation=True，
    图暂停到 END，用户确认后恢复执行 question_chain_design_node。
    如果 waiting_for_confirmation=False，直接继续。
    """
    if state.get("waiting_for_confirmation"):
        return "__end__"
    return "question_chain"


def route_after_structure(state: NovelState) -> Literal["context_assembly"]:
    """结构确认后的路由：确认→写作"""
    if state.get("waiting_for_confirmation"):
        return "__end__"
    return "context_assembly"


def route_after_chapter_node(state: NovelState) -> Literal["chapter_writing"]:
    """章节点确认后的路由"""
    if state.get("waiting_for_confirmation"):
        return "__end__"
    return "chapter_writing"


def route_after_post_write(state: NovelState) -> Literal["deep_review", "context_assembly", "structural_review"]:
    """写后自检后的路由

    - 每5章触发深度审查
    - 还有下一章→回到上下文组装
    - 全部完成→进入修订
    """
    current_chapter = state.get("current_chapter", 1)
    chapter_count = state.get("chapter_count", 0)
    last_review = state.get("last_review_chapter", 0)

    # 每5章触发深度审查
    if current_chapter > 0 and (current_chapter % 5 == 0) and last_review < current_chapter - 4:
        return "deep_review"

    # 全部章节完成→修订
    if current_chapter > chapter_count:
        return "structural_review"

    # 继续写下一章
    return "context_assembly"


def route_after_deep_review(state: NovelState) -> Literal["context_assembly", "structural_review"]:
    """深度审查后的路由"""
    current_chapter = state.get("current_chapter", 1)
    chapter_count = state.get("chapter_count", 0)

    if current_chapter > chapter_count:
        return "structural_review"
    return "context_assembly"


# ========== 图构建 ==========

def create_novel_graph(checkpointer=None):
    """创建创作智能体工作流图

    工作流：

    创意孵化：
    inspiration_dialogue ⇄ 用户 ↔ story_seed → outline_generation
    → character_generation → relation_generation
    → world_setting → style_setup → foreshadowing_plan
    → (用户确认知识库)

    结构设计：
    → question_chain → plot_blocks → subplot_network → rhythm_curve → chapter_count_estimate
    → (用户确认结构)

    写作循环：
    context_assembly → chapter_planning → (用户确认章节点) → chapter_writing
    → character_consistency → tracking_update → style_check → scene_update → post_write_summary
    → (条件: 每5章→deep_review) → deep_review → (条件: 还有下一章→context_assembly, 全部完成→revision)

    修订：
    structural_review → character_arc_review → final_polish → END
    """
    graph = StateGraph(NovelState)

    # ===== 添加节点 =====

    # 创意孵化
    graph.add_node("inspiration_dialogue_node", inspiration_dialogue_node)
    graph.add_node("story_seed_node", story_seed_node)
    graph.add_node("outline_generation_node", outline_generation_node)
    graph.add_node("character_generation_node", character_generation_node)
    graph.add_node("relation_generation_node", relation_generation_node)
    graph.add_node("world_setting_node", world_setting_node)
    graph.add_node("style_setup_node", style_setup_node)
    graph.add_node("foreshadowing_plan_node", foreshadowing_plan_node)

    # 结构设计
    graph.add_node("question_chain_design_node", question_chain_design_node)
    graph.add_node("plot_blocks_node", plot_blocks_node)
    graph.add_node("subplot_network_node", subplot_network_node)
    graph.add_node("rhythm_curve_node", rhythm_curve_node)
    graph.add_node("chapter_count_estimate_node", chapter_count_estimate_node)

    # 写作
    graph.add_node("context_assembly_node", context_assembly_node)
    graph.add_node("chapter_planning_node", chapter_planning_node)
    graph.add_node("chapter_writing_node", chapter_writing_node)

    # 写后自检（5个独立节点）
    graph.add_node("character_consistency_node", character_consistency_node)
    graph.add_node("tracking_update_node", tracking_update_node)
    graph.add_node("style_check_node", style_check_node)
    graph.add_node("scene_update_node", scene_update_node)
    graph.add_node("post_write_summary_node", post_write_summary_node)

    # 深度审查
    graph.add_node("deep_review_node", deep_review_node)

    # 修订
    graph.add_node("structural_review_node", structural_review_node)
    graph.add_node("character_arc_review_node", character_arc_review_node)
    graph.add_node("final_polish_node", final_polish_node)

    # ===== 设置入口点 =====
    graph.set_entry_point("inspiration_dialogue_node")

    # ===== 添加边 =====

    # 创意孵化
    # inspiration_dialogue 通过 waiting_for_confirmation 暂停到 END
    # 用户确认后 LangGraph 恢复执行 → 检查消息 → story_seed 或继续对话
    graph.add_conditional_edges(
        "inspiration_dialogue_node",
        route_after_inspiration,
        {"story_seed": "story_seed_node"},
    )
    graph.add_edge("story_seed_node", "outline_generation_node")
    graph.add_edge("outline_generation_node", "character_generation_node")
    graph.add_edge("character_generation_node", "relation_generation_node")
    graph.add_edge("relation_generation_node", "world_setting_node")

    # 知识库构建
    graph.add_edge("world_setting_node", "style_setup_node")
    graph.add_edge("style_setup_node", "foreshadowing_plan_node")
    graph.add_conditional_edges(
        "foreshadowing_plan_node",
        route_after_knowledge,
        {"question_chain": "question_chain_design_node"},
    )

    # 结构设计
    graph.add_edge("question_chain_design_node", "plot_blocks_node")
    graph.add_edge("plot_blocks_node", "subplot_network_node")
    graph.add_edge("subplot_network_node", "rhythm_curve_node")
    graph.add_edge("rhythm_curve_node", "chapter_count_estimate_node")
    graph.add_conditional_edges(
        "chapter_count_estimate_node",
        route_after_structure,
        {"context_assembly": "context_assembly_node"},
    )

    # 写作循环
    graph.add_conditional_edges(
        "chapter_planning_node",
        route_after_chapter_node,
        {"chapter_writing": "chapter_writing_node"},
    )
    graph.add_edge("chapter_writing_node", "character_consistency_node")
    graph.add_edge("character_consistency_node", "tracking_update_node")
    graph.add_edge("tracking_update_node", "style_check_node")
    graph.add_edge("style_check_node", "scene_update_node")
    graph.add_edge("scene_update_node", "post_write_summary_node")

    # 写后路由
    graph.add_conditional_edges(
        "post_write_summary_node",
        route_after_post_write,
        {
            "deep_review": "deep_review_node",
            "context_assembly": "context_assembly_node",
            "structural_review": "structural_review_node",
        },
    )

    # 深度审查后路由
    graph.add_conditional_edges(
        "deep_review_node",
        route_after_deep_review,
        {
            "context_assembly": "context_assembly_node",
            "structural_review": "structural_review_node",
        },
    )

    # 修订
    graph.add_edge("structural_review_node", "character_arc_review_node")
    graph.add_edge("character_arc_review_node", "final_polish_node")
    graph.add_edge("final_polish_node", END)

    return graph.compile(checkpointer=checkpointer)


def create_novel_graph_with_checkpointer(
    project_id: int, thread_id: str = "default"
):
    """创建带检查点的创作智能体工作流图"""
    from app.agents.checkpointer import get_checkpoint_saver

    checkpointer = get_checkpoint_saver(project_id, thread_id)
    return create_novel_graph(checkpointer=checkpointer)


__all__ = [
    "create_novel_graph",
    "create_novel_graph_with_checkpointer",
    "route_after_inspiration",
    "route_after_knowledge",
    "route_after_structure",
    "route_after_chapter_node",
    "route_after_post_write",
    "route_after_deep_review",
]
