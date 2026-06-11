"""生成章节内容工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb




def _compute_style_snapshot(content: str) -> dict:
    """从章节文本计算风格统计指标

    指标：
    - paragraph_count: 段落数（按空行分段，过滤空段）
    - avg_paragraph_length: 平均段落字符数
    - dialogue_ratio: 对话占比（「」和""内的文本长度 / 总长度）
    - avg_sentence_length: 平均句长（按句末标点分句后的字符数均值）
    """
    import re as _re

    if not content or not content.strip():
        return {
            "paragraph_count": 0,
            "avg_paragraph_length": 0.0,
            "dialogue_ratio": 0.0,
            "avg_sentence_length": 0.0,
        }

    total_chars = len(content)

    # 段落数：按 \n\n 分段，过滤空段
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    paragraph_count = len(paragraphs) if paragraphs else 1

    # 平均段长
    avg_paragraph_length = sum(len(p) for p in paragraphs) / paragraph_count

    # 对话占比：匹配「…」和"…"和"…"
    dialogue_chars = 0
    # 中文引号「…」
    for m in _re.finditer(r"「([^」]*)」", content):
        dialogue_chars += len(m.group(1))
    # 中文引号"…"（非贪婪，配对匹配）
    for m in _re.finditer(r"“([^”]*)”", content):
        dialogue_chars += len(m.group(1))
    # 直引号"…"（英文双引号配对）
    quote_open = False
    start = 0
    for i, ch in enumerate(content):
        if ch == '"':
            if not quote_open:
                quote_open = True
                start = i + 1
            else:
                dialogue_chars += len(content[start:i])
                quote_open = False

    dialogue_ratio = dialogue_chars / total_chars if total_chars > 0 else 0.0

    # 平均句长：按句末标点分句
    sentence_ends = _re.split(r"[。！？…]+", content)
    sentences = [s for s in sentence_ends if s.strip()]
    if sentences:
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
    else:
        avg_sentence_length = 0.0

    return {
        "paragraph_count": paragraph_count,
        "avg_paragraph_length": round(avg_paragraph_length, 1),
        "dialogue_ratio": round(dialogue_ratio, 3),
        "avg_sentence_length": round(avg_sentence_length, 1),
    }

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
        # 1. 找到或创建 ChapterOutline（Chapter 的必需外键）
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

        # 2. 创建或更新 Chapter
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

        # 3. 创建时间线条目
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

        # 先提交核心数据（Chapter + Timeline），确保主记录持久化
        db.commit()
        committed = True

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

    # 4. 通过 KB service 创建新伏笔（独立 session，在主记录持久化之后执行）
    created_fs = []
    for fs_data in new_fs:
        try:
            f = kb.create_foreshadowing({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f.id, "content": f.content[:60]})
        except Exception:
            pass  # 伏笔创建失败不影响章节主体

    # 5. 回收伏笔
    for fs_id in reclaimed_ids:
        try:
            kb.update_foreshadowing(fs_id, {"status": "reclaimed"})
        except Exception:
            pass

    # 6. 创建风格快照（独立 session，不影响章节主体）
    style_snapshot_created = False
    if content and content.strip():
        try:
            snapshot_data = _compute_style_snapshot(content)
            snapshot_data["chapter_number"] = chapter_number
            kb.create_style_snapshot(snapshot_data)
            style_snapshot_created = True
        except Exception:
            pass  # 快照创建失败不影响章节主体

    return {
        "action": "created" if not existing_chapter else "updated",
        "chapter_number": chapter_number,
        "title": chapter_title,
        "word_count": word_count or len(content),
        "timeline_entry": bool(timeline_summary),
        "new_foreshadowings": len(created_fs),
        "reclaimed_foreshadowings": len(reclaimed_ids),
        "style_snapshot_created": style_snapshot_created,
        "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
    }
