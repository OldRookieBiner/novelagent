"""重写章节工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.services.chapter_quality import ChapterQuality
from app.agents.token_budget import get_context_window


@tool
async def rewrite_chapter(chapter_number: int) -> dict:
    """Rewrite a chapter based on its latest review feedback.

    The chapter must have been reviewed first (review_feedback must exist).
    Generates new content, saves it to the database, increments rewrite_count,
    and clears the review state so it can be re-reviewed.

    Args:
        chapter_number: The chapter number to rewrite (e.g., 1, 2, 3)
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
    return await cq.rewrite(chapter_number)
