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

    # 获取当前值（通过 _read_all_with_session 获取全部后筛选）
    all_plots_data = kb.plots._read_all_with_session(None)
    subplots = all_plots_data.get("subplots", []) if all_plots_data else kb.plots.list_plot_blocks()
    before = None
    # 使用独立查询获取 subplots
    from app.database import SessionLocal
    from app.models.plot import Subplot
    db = SessionLocal()
    try:
        sp = db.query(Subplot).filter(Subplot.id == subplot_id).first()
        if sp:
            before = {
                "id": sp.id,
                "title": sp.title,
                "status": sp.status,
                "resolution": sp.resolution,
            }
    finally:
        db.close()

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
