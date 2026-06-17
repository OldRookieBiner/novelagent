"""创建/更新支线工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff, parse_json_param


@tool
async def create_subplot(
    subplot_id: int = 0,
    name: str | None = None,
    characters: str | None = None,
    current_status: str | None = None,
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """创建新支线或更新已有支线. 提供 subplot_id 时为更新模式.

    - subplot_id=0(默认): 创建新支线(name 必填)
    - subplot_id>0: 更新指定 ID 的支线. None 表示不修改

    Args:
        subplot_id: 支线 ID(非零时更新已有支线)
        name: 支线名称
        characters: JSON 字符串列表, 参与角色名(create 路径默认 [], update 路径 None 不修改)
        current_status: 支线状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)
        raised_in_chapter: 支线提出的章节号
        planned_intersection_chapter: 计划与主线交汇的章节号
        expected_resolution_chapter: 预期解决的章节号
    """
    kb = _kb()

    if subplot_id:
        # --- 更新路径 ---
        before = kb.plots.get_subplot_by_id(subplot_id)
        if not before:
            return {"error": f"支线 ID {subplot_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "name", "current_status", "characters",
            "raised_in_chapter", "planned_intersection_chapter",
            "expected_resolution_chapter",
        )
        update_data = {}
        for k in _UPDATABLE_FIELDS:
            v = locals()[k]
            if v is not None:
                if k == "characters":
                    parsed, _ = parse_json_param(v, [], "characters")
                    update_data[k] = parsed
                else:
                    update_data[k] = v

        if not update_data:
            return {"message": "无字段需要更新", "subplot_id": subplot_id}

        updated = kb.plots.update_subplot(subplot_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "subplot_id": subplot_id,
            "name": updated.get("name", before.get("name")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"支线「{updated.get('name', before.get('name'))}」已更新",
        }
    else:
        # --- 创建路径 ---
        if not name:
            return {"error": "创建支线时 name 为必填字段"}

        chars, chars_warn = parse_json_param(characters or "[]", [], "characters")
        status = current_status or "developing"

        data = {"name": name, "characters": chars, "current_status": status}
        if raised_in_chapter is not None:
            data["raised_in_chapter"] = raised_in_chapter
        if planned_intersection_chapter is not None:
            data["planned_intersection_chapter"] = planned_intersection_chapter
        if expected_resolution_chapter is not None:
            data["expected_resolution_chapter"] = expected_resolution_chapter

        s = kb.plots.create_subplot(data)
        return {
            "action": "created",
            "id": s["id"],
            "name": name,
            "message": f"支线「{name}」已创建并写入知识库",
        }
