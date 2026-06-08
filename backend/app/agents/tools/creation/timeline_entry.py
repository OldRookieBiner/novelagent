"""创建时间线条目工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_timeline_entry(
    chapter_number: int,
    summary: str,
    causal_chain: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
) -> dict:
    """Create a timeline entry for a chapter.

    Use when the user wants to manually add a timeline summary entry
    for a specific chapter. Timeline entries help the Agent track
    story progression across chapters.

    Args:
        chapter_number: Chapter number this entry refers to
        summary: One-sentence summary of key events in this chapter
        causal_chain: Causal chain description (what led to what)
        rhythm_score: Rhythm score 1-5 (1=slow, 5=frantic)
        tension_score: Tension score 1-5 (1=relaxed, 5=peak)
        emotion_score: Emotion score 1-5
        emotion_tag: Emotion tag - one of: 紧张, 舒缓, 悲伤, 温暖, 转折, 日常
    """
    kb = _kb()

    data = {"chapter_number": chapter_number, "summary": summary}
    if causal_chain:
        data["causal_chain"] = causal_chain
    if rhythm_score:
        data["rhythm_score"] = rhythm_score
    if tension_score:
        data["tension_score"] = tension_score
    if emotion_score:
        data["emotion_score"] = emotion_score
    if emotion_tag:
        data["emotion_tag"] = emotion_tag

    entry = kb.create_timeline_entry(data)
    return {
        "action": "created",
        "id": entry.id,
        "chapter_number": chapter_number,
        "message": f"第{chapter_number}章时间线条目已创建",
    }
