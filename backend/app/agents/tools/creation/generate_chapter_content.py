"""生成章节内容工具"""

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb, parse_json_param


def _compute_style_snapshot(content: str) -> dict:
    """从章节文本计算风格统计指标"""
    import re as _re

    if not content or not content.strip():
        return {
            "paragraph_count": 0,
            "avg_paragraph_length": 0.0,
            "dialogue_ratio": 0.0,
            "avg_sentence_length": 0.0,
        }

    total_chars = len(content)
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    paragraph_count = len(paragraphs) if paragraphs else 1
    avg_paragraph_length = sum(len(p) for p in paragraphs) / paragraph_count

    dialogue_chars = 0
    for m in _re.finditer(r"「([^」]*)」", content):
        dialogue_chars += len(m.group(1))
    for m in _re.finditer(r"\u201c([^\u201d]*)\u201d", content):
        dialogue_chars += len(m.group(1))
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

    sentence_ends = _re.split(r"[。！？…]+", content)
    sentences = [s for s in sentence_ends if s.strip()]
    avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0.0

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

    Args:
        chapter_number: Chapter number (e.g., 1)
        chapter_title: Chapter title
        content: Full chapter text content
        summary: One-sentence chapter summary
        word_count: Word/character count
        status: Chapter status - "draft" or "complete"
        scene_count: Number of scenes
        new_foreshadowings: JSON string list of new foreshadowings
        reclaimed_foreshadowing_ids: JSON string list of reclaimed foreshadowing IDs
        timeline_summary: Summary entry for the timeline
        rhythm_score: Rhythm score 1-5
        tension_score: Tension score 1-5
        emotion_score: Emotion score 1-5
        emotion_tag: Emotion tag
    """
    from app.agents.services.knowledge_base import KnowledgeBaseService

    new_fs, new_fs_warn = parse_json_param(new_foreshadowings, [], "new_foreshadowings")

    reclaimed_ids, reclaimed_ids_warn = parse_json_param(reclaimed_foreshadowing_ids, [], "reclaimed_foreshadowing_ids")

    project_id = get_project_id()
    kb = KnowledgeBaseService(project_id)

    # 检查当前章是否有已确认的大纲
    try:
        co = kb.outlines.get_chapter_outline(chapter_number)
        if co and not co.get("confirmed"):
            return {
                "error": f"第{chapter_number}章大纲尚未确认，请先审查并确认章节大纲后再写作",
                "hint": "使用 generate_chapter_outline 工具生成大纲，或提醒用户确认大纲",
            }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("大纲确认状态检查失败: %s", e)

    # 1. 保存章节正文（通过 OutlineStore 确保 ChapterOutline 存在，然后 ChapterStore 保存）
    # 如果大纲不存在，先创建
    existing_co = kb.outlines.get_chapter_outline(chapter_number)
    if not existing_co:
        kb.outlines.create_chapter_outline({
            "chapter_number": chapter_number,
            "title": chapter_title,
        })

    chapter_result = kb.chapters.save_content(chapter_number, content, word_count or len(content))
    existing_chapter = chapter_result.get("id") is not None

    # 2. 时间线
    timeline_created = False
    if timeline_summary:
        try:
            kb.timelines.create_timeline_entry({
                "chapter_number": chapter_number,
                "summary": timeline_summary or summary or "",
                "causal_chain": "",
                "rhythm_score": rhythm_score,
                "tension_score": tension_score,
                "emotion_score": emotion_score,
                "emotion_tag": emotion_tag or "",
            })
            timeline_created = True
        except Exception:
            pass

    # 3. 创建新伏笔
    created_fs = []
    for fs_data in new_fs:
        try:
            f = kb.foreshadowings.create({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f["id"], "content": (f.get("content") or "")[:60]})
        except Exception:
            pass

    # 4. 回收伏笔
    for fs_id in reclaimed_ids:
        try:
            kb.foreshadowings.update(fs_id, {"status": "reclaimed"})
        except Exception:
            pass

    # 5. 风格快照
    style_snapshot_created = False
    if content and content.strip():
        try:
            snapshot_data = _compute_style_snapshot(content)
            snapshot_data["chapter_number"] = chapter_number
            kb.styles.create_snapshot(snapshot_data)
            style_snapshot_created = True
        except Exception:
            pass

    return {
        "action": "created" if not existing_chapter else "updated",
        "chapter_number": chapter_number,
        "title": chapter_title,
        "word_count": word_count or len(content),
        "timeline_entry": timeline_created,
        "new_foreshadowings": len(created_fs),
        "reclaimed_foreshadowings": len(reclaimed_ids),
        "style_snapshot_created": style_snapshot_created,
        "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
    }
