"""写后摘要节点 — 长篇小说章节摘要生成"""

import logging

from app.agents.state import NovelState

logger = logging.getLogger(__name__)


def build_summary_prompt(chapter_content: str, prompts: dict) -> str:
    """构建摘要生成的 prompt

    Args:
        chapter_content: 章节正文
        prompts: 预加载的 prompt 模板

    Returns:
        格式化后的 prompt
    """
    from app.agents.prompts import DEFAULT_PROMPTS
    from app.agents.nodes.utils import safe_format

    template = prompts.get("chapter_summary_generation", DEFAULT_PROMPTS["chapter_summary_generation"])
    return safe_format(template, chapter_content=chapter_content)


def _get_target_chapter_num(written_chapters: list[dict], current_chapter: int) -> int | None:
    """计算需要生成摘要的章节号

    current_chapter 是下一章的编号，已写完的是 current_chapter - 1。
    返回 None 表示无需生成摘要。

    Args:
        written_chapters: 已写章节列表
        current_chapter: 当前章节号（下一章）

    Returns:
        目标章节号，或 None
    """
    target = current_chapter - 1
    if target < 1:
        return None
    # 确认目标章节有内容
    for ch in written_chapters:
        if ch.get("chapter_number") == target and ch.get("content"):
            return target
    return None


async def chapter_summary_node(state: NovelState) -> dict:
    """写后摘要节点

    长篇小说专属：审核通过后为当前章节生成200字摘要。
    节点内部直接持久化到 DB（与 outline_generation_node 模式一致），
    因为主工作流的 stream_workflow_events 不调用 NODE_PERSIST_MAP。

    双路径说明：SSE 审核端点（chapters.py）也会为长篇小说生成摘要（用于 step_by_step 模式），
    本节点处理主工作流 auto/hybrid 模式。两路径通过 DB 已有摘要检查避免重复 LLM 调用。

    Returns:
        更新 chapter_summaries（通过 reducer 合并）
    """
    from app.utils.llm import get_llm_from_state_async
    from app.agents.prompts import DEFAULT_PROMPTS

    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)

    target_chapter_num = _get_target_chapter_num(written_chapters, current_chapter)
    if target_chapter_num is None:
        return {**state, "chapter_summaries": []}

    # 找到目标章节的 content
    target_chapter = None
    for ch in written_chapters:
        if ch.get("chapter_number") == target_chapter_num:
            target_chapter = ch
            break

    if not target_chapter or not target_chapter.get("content"):
        logger.warning(f"chapter_summary_node: no content for chapter {target_chapter_num}")
        return {**state, "chapter_summaries": []}

    # 单次 DB 操作：检查已有摘要 + 持久化新摘要
    project_id = state.get("project_id")
    if project_id:
        from app.database import SessionLocal
        from app.models.outline import ChapterOutline

        db = SessionLocal()
        try:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == target_chapter_num,
            ).first()

            # 已有摘要则直接返回，避免重复 LLM 调用
            if co and co.chapter and co.chapter.summary:
                logger.info(f"chapter_summary_node: summary already exists for chapter {target_chapter_num}, skipping")
                return {
                    **state,
                    "chapter_summaries": [
                        {"chapter_number": target_chapter_num, "summary": co.chapter.summary}
                    ],
                }
        except Exception as e:
            logger.warning(f"chapter_summary_node: DB check failed: {e}")
        finally:
            db.close()

    # 获取 LLM
    llm = await get_llm_from_state_async(state)

    # 构建 prompt
    prompts = state.get("_prompts", DEFAULT_PROMPTS)
    prompt = build_summary_prompt(target_chapter["content"], prompts)

    # 流式生成摘要
    messages = [{"role": "user", "content": prompt}]
    summary = ""
    async for chunk in llm.chat_stream(messages):
        summary += chunk

    summary = summary.strip()

    if not summary:
        logger.warning(f"chapter_summary_node: empty summary for chapter {target_chapter_num}")
        return {**state, "chapter_summaries": []}

    # 持久化摘要到 DB（复用同一逻辑）
    if project_id:
        from app.database import SessionLocal
        from app.models.outline import ChapterOutline

        save_db = SessionLocal()
        try:
            co = save_db.query(ChapterOutline).filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == target_chapter_num,
            ).first()
            if co and co.chapter:
                co.chapter.summary = summary
                save_db.commit()
                logger.info(f"chapter_summary_node: persisted summary for chapter {target_chapter_num}")
        except Exception as e:
            save_db.rollback()
            logger.error(f"chapter_summary_node: persist failed: {e}")
        finally:
            save_db.close()

    return {
        **state,
        "chapter_summaries": [
            {"chapter_number": target_chapter_num, "summary": summary}
        ],
    }
