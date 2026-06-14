"""审核章节工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.services.chapter_quality import ChapterQuality
from app.agents.token_budget import get_context_window


@tool
async def review_chapter(chapter_number: int) -> dict:
    """审查章节质量（6 维度评分）。

    对已完成章节进行多维度质量评估，包括情节连贯性、角色表现、文笔质量、节奏感、情感表达和整体评分。

    Args:
            chapter_number: 要审核的章节号（如 1, 2, 3）
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    try:
        llm = resolve_llm_service(get_model_config_id(), get_user_id())
    except ValueError as e:
        return {"error": f"Cannot resolve LLM config: {e}"}

    context_window = get_context_window()
    cq = ChapterQuality(project_id, llm, context_window=context_window)
    return await cq.review(chapter_number)
