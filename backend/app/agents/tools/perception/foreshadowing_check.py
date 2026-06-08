"""伏笔状态检查工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def foreshadowing_check(current_chapter: int | None = None) -> dict:
    """Check foreshadowing status — active, pending reclaim, overdue.

    Use when the user asks about foreshadowing health, which foreshadowings
    haven't been reclaimed, or whether any are overdue.

    Args:
        current_chapter: Current chapter number (for overdue calculation).
                         If not provided, no overdue check is performed.
    """
    kb = _kb()

    active = kb.get_foreshadowings(status="active")
    pending = kb.get_pending_foreshadowings()
    overdue = []
    if current_chapter:
        overdue = kb.get_overdue_foreshadowings(current_chapter)

    result = {
        "active_count": len(active),
        "pending_reclaim_count": len(pending),
        "overdue_count": len(overdue),
        "active": [
            {"id": f.id, "content": f.content[:80], "planted_chapter": f.planted_chapter, "level": f.level}
            for f in active
        ],
        "pending_reclaim": [
            {"id": f.id, "content": f.content[:80], "expected_resolve_chapter": f.expected_resolve_chapter}
            for f in pending
        ],
        "overdue": [
            {
                "id": f.id,
                "content": f.content[:80],
                "expected_resolve_chapter": f.expected_resolve_chapter,
                "overdue_by": current_chapter - f.expected_resolve_chapter
                if current_chapter and f.expected_resolve_chapter else 0,
            }
            for f in overdue
        ],
    }

    if overdue:
        result["warning"] = f"有 {len(overdue)} 个伏笔已超过预期回收章节"
    return result
