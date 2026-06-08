"""进度报告工具"""

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

    result = {
        "total_planned_chapters": total_chapters,
        "chapters_written": written_chapters,
        "progress_percent": round(written_chapters / total_chapters * 100, 1) if total_chapters else 0,
        "characters_count": len(chars),
        "foreshadowings_active": len(active_foreshadowings),
        "foreshadowings_reclaimed": len(reclaimed),
        "plot_blocks_total": len(blocks),
        "plot_blocks_completed": len([b for b in blocks if b.completion_summary]),
    }

    if outline:
        result["title"] = outline.title or "未命名"
        result["summary"] = (outline.summary or "")[:200]

    return result
