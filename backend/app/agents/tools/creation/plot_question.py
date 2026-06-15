"""创建问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_plot_question(
    question_text: str,
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
) -> dict:
    """在问题链中创建新的问题。

    当用户需要为情节块添加需要提出或回答的问题时使用。问题链帮助追踪情节中需要解决的悬念。

    Args:
        question_text: 问题内容
        raised_in_chapter: 提出问题的章节号（可选）
        plot_block_id: 所属情节块 ID（可选）
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
