"""创建/更新伏笔工具

合并原 create_foreshadowing 和 update_foreshadowing。
支持三种模式: 创建、单条更新、批量更新。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff, parse_json_param


@tool
async def create_foreshadowing(
    foreshadowing_id: int = 0,
    foreshadowing_ids: str = "",
    content: str | None = None,
    level: str | None = None,
    planted_chapter: int | None = None,
    expected_resolve_chapter: int | None = None,
    related_characters: str | None = None,
    status: str | None = None,
    appearance_count: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """创建新伏笔或更新已有伏笔. 支持 single/batch 更新模式.

    - foreshadowing_id=0 且 foreshadowing_ids 为空: 创建新伏笔(content 必填)
    - foreshadowing_id>0: 单条更新模式
    - foreshadowing_ids 非空: 批量更新模式

    不能同时提供 foreshadowing_id 和 foreshadowing_ids.

    Args:
        foreshadowing_id: 伏笔 ID(非零时单条更新)
        foreshadowing_ids: JSON 字符串列表, 伏笔 ID 列表(批量模式, 如 "[1,3,5]")
        content: 伏笔内容描述(create 路径必填)
        level: 等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)
        planted_chapter: 埋设伏笔的章节号
        expected_resolve_chapter: 预期回收伏笔的章节号
        related_characters: JSON 字符串列表, 关联角色名
        status: 新状态 - "active", "pending_reclaim", "reclaimed"(仅更新路径)
        appearance_count: 出现次数(仅更新路径)
        resolved_chapter: 实际回收章节号(仅更新路径)
    """
    kb = _kb()

    # 解析 foreshadowing_ids(提前解析, 用于冲突检查和模式判断)
    parsed_ids = None
    if foreshadowing_ids:
        parsed_ids, ids_warn = parse_json_param(foreshadowing_ids, [], "foreshadowing_ids")
        if ids_warn:
            return {"error": f"foreshadowing_ids 参数解析失败: {ids_warn}"}

    # 双参数冲突检查
    if foreshadowing_id and parsed_ids:
        return {"error": "不能同时提供 foreshadowing_id 和 foreshadowing_ids, 请选择单条或批量模式"}

    # 批量模式
    if parsed_ids:
        return _batch_update(kb, parsed_ids, status, resolved_chapter)

    # 单条更新模式
    if foreshadowing_id:
        before = kb.foreshadowings.get(foreshadowing_id)
        if not before:
            return {"error": f"伏笔 ID {foreshadowing_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "content", "level", "planted_chapter",
            "expected_resolve_chapter", "status",
            "appearance_count", "resolved_chapter",
        )
        update_data = {}
        for k in _UPDATABLE_FIELDS:
            v = locals()[k]
            if v is not None:
                if k == "related_characters":
                    parsed, _ = parse_json_param(v, [], "related_characters")
                    update_data[k] = parsed
                else:
                    update_data[k] = v

        if not update_data:
            return {"message": "无字段需要更新", "foreshadowing_id": foreshadowing_id}

        updated = kb.foreshadowings.update(foreshadowing_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "foreshadowing_id": foreshadowing_id,
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"伏笔 {foreshadowing_id} 已更新（{', '.join(changes.keys())}）",
        }

    # 创建模式
    if not content:
        return {"error": "创建伏笔时 content 为必填字段"}

    characters, _ = parse_json_param(related_characters or "[]", [], "related_characters")

    data = {
        "content": content,
        "level": level or "hint",
        "related_characters": characters,
    }
    if planted_chapter is not None:
        data["planted_chapter"] = planted_chapter
    if expected_resolve_chapter is not None:
        data["expected_resolve_chapter"] = expected_resolve_chapter

    f = kb.foreshadowings.create(data)
    return {
        "action": "created",
        "id": f["id"],
        "content": content[:80],
        "level": level or "hint",
        "message": "伏笔已创建并写入知识库",
    }


def _batch_update(kb, ids: list, status: str | None, resolved_chapter: int | None) -> dict:
    """批量更新伏笔状态"""
    if not ids:
        return {"error": "foreshadowing_ids 不能为空"}

    if not status:
        return {"error": "批量模式必须提供 status 参数"}

    valid_statuses = {"active", "pending_reclaim", "reclaimed"}
    if status not in valid_statuses:
        return {"error": f"status 必须是 {valid_statuses} 之一, 收到: {status}"}

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
