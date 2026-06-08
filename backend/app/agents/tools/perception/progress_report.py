"""进度报告工具

B6 增强：完稿时间预估 + 里程碑提醒。
完稿预估附带置信度标注，提醒用户这是粗略估算。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def progress_report() -> dict:
    """Generate a writing progress report.

    Use when the user asks how far they've gotten, what's been written,
    what's left, or the overall status of the novel.
    """
    kb = _kb()

    outline = kb.get_outline()
    chars = kb.get_characters()
    foreshadowings = kb.get_foreshadowings()
    timeline = kb.get_timeline()
    blocks = kb.get_plot_blocks()

    written_chapters = len(timeline) if timeline else 0
    total_chapters = 0
    if outline:
        total_chapters = outline.chapter_count_confirmed or outline.chapter_count_suggested or 0

    active_foreshadowings = [f for f in foreshadowings if f.status in ("active", "pending_reclaim")]
    reclaimed = [f for f in foreshadowings if f.status == "reclaimed"]

    progress_percent = round(written_chapters / total_chapters * 100, 1) if total_chapters else 0

    result = {
        "total_planned_chapters": total_chapters,
        "chapters_written": written_chapters,
        "progress_percent": progress_percent,
        "characters_count": len(chars),
        "foreshadowings_active": len(active_foreshadowings),
        "foreshadowings_reclaimed": len(reclaimed),
        "plot_blocks_total": len(blocks),
        "plot_blocks_completed": len([b for b in blocks if b.completion_summary]),
    }

    if outline:
        result["title"] = outline.title or "未命名"
        result["summary"] = (outline.summary or "")[:200]

    # B6 增强：完稿时间预估（附带置信度标注）
    if timeline and len(timeline) >= 2 and total_chapters > 0:
        recent_entries = timeline[:min(3, len(timeline))]
        if len(recent_entries) >= 2:
            dates = [t.created_at for t in recent_entries if t.created_at]
            if len(dates) >= 2:
                dates.sort(reverse=True)
                span_days = (dates[0] - dates[-1]).days + 1
                chapters_in_span = len(recent_entries)
                if span_days > 0 and chapters_in_span > 0:
                    speed = chapters_in_span / span_days
                    remaining = total_chapters - written_chapters
                    if remaining > 0 and speed > 0:
                        estimated_days = round(remaining / speed, 1)
                        # 根据样本量和跨度确定置信度
                        confidence = "低"
                        if span_days >= 7 and chapters_in_span >= 3:
                            confidence = "中"
                        if span_days >= 14 and chapters_in_span >= 5:
                            confidence = "高"
                        result["completion_estimate"] = {
                            "speed_chapters_per_day": round(speed, 2),
                            "remaining_chapters": remaining,
                            "estimated_days": estimated_days,
                            "confidence": confidence,
                            "note": f"基于最近 {chapters_in_span} 章、{span_days} 天写作节奏的粗略估算，置信度：{confidence}",
                        }

    # B6 增强：里程碑提醒
    milestones = []
    milestone_thresholds = [10, 50, 90]
    for threshold in milestone_thresholds:
        if progress_percent >= threshold:
            milestones.append({"percent": threshold, "status": "reached"})
        elif progress_percent >= threshold - 5:
            milestones.append({"percent": threshold, "status": "approaching", "remaining_percent": round(threshold - progress_percent, 1)})
    if milestones:
        result["milestones"] = milestones

    return result
