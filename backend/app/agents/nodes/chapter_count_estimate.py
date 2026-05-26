"""章节数估算节点"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService


async def chapter_count_estimate_node(state: NovelState) -> NovelState:
    """基于目标字数和情节块数估算章节数

    短篇每章 1500-2500 字，长篇 2000-4000 字。
    """
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    outline = kb.get_outline()
    target_words = outline.project.target_words if outline and outline.project else 100000
    plot_blocks = kb.get_plot_blocks()
    block_count = len(plot_blocks)

    # 估算：每章约 3000 字
    chapter_count = max(1, target_words // 3000)
    # 确保至少等于情节块数
    chapter_count = max(chapter_count, block_count)

    return {
        **state,
        "chapter_count": chapter_count,
    }
