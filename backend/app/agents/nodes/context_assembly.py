"""上下文组装节点（感知）

写作循环的第一步：按需加载当前章节所需的所有上下文。
"""

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService


async def context_assembly_node(state: NovelState) -> NovelState:
    """组装当前章节的上下文

    从 DB 按需加载，不全文加载：
    1. 当前情节块目标 + 风格约束
    2. 待回收伏笔 + 问题链
    3. 涉及角色 + 涉及设定
    4. 前文上下文（通过 context_strategy）
    """
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 1. 当前情节块
    current_block = kb.get_current_plot_block(current_chapter)

    # 2. 风格约束
    style = kb.get_style_constraints()

    # 3. 待回收伏笔
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    pending = kb.get_pending_foreshadowings()

    # 4. 待回答问题
    questions = kb.get_questions_for_chapter(current_chapter)

    # 5. 角色
    characters = kb.get_characters()

    # 6. 世界观
    world_setting = kb.get_world_setting()

    # 7. 大纲
    outline = kb.get_outline()

    # 组装上下文摘要（存入 state 供下游节点使用）
    context_parts = []
    if current_block:
        context_parts.append(f"当前情节块：{current_block.title}")
        if current_block.must_happen:
            context_parts.append(f"必须事件：{', '.join(current_block.must_happen)}")
    if overdue:
        context_parts.append(f"⚠️超期伏笔：{', '.join([f.content for f in overdue])}")
    if pending:
        context_parts.append(f"待回收伏笔：{', '.join([f.content for f in pending[:5]])}")
    if questions:
        context_parts.append(f"待回答问题：{', '.join([q.question_text for q in questions[:3]])}")

    context_summary = "\n".join(context_parts) if context_parts else "（无额外上下文）"

    return {
        **state,
        "phase": Phase.WRITING.value,
        # 上下文数据不存入 state，下游节点通过 kb 实时读取
    }
