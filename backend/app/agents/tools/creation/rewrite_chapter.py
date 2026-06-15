"""重写章节工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.services.chapter_quality import ChapterQuality
from app.agents.token_budget import get_context_window


@tool
async def rewrite_chapter(chapter_number: int) -> dict:
    """基于最新审查反馈重写章节。

    根据 review_chapter 的审查结果，对章节进行针对性修改。会保留旧版本的内容记录。


    Prerequisites:
        - 章节必须已存在
        - 需要明确 rewrite_chapter 的具体修改方向

    Args:
            chapter_number: 要重写的章节号（如 1, 2, 3）
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    try:
        llm = resolve_llm_service(get_model_config_id(), get_user_id())
    except ValueError as e:
        return {"error": f"Cannot resolve LLM config: {e}"}

    context_window = get_context_window()
    # rewrite 输出是完整章节，需要较大 max_tokens
    # 保留 context_window 的 1/3 给输出，但至少 8K
    rewrite_max_tokens = max(8192, context_window // 3) if context_window else 16384
    cq = ChapterQuality(
        project_id, llm,
        context_window=context_window,
        rewrite_max_tokens=rewrite_max_tokens,
    )
    return await cq.rewrite(chapter_number)
