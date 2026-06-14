"""更新支线状态工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_subplot(
    subplot_id: int,
    title: str | None = None,
    status: str | None = None,
    resolution: str | None = None,
) -> dict:
    """更新支线的状态或属性。用于推进支线进展或标记完结。

    Args:
        subplot_id: 支线 ID
        title: 支线标题
        status: 新状态 - "active"(进行中), "resolved"(已解决), "abandoned"(已放弃)
        resolution: 解决说明（标记 resolved 时建议提供）
    """
    kb = _kb()

    # 通过 Store 层获取当前值
    subplots = kb.plots.list_subplots()
    before = None
    for s in subplots:
        if s["id"] == subplot_id:
            before = s
            break

    if not before:
        return {"error": f"支线 ID {subplot_id} 不存在"}

    update_data = {}
    for field in ("title", "status", "resolution"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "subplot_id": subplot_id}

    updated = kb.plots.update_subplot(subplot_id, update_data)

    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}

    return {
        "subplot_id": subplot_id,
        "title": updated.get("title", before.get("title")),
        "updated_fields": list(changes.keys()),
        "changes": changes,
        "message": f"支线「{updated.get('title', before.get('title'))}」已更新",
    }
