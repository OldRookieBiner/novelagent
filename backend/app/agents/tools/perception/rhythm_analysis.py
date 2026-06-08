"""节奏分析工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def rhythm_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze story rhythm — tension, emotion, pacing trends.

    Use when the user asks about pacing, whether recent chapters
    feel flat, or whether the rhythm curve is monotone.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    timeline = kb.get_timeline()
    recent = timeline[:last_n_chapters] if timeline else []

    if not recent:
        return {"has_data": False, "message": "尚无时间线数据，需要先写几章后才能分析节奏"}

    # Detect monotone sections: 3+ consecutive chapters with same emotion_tag
    monotone_sections = []
    consecutive_same = 0
    last_tag = None
    start_chapter = None
    last_tag_chapter = None

    for entry in reversed(recent):  # timeline is ordered desc
        tag = entry.emotion_tag
        if tag == last_tag and tag:
            consecutive_same += 1
            if consecutive_same >= 3:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": entry.chapter_number,
                    "emotion": tag,
                    "length": consecutive_same + 1,
                })
        else:
            consecutive_same = 0
            start_chapter = entry.chapter_number
        last_tag = tag
        last_tag_chapter = entry.chapter_number

    result = {
        "has_data": True,
        "chapters_analyzed": len(recent),
        "rhythm_curve": [
            {
                "chapter": t.chapter_number,
                "rhythm_score": t.rhythm_score,
                "tension_score": t.tension_score,
                "emotion_score": t.emotion_score,
                "emotion_tag": t.emotion_tag,
            }
            for t in reversed(recent)
        ],
        "monotone_sections": monotone_sections,
        "average_tension": round(
            sum(t.tension_score for t in recent if t.tension_score) / max(len(recent), 1), 1
        ),
    }

    if monotone_sections:
        result["warning"] = f"检测到 {len(monotone_sections)} 段节奏单调区域，建议调整情绪节奏"
    return result
