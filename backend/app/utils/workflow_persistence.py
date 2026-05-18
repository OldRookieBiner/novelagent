"""工作流节点输出持久化工具

将 LangGraph 节点的输出结果写入数据库。
在 run_workflow 和 confirm_workflow 的 SSE 流式处理中复用。
"""

import logging
from sqlalchemy.orm import Session

from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.character import Character, Relation
from app.models.arc import Arc
from app.models.volume import Volume
from app.agents.nodes.review import check_review_passed
from app.agents.nodes.character_generation import _map_role
from app.agents.nodes.relation_generation import write_relations_to_db

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


def persist_arc_outlines(output: dict, project_id: int, db: Session):
    """持久化弧纲到 Arc.outline 和 Arc.outline_confirmed 字段

    从 output["arcs"] 读取弧纲数据，更新对应 Arc 记录。
    """
    arcs_data = output.get("arcs", [])
    if not arcs_data:
        logger.info(f"persist_arc_outlines: no arcs data for project {project_id}")
        return

    for arc_data in arcs_data:
        arc_id = arc_data.get("id")
        if not arc_id:
            continue
        arc = db.query(Arc).filter(Arc.id == arc_id).first()
        if arc:
            if arc_data.get("outline"):
                arc.outline = arc_data["outline"]
            if arc_data.get("outline_confirmed") is not None:
                arc.outline_confirmed = arc_data["outline_confirmed"]

    logger.info(
        f"persist_arc_outlines: project {project_id}: "
        f"updated {len(arcs_data)} arcs"
    )


def persist_chapter_outlines(output: dict, project_id: int, db: Session):
    """持久化章节大纲生成节点的输出到 chapter_outlines 表

    长篇按弧模式：仅追加当前弧的章节大纲，不删除已有数据。
    短篇/中篇：全量写入（原有行为）。
    """
    chapter_outlines = output.get("chapter_outlines", [])
    if not chapter_outlines:
        logger.info(f"persist_chapter_outlines: no outlines for project {project_id}")
        return

    # 检查是否已有章节大纲（长篇按弧追加场景）
    existing_numbers = set(
        co.chapter_number for co in db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).all()
    )

    created_count = 0
    for co_data in chapter_outlines:
        chapter_number = co_data.get("chapter_number", 1)

        # 跳过已存在的章节大纲（按弧追加时避免重复）
        if chapter_number in existing_numbers:
            continue

        # 查询 arc_id
        arc_id = None
        vol_num = co_data.get("volume_number")
        arc_num = co_data.get("arc_number")
        if vol_num and arc_num:
            arc_record = db.query(Arc).join(Volume).filter(
                Volume.project_id == project_id,
                Volume.volume_number == vol_num,
                Arc.arc_number == arc_num,
            ).first()
            if arc_record:
                arc_id = arc_record.id

        chapter_outline = ChapterOutline(
            project_id=project_id,
            chapter_number=chapter_number,
            title=co_data.get("title"),
            scene=co_data.get("scene"),
            characters=co_data.get("characters"),
            plot=co_data.get("plot"),
            conflict=co_data.get("conflict"),
            turning_point=co_data.get("turning_point"),
            hook=co_data.get("hook"),
            transition=co_data.get("transition"),
            ending=co_data.get("ending"),
            target_words=co_data.get("target_words", 3000),
            confirmed=False,
        )
        db.add(chapter_outline)
        created_count += 1

    logger.info(
        f"persist_chapter_outlines: project {project_id}: "
        f"created {created_count} outlines (skipped {len(chapter_outlines) - created_count} existing)"
    )


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


def persist_character_generation(output: dict, project_id: int, db: Session):
    """持久化角色提取节点输出到 characters 表

    从 output["characters"] 中提取角色列表，删除项目已有角色后批量写入。

    Args:
        output: create_characters_from_outline_node 的输出
        project_id: 项目 ID
        db: 数据库会话
    """
    characters = output.get("characters", [])
    if not characters:
        logger.info(f"persist_character_generation: no characters for project {project_id}")
        return

    # 删除已有角色（重新生成场景，避免重复）
    db.query(Character).filter(Character.project_id == project_id).delete()

    for c in characters:
        char = Character(
            project_id=project_id,
            name=c.get("name", "未命名") or "未命名",
            role=c.get("role", "配角"),
            personality=c.get("personality", ""),
            core_motivation=c.get("core_motivation", ""),
            growth_arc=c.get("growth_arc", ""),
        )
        db.add(char)
        db.flush()  # 获取 id，供后续关系生成使用
        c["id"] = char.id  # 将 DB 生成的 id 写回数据，供关系生成使用

    logger.info(
        f"persist_character_generation: project {project_id}: "
        f"created {len(characters)} characters"
    )


def persist_relation_generation(output: dict, project_id: int, db: Session):
    """持久化关系生成节点输出到 relations 表

    Args:
        output: generate_relations_node 的输出
        project_id: 项目 ID
        db: 数据库会话
    """
    relations = output.get("relations", [])
    if not relations:
        logger.info(f"persist_relation_generation: no relations for project {project_id}")
        return

    write_relations_to_db(project_id, relations, db)

    logger.info(
        f"persist_relation_generation: project {project_id}: "
        f"created {len(relations)} relations"
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
    "create_characters_from_outline_node": persist_character_generation,
    "generate_relations_node": persist_relation_generation,
    "arc_outline_generation_node": persist_arc_outlines,
    "chapter_outlines_node": persist_chapter_outlines,
    "generate_chapter_content_node": persist_chapter_content,
    "review_node": persist_review_result,
    "rewrite_node": persist_rewrite_result,
}
