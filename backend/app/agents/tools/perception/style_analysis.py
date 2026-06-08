"""风格分析工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def style_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze writing style trends and detect drift.

    Use when the user asks about style consistency, dialogue ratio,
    or whether recent chapters are drifting from the established style.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    snapshots = kb.get_style_snapshots(last_n=last_n_chapters)

    if not snapshots:
        return {"has_data": False, "message": "尚无风格统计数据，需要先写几章后才能分析"}

    avg_dialogue = sum(s.dialogue_ratio for s in snapshots if s.dialogue_ratio) / max(len(snapshots), 1)
    avg_sent_len = sum(s.avg_sentence_length for s in snapshots if s.avg_sentence_length) / max(len(snapshots), 1)
    avg_para_len = sum(s.avg_paragraph_length for s in snapshots if s.avg_paragraph_length) / max(len(snapshots), 1)

    drift = {}
    if len(snapshots) >= 3:
        recent_3 = snapshots[:3]
        recent_dialogue = sum(s.dialogue_ratio for s in recent_3) / 3
        recent_sent = sum(s.avg_sentence_length for s in recent_3) / 3

        if avg_dialogue > 0 and abs(recent_dialogue - avg_dialogue) / avg_dialogue > 0.25:
            drift["dialogue_ratio"] = {
                "overall_avg": round(avg_dialogue, 3),
                "recent_avg": round(recent_dialogue, 3),
                "direction": "偏高" if recent_dialogue > avg_dialogue else "偏低",
            }
        if avg_sent_len > 0 and abs(recent_sent - avg_sent_len) / avg_sent_len > 0.25:
            drift["sentence_length"] = {
                "overall_avg": round(avg_sent_len, 1),
                "recent_avg": round(recent_sent, 1),
                "direction": "偏长" if recent_sent > avg_sent_len else "偏短",
            }

    result = {
        "has_data": True,
        "overall_averages": {
            "dialogue_ratio": round(avg_dialogue, 3),
            "avg_sentence_length": round(avg_sent_len, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
        },
        "snapshots": [
            {
                "chapter": s.chapter_number,
                "dialogue_ratio": s.dialogue_ratio,
                "avg_sentence_length": s.avg_sentence_length,
                "paragraph_count": s.paragraph_count,
            }
            for s in snapshots
        ],
        "drift_detection": drift if drift else "风格稳定，未检测到漂移",
    }

    if drift:
        result["warning"] = "检测到风格漂移，建议检查最近几章的写作风格"
    return result
