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
    """为章节创建时间线条目。

    当用户需要记录章节的关键时间线事件时使用。时间线帮助追踪情节的因果链和节奏。

    Args:
            chapter_number: 时间线条目对应的章节号
            summary: 本章关键事件的一句话摘要
            causal_chain: 因果链描述（什么导致了什么）
            rhythm_score: 节奏评分 1-5（1=缓慢，5=急促）
            tension_score: 张力评分 1-5（1=轻松，5=高潮）
            emotion_score: 情感评分 1-5
            emotion_tag: Emotion tag - one of: 紧张, 舒缓, 悲伤, 温暖, 转折, 日常
    """
    kb = _kb()

    # 去重检查：如果该章已有时间线条目，返回提示而非重复创建
    existing = kb.timelines.get_by_chapter_number(chapter_number)
    if existing:
        return {
            "action": "skipped",
            "chapter_number": chapter_number,
            "message": f"第{chapter_number}章已有时间线条目（ID: {existing['id']}），如需更新请使用 record_chapter_meta",
            "existing_id": existing["id"],
        }

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

    entry = kb.timelines.create_timeline_entry(data)
    return {
        "action": "created",
        "id": entry["id"],
        "chapter_number": chapter_number,
        "message": f"第{chapter_number}章时间线条目已创建",
    }
