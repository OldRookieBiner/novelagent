"""更新伏笔状态工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_foreshadowing(
    foreshadowing_id: int,
    level: str | None = None,
    status: str | None = None,
    content: str | None = None,
    appearance_count: int | None = None,
    expected_resolve_chapter: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。用于推进伏笔等级或标记回收。

    Args:
        foreshadowing_id: 伏笔 ID
        level: 新等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)
        status: 新状态 - "active", "pending_reclaim", "reclaimed"
        content: 伏笔内容
        appearance_count: 出现次数（用于判断升级：>=2 且 hint→strengthened）
        expected_resolve_chapter: 预期回收章节号
        resolved_chapter: 实际回收章节号
    """
    kb = _kb()

    # 获取当前值
    before = kb.foreshadowings.get(foreshadowing_id)
    if not before:
        return {"error": f"伏笔 ID {foreshadowing_id} 不存在"}

    update_data = {}
    for field in ("level", "status", "content", "appearance_count",
                  "expected_resolve_chapter", "resolved_chapter"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "foreshadowing_id": foreshadowing_id}

    updated = kb.foreshadowings.update(foreshadowing_id, update_data)

    # 构建变更对比
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}

    return {
        "foreshadowing_id": foreshadowing_id,
        "updated_fields": list(changes.keys()),
        "changes": changes,
        "message": f"伏笔 {foreshadowing_id} 已更新（{', '.join(changes.keys())}）",
    }
