"""节奏分析工具

B4 增强：高潮/低谷分布 + 情节块预期节奏对比。
Store 返回 dict。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, _mood_to_tension


@tool
async def rhythm_analysis(last_n_chapters: int = 10) -> dict:
    """分析故事节奏——张力、情绪、步调趋势。

    当用户询问节奏是否单调、最近章节是否平淡、或节奏曲线是否单调时使用。
    返回节奏曲线、单调段检测、高潮/低谷分布，并提供可操作性建议。

    Args:
        last_n_chapters: 分析最近多少章的节奏（默认 10）
    """
    kb = _kb()
    timeline = kb.timelines.list_timeline()
    recent = timeline[:last_n_chapters] if timeline else []

    if not recent:
        return {"has_data": False, "message": "尚无时间线数据，需要先写几章后才能分析节奏"}

    # 检测单调段（正序遍历，只在序列结束时记录一次）
    monotone_sections = []
    consecutive_same = 1
    start_chapter = None
    last_tag = None
    prev_chapter = None

    for entry in recent:
        tag = entry.get("emotion_tag")
        if tag and tag == last_tag:
            consecutive_same += 1
        else:
            # 检测到断点，记录之前的单调段
            if consecutive_same >= 3 and last_tag:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": prev_chapter,
                    "emotion": last_tag,
                    "length": consecutive_same,
                })
            # 开始新序列
            consecutive_same = 1
            start_chapter = entry.get("chapter_number")
        prev_chapter = entry.get("chapter_number")
        last_tag = tag

    # 检查最后一段
    if consecutive_same >= 3 and last_tag:
        monotone_sections.append({
            "start_chapter": start_chapter,
            "end_chapter": prev_chapter,
            "emotion": last_tag,
            "length": consecutive_same,
        })

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

    # 生成可操作性建议
    suggested_adjustments = []
    for section in monotone_sections:
        suggested_adjustments.append({
            "type": "单调段打破",
            "chapters": f"{section.get('start_chapter', '?')}-{section.get('end_chapter', '?')}",
            "suggestion": f"建议在第{section.get('end_chapter', '?')}章后加入冲突或转折事件打破连续「{section.get('emotion', '相同')}」节奏",
        })
    for bw in block_warnings:
        suggested_adjustments.append({
            "type": "节奏偏差",
            "chapter": bw.get("chapter"),
            "suggestion": f"情节块「{bw.get('block_title', '')}」预期「{bw.get('expected_mood', '')}」但实际张力{bw.get('actual_tension')}分，建议{'增加紧迫感事件' if bw.get('actual_tension', 3) < bw.get('expected_tension', 3) else '适当放缓节奏'}",
        })
    if suggested_adjustments:
        result["suggested_adjustments"] = suggested_adjustments

    if monotone_sections:
        result["warning"] = f"检测到 {len(monotone_sections)} 段节奏单调区域（3+章相同情绪），建议调整情绪节奏"
    elif block_warnings:
        result["warning"] = f"检测到 {len(block_warnings)} 处节奏与预期偏差过大"
    return result
