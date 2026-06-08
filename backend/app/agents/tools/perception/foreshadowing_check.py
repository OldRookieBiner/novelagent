"""伏笔状态检查工具

B2 增强：新增健康度评分 + 回收建议。
"""

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

    # B2 增强：健康度评分
    health_score = 100
    overdue_deduction = min(len(overdue) * 15, 60)
    pending_deduction = min(max(len(pending) - 3, 0) * 5, 20)
    health_score = max(health_score - overdue_deduction - pending_deduction, 0)

    result["health_score"] = health_score
    if health_score >= 80:
        result["health_label"] = "🟢 健康"
    elif health_score >= 50:
        result["health_label"] = "🟡 需关注"
    else:
        result["health_label"] = "🔴 需紧急处理"

    # B2 增强：超期伏笔回收建议
    if overdue:
        suggestions = []
        for f in overdue:
            suggested_method = "强化暗示" if f.level == "hint" else "推进揭示"
            suggested_chapter = (current_chapter or 1) + 1 if current_chapter else None
            suggestions.append({
                "id": f.id,
                "content": f.content[:80],
                "suggested_method": suggested_method,
                "suggested_chapter": suggested_chapter,
            })
        result["recovery_suggestions"] = suggestions

    if overdue:
        result["warning"] = f"有 {len(overdue)} 个伏笔已超过预期回收章节"
    return result
