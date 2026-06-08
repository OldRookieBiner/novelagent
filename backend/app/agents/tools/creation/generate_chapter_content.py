"""生成章节内容工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb


@tool
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    summary: str = "",
    word_count: int = 0,
    status: str = "draft",
    scene_count: int = 0,
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
    timeline_summary: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
) -> dict:
    """Generate and save a complete chapter with all tracking data.

    This is the primary tool for writing chapters. It creates the chapter content
    and simultaneously updates timeline, foreshadowings, and style stats.
    Use this when the user asks to write a chapter.

    Args:
        chapter_number: Chapter number (e.g., 1)
        chapter_title: Chapter title (e.g., "星辰陨落")
        content: Full chapter text content
        summary: One-sentence chapter summary for the timeline
        word_count: Word/character count of this chapter
        status: Chapter status - "draft" or "complete"
        scene_count: Number of scenes in this chapter
        new_foreshadowings: JSON string list of new foreshadowings planted in this chapter.
                           Each: {"content": "...", "level": "hint", "expected_resolve_chapter": N, "related_characters": ["..."]}
        reclaimed_foreshadowing_ids: JSON string list of foreshadowing IDs reclaimed in this chapter
        timeline_summary: Summary entry for the timeline (format: "第X章：[摘要] → [因果链]")
        rhythm_score: Rhythm score 1-5 (1=slow, 5=frantic)
        tension_score: Tension score 1-5 (1=relaxed, 5=peak)
        emotion_score: Emotion score 1-5
        emotion_tag: Emotion tag (e.g., "紧张", "舒缓", "悲伤", "温暖", "转折", "日常")
    """
    import json as _json
    from app.database import SessionLocal
    from app.models.chapter import Chapter
    from app.models.outline import ChapterOutline
    from app.models.timeline import TimelineEntry

    try:
        new_fs = _json.loads(new_foreshadowings) if isinstance(new_foreshadowings, str) else new_foreshadowings
    except _json.JSONDecodeError:
        new_fs = []

    try:
        reclaimed_ids = _json.loads(reclaimed_foreshadowing_ids) if isinstance(reclaimed_foreshadowing_ids, str) else reclaimed_foreshadowing_ids
    except _json.JSONDecodeError:
        reclaimed_ids = []

    project_id = get_project_id()
    kb = _kb()
    db = SessionLocal()
    committed = False

    try:
        # 1. Find or create ChapterOutline (required foreign key for Chapter)
        chapter_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number
        ).first()

        if not chapter_outline:
            chapter_outline = ChapterOutline(
                project_id=project_id,
                chapter_number=chapter_number,
                title=chapter_title,
            )
            db.add(chapter_outline)
            db.flush()

        # 2. Create or update the Chapter
        existing_chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == chapter_outline.id
        ).first()

        if existing_chapter:
            existing_chapter.content = content
            if summary:
                existing_chapter.summary = summary
            if word_count:
                existing_chapter.word_count = word_count
        else:
            chapter = Chapter(
                chapter_outline_id=chapter_outline.id,
                content=content,
                summary=summary or "",
                word_count=word_count or len(content),
            )
            db.add(chapter)

        # 3. Create timeline entry (via KnowledgeBaseService for consistency)
        if timeline_summary:
            timeline = TimelineEntry(
                project_id=project_id,
                chapter_number=chapter_number,
                summary=timeline_summary or summary or "",
                causal_chain="",
                rhythm_score=rhythm_score,
                tension_score=tension_score,
                emotion_score=emotion_score,
                emotion_tag=emotion_tag or "",
            )
            db.add(timeline)

        # 4. Create new foreshadowings via KB service (handles its own session)
        created_fs = []
        for fs_data in new_fs:
            f = kb.create_foreshadowing({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f.id, "content": f.content[:60]})

        # 5. Reclaim foreshadowings via KB service
        for fs_id in reclaimed_ids:
            kb.update_foreshadowing(fs_id, {"status": "reclaimed"})

        db.commit()
        committed = True

        return {
            "action": "created" if not existing_chapter else "updated",
            "chapter_number": chapter_number,
            "title": chapter_title,
            "word_count": word_count or len(content),
            "timeline_entry": bool(timeline_summary),
            "new_foreshadowings": len(created_fs),
            "reclaimed_foreshadowings": len(reclaimed_ids),
            "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass
