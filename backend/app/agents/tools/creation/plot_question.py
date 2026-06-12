"""创建问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_plot_question(
    question_text: str,
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
) -> dict:
    """Create a new plot question in the question chain.

    Use when the user wants to add a dramatic question that the story
    needs to answer. Part of the reverse-planning question chain system.

    Args:
        question_text: The question to be answered (e.g., "主角为什么被追捕？")
        raised_in_chapter: Chapter number where this question is raised
        plot_block_id: Optional plot block ID that this question belongs to
    """
    kb = _kb()

    data = {"question_text": question_text, "status": "pending"}
    if raised_in_chapter is not None:
        data["raised_in_chapter"] = raised_in_chapter
    if plot_block_id is not None:
        data["plot_block_id"] = plot_block_id

    q = kb.plots.create_plot_question(data)
    return {
        "action": "created",
        "id": q["id"],
        "question_text": question_text[:80],
        "message": f"问题「{question_text[:60]}」已创建并写入知识库",
    }
