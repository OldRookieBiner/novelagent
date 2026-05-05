"""工作流节点输出持久化工具

将 LangGraph 节点的输出结果写入数据库。
在 run_workflow 和 confirm_workflow 的 SSE 流式处理中复用。
"""

import logging
from sqlalchemy.orm import Session

from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.agents.nodes.review import check_review_passed

logger = logging.getLogger(__name__)


def persist_outline(output: dict, project_id: int, outline: Outline, db: Session):
    """持久化大纲生成节点的输出到 outlines 表"""
    new_title = output.get("outline_title", "")
    new_summary = output.get("outline_summary", "")
    new_characters = output.get("outline_characters", [])
    new_plot_points = output.get("outline_plot_points", [])

    if not new_title and not new_summary and not new_characters and not new_plot_points:
        logger.warning(
            f"persist_outline: empty data for project {project_id}"
        )
        return False

    if new_title:
        outline.title = new_title
    if new_summary:
        outline.summary = new_summary
    if new_plot_points:
        outline.plot_points = new_plot_points
    if new_characters:
        outline.characters = new_characters

    outline.world_setting = output.get(
        "outline_world_setting", outline.world_setting or {}
    )
    outline.emotional_curve = output.get(
        "outline_emotional_curve", outline.emotional_curve
    )
    outline.chapter_count_suggested = output.get(
        "chapter_count", outline.chapter_count_suggested
    )

    logger.info(
        f"persist_outline: project {project_id}: "
        f"title='{new_title}', char={len(new_characters)}, "
        f"plot={len(new_plot_points)}"
    )
    return True


def persist_chapter_content(output: dict, project_id: int, db: Session):
    """持久化章节内容生成节点的输出到 chapters 表"""
    written_chapters = output.get("written_chapters", [])
    for chapter_data in written_chapters:
        chapter_num = chapter_data.get("chapter_number")
        if not chapter_num:
            continue
        chapter_outline = (
            db.query(ChapterOutline)
            .filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_num,
            )
            .first()
        )
        if not chapter_outline:
            continue
        chapter = (
            db.query(Chapter)
            .filter(Chapter.chapter_outline_id == chapter_outline.id)
            .first()
        )
        if not chapter:
            chapter = Chapter(
                chapter_outline_id=chapter_outline.id,
                content=chapter_data.get("content", ""),
                word_count=chapter_data.get("word_count", 0),
                review_passed=False,
                review_feedback=None,
            )
            db.add(chapter)
        else:
            chapter.content = chapter_data.get("content", chapter.content)
            chapter.word_count = chapter_data.get(
                "word_count", chapter.word_count
            )
    logger.info(
        f"persist_chapter_content: project {project_id}"
    )


def persist_review_result(output: dict, project_id: int, db: Session):
    """持久化审核节点的输出到 chapters 表"""
    review_result = output.get("review_result", {})
    current_chapter = output.get("current_chapter", 1)
    reviewed_chapter_num = current_chapter - 1
    chapter_outline = (
        db.query(ChapterOutline)
        .filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == reviewed_chapter_num,
        )
        .first()
    )
    if chapter_outline:
        chapter = (
            db.query(Chapter)
            .filter(Chapter.chapter_outline_id == chapter_outline.id)
            .first()
        )
        if chapter:
            chapter.review_passed = check_review_passed(review_result)
            chapter.review_feedback = review_result.get("raw_response")
            chapter.review_result = review_result
    logger.info(
        f"persist_review_result: project {project_id}"
    )


def persist_rewrite_result(output: dict, project_id: int, db: Session):
    """持久化重写节点的输出到 chapters 表"""
    written_chapters = output.get("written_chapters", [])
    for chapter_data in written_chapters:
        chapter_num = chapter_data.get("chapter_number")
        if not chapter_num:
            continue
        chapter_outline = (
            db.query(ChapterOutline)
            .filter(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_num,
            )
            .first()
        )
        if not chapter_outline:
            continue
        chapter = (
            db.query(Chapter)
            .filter(Chapter.chapter_outline_id == chapter_outline.id)
            .first()
        )
        if chapter:
            chapter.content = chapter_data.get("content", chapter.content)
            chapter.word_count = chapter_data.get(
                "word_count", chapter.word_count
            )
            chapter.rewrite_count = output.get(
                "rewrite_count", chapter.rewrite_count
            )
    logger.info(
        f"persist_rewrite_result: project {project_id}"
    )


# 节点名到持久化函数的映射
NODE_PERSIST_MAP = {
    "outline_generation_node": persist_outline,
    "generate_chapter_content_node": persist_chapter_content,
    "review_node": persist_review_result,
    "rewrite_node": persist_rewrite_result,
}
