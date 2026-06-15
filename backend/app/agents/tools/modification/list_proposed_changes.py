"""列出待决策变更工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def list_proposed_changes(status: str = "proposed") -> dict:
    """列出知识库中的变更提议。

    当用户需要查看待处理、已通过或已拒绝的变更提议时使用。
    默认只显示 pending/pending_review/proposed 状态的变更。

    Args:
        status: 过滤的状态 - "proposed"(待决策), "applied"(已应用), "abandoned"(已拒绝), "all"(全部)
    """
    kb = _kb()

    if status == "all":
        changes = kb.changes.list_changes()
    else:
        changes = kb.changes.list_changes(status=status)

    if not changes:
        return {
            "found": False,
            "status": status,
            "message": f"没有找到状态为「{status}」的变更提议" if status != "all" else "暂无变更提议",
        }

    # 格式化输出
    formatted_changes = []
    for c in changes:
        target_type = c.get("target_type", "unknown")
        target_id = c.get("target_id", 0)
        change_desc = c.get("description", "")[:60]

        formatted_changes.append({
            "id": c.get("id"),
            "target_type": target_type,
            "target_id": target_id,
            "description": change_desc,
            "status": c.get("status"),
            "created_at": c.get("created_at"),
        })

    return {
        "found": True,
        "count": len(changes),
        "status": status,
        "changes": formatted_changes,
        "message": f"找到 {len(changes)} 个{('「' + status + '」') if status != 'all' else ''}变更提议",
    }
