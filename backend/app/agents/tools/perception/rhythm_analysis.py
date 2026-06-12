"""节奏分析工具

B4 增强：高潮/低谷分布 + 情节块预期节奏对比。
Store 返回 dict。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _mood_to_tension


@tool
async def rhythm_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze story rhythm — tension, emotion, pacing trends.

    Use when the user asks about pacing, whether recent chapters
    feel flat, or whether the rhythm curve is monotone.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    timeline = kb.timelines.list_timeline()
    recent = timeline[:last_n_chapters] if timeline else []

    if not recent:
        return {"has_data": False, "message": "尚无时间线数据，需要先写几章后才能分析节奏"}

    # 检测单调段
    monotone_sections = []
    consecutive_same = 0
    last_tag = None
    start_chapter = None

    for entry in reversed(recent):
        tag = entry.get("emotion_tag")
        if tag and tag == last_tag:
            consecutive_same += 1
            if consecutive_same >= 2:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": entry.get("chapter_number"),
                    "emotion": tag,
                    "length": consecutive_same + 1,
                })
        else:
            consecutive_same = 0
            start_chapter = entry.get("chapter_number")
        last_tag = tag

    # 高潮/低谷分布
    peaks = []
    valleys = []
    for t in recent:
        tension = t.get("tension_score")
        if tension is not None:
            if tension >= 4:
                peaks.append({"chapter": t.get("chapter_number"), "tension": tension, "emotion_tag": t.get("emotion_tag")})
            elif tension <= 2:
                valleys.append({"chapter": t.get("chapter_number"), "tension": tension, "emotion_tag": t.get("emotion_tag")})

    # 情节块预期节奏对比
    block_warnings = []
    for t in recent:
        ch_num = t.get("chapter_number")
        if ch_num:
            block = kb.plots.get_current_plot_block(ch_num)
            if block and block.get("expected_mood"):
                expected_tension = _mood_to_tension(block["expected_mood"])
                actual_tension = t.get("tension_score") or 3
                deviation = abs(actual_tension - expected_tension)
                if deviation > 1:
                    block_warnings.append({
                        "chapter": ch_num,
                        "block_title": block.get("title"),
                        "expected_mood": block.get("expected_mood"),
                        "expected_tension": expected_tension,
                        "actual_tension": actual_tension,
                        "deviation": deviation,
                    })

    result = {
        "has_data": True,
        "chapters_analyzed": len(recent),
        "rhythm_curve": [
            {
                "chapter": t.get("chapter_number"),
                "rhythm_score": t.get("rhythm_score"),
                "tension_score": t.get("tension_score"),
                "emotion_score": t.get("emotion_score"),
                "emotion_tag": t.get("emotion_tag"),
            }
            for t in reversed(recent)
        ],
        "monotone_sections": monotone_sections,
        "average_tension": round(
            sum(t.get("tension_score", 0) or 0 for t in recent) / max(len(recent), 1), 1
        ),
        "peaks": peaks,
        "valleys": valleys,
        "block_deviation_warnings": block_warnings,
    }

    if monotone_sections:
        result["warning"] = f"检测到 {len(monotone_sections)} 段节奏单调区域，建议调整情绪节奏"
    elif block_warnings:
        result["warning"] = f"检测到 {len(block_warnings)} 处节奏与预期偏差过大"
    return result
