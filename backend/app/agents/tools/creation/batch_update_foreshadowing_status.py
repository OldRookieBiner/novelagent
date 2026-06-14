"""批量更新伏笔状态工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def batch_update_foreshadowing_status(
    foreshadowing_ids: str,
    new_status: str,
    resolved_chapter: int | None = None,
) -> dict:
    """批量更新伏笔状态。适合在章节完成后一次回收多个伏笔。

    Args:
        foreshadowing_ids: JSON 字符串列表，伏笔 ID 列表（如 "[1,3,5]"）
        new_status: 新状态 - "active", "pending_reclaim", "reclaimed"
        resolved_chapter: 实际回收章节号（当 new_status="reclaimed" 时建议提供）
    """
    kb = _kb()

    ids, warn = parse_json_param(foreshadowing_ids, [], "foreshadowing_ids")
    if warn:
        return {"error": f"foreshadowing_ids 参数解析失败: {warn}"}

    if not ids:
        return {"error": "foreshadowing_ids 不能为空"}

    valid_statuses = {"active", "pending_reclaim", "reclaimed"}
    if new_status not in valid_statuses:
        return {"error": f"new_status 必须是 {valid_statuses} 之一，收到: {new_status}"}

    updated = []
    not_found = []
    errors = []

    update_data = {"status": new_status}
    if new_status == "reclaimed" and resolved_chapter:
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
        "new_status": new_status,
        "message": f"已将 {len(updated)} 个伏笔状态更新为「{new_status}」" if updated else "没有伏笔被更新",
    }
