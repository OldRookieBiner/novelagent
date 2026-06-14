"""伏笔状态检查工具

B2 增强：新增健康度评分 + 回收建议。
Store 返回 dict，用 dict[key] 访问。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def foreshadowing_check(current_chapter: int | None = None) -> dict:
    """检查伏笔状态——活跃、待回收、超期。

    当用户需要了解伏笔的整体健康状况时使用。返回活跃伏笔数、待回收数、超期数和健康评分。

    Args:
            current_chapter: 当前章节号（用于超期计算）
                             If not provided, no overdue check is performed.
    """
    kb = _kb()

    active = kb.foreshadowings.list_foreshadowings(status="active")
    pending = kb.foreshadowings.list_pending()
    overdue = []
    if current_chapter:
        overdue = kb.foreshadowings.list_overdue(current_chapter)

    result = {
        "active_count": len(active),
        "pending_reclaim_count": len(pending),
        "overdue_count": len(overdue),
        "active": [
            {"id": f["id"], "content": (f.get("content") or "")[:80], "planted_chapter": f.get("planted_chapter"), "level": f.get("level")}
            for f in active
        ],
        "pending_reclaim": [
            {"id": f["id"], "content": (f.get("content") or "")[:80], "expected_resolve_chapter": f.get("expected_resolve_chapter")}
            for f in pending
        ],
        "overdue": [
            {
                "id": f["id"],
                "content": (f.get("content") or "")[:80],
                "expected_resolve_chapter": f.get("expected_resolve_chapter"),
                "overdue_by": current_chapter - f["expected_resolve_chapter"]
                if current_chapter and f.get("expected_resolve_chapter") else 0,
            }
            for f in overdue
        ],
    }

    # B2 增强：健康度评分
    outline = kb.outlines.get()
    total_chapters = 0
    if outline:
        total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0

    pending_tolerance = 3
    if total_chapters >= 50:
        pending_tolerance = 8
    elif total_chapters >= 30:
        pending_tolerance = 5

    health_score = 100
    overdue_deduction = min(len(overdue) * 15, 60)
    pending_deduction = min(max(len(pending) - pending_tolerance, 0) * 5, 20)
    health_score = max(health_score - overdue_deduction - pending_deduction, 0)

    result["health_score"] = health_score
    result["pending_tolerance"] = pending_tolerance
    if health_score >= 80:
        result["health_label"] = "🟢 健康"
    elif health_score >= 50:
        result["health_label"] = "🟡 需关注"
    else:
        result["health_label"] = "🔴 需紧急处理"

    # 超期伏笔回收建议
    if overdue:
        suggestions = []
        for f in overdue:
            suggested_method = "强化暗示" if f.get("level") == "hint" else "推进揭示"
            suggested_chapter = (current_chapter or 1) + 1 if current_chapter else None
            suggestions.append({
                "id": f["id"],
                "content": (f.get("content") or "")[:80],
                "suggested_method": suggested_method,
                "suggested_chapter": suggested_chapter,
            })
        result["recovery_suggestions"] = suggestions

    if overdue:
        result["warning"] = f"有 {len(overdue)} 个伏笔已超过预期回收章节"
    return result
