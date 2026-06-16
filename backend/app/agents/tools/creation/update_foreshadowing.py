"""更新伏笔状态工具（合并版）

合并原 update_foreshadowing 和 batch_update_foreshadowing_status。
支持单条更新（foreshadowing_id）和批量更新（foreshadowing_ids）。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def update_foreshadowing(
    foreshadowing_id: int = 0,
    foreshadowing_ids: str = "",
    level: str | None = None,
    status: str | None = None,
    content: str | None = None,
    appearance_count: int | None = None,
    expected_resolve_chapter: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。支持单条和批量更新。

    - 提供foreshadowing_id时：更新单个伏笔
    - 提供foreshadowing_ids时：批量更新多个伏笔状态（如 "[1,3,5]"）

    Args:
        foreshadowing_id: 伏笔 ID（单条模式）
        foreshadowing_ids: JSON 字符串列表，伏笔 ID 列表（批量模式，如 "[1,3,5]"）
        level: 新等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)
        status: 新状态 - "active", "pending_reclaim", "reclaimed"
        content: 伏笔内容
        appearance_count: 出现次数
        expected_resolve_chapter: 预期回收章节号
        resolved_chapter: 实际回收章节号
    """
    kb = _kb()

    # 解析 foreshadowing_ids（提前解析，用于冲突检查和模式判断）
    parsed_ids = None
    if foreshadowing_ids:
        parsed_ids, ids_warn = parse_json_param(foreshadowing_ids, [], "foreshadowing_ids")
        if ids_warn:
            return {"error": f"foreshadowing_ids 参数解析失败: {ids_warn}"}

    # 双参数冲突检查：只有解析后的列表非空才算批量模式
    if foreshadowing_id and parsed_ids:
        return {"error": "不能同时提供 foreshadowing_id 和 foreshadowing_ids，请选择单条或批量模式"}

    # 批量模式
    if parsed_ids:
        return _batch_update(kb, parsed_ids, status, resolved_chapter)

    # 单条模式
    if not foreshadowing_id:
        return {"error": "需要提供 foreshadowing_id 或 foreshadowing_ids"}

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


def _batch_update(kb, ids: list, status: str | None, resolved_chapter: int | None) -> dict:
    """批量更新伏笔状态"""
    if not ids:
        return {"error": "foreshadowing_ids 不能为空"}

    if not status:
        return {"error": "批量模式必须提供 status 参数"}

    valid_statuses = {"active", "pending_reclaim", "reclaimed"}
    if status not in valid_statuses:
        return {"error": f"status 必须是 {valid_statuses} 之一，收到: {status}"}

    updated = []
    not_found = []
    errors = []

    update_data = {"status": status}
    if status == "reclaimed" and resolved_chapter:
        update_data["resolved_chapter"] = resolved_chapter

    for fs_id in ids:
        try:
            existing = kb.foreshadowings.get(fs_id)
            if not existing:
                not_found.append(fs_id)
            else:
                kb.foreshadowings.update(fs_id, update_data)
                updated.append(fs_id)
        except Exception as e:
            errors.append({"foreshadowing_id": fs_id, "error": str(e)})

    return {
        "updated": updated,
        "not_found": not_found,
        "errors": errors,
        "total_requested": len(ids),
        "total_updated": len(updated),
        "new_status": status,
        "message": f"已将 {len(updated)} 个伏笔状态更新为「{status}」" if updated else "没有伏笔被更新",
    }
