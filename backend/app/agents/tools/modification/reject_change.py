"""拒绝变更提议工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def reject_change(change_id: int, reason: str = "") -> dict:
    """拒绝并关闭变更提议。

    当用户决定不采纳某个设定变更、大纲调整或章节重写提议时，
    使用此工具将变更标记为已拒绝。

    Args:
        change_id: 变更提议的 ID
        reason: 拒绝原因（可选）
    """
    kb = _kb()

    # 1. 获取变更记录
    change = kb.changes.get(change_id)
    if change is None:
        return {"error": f"变更 ID {change_id} 不存在"}

    # 2. 检查状态是否为 proposed
    if change.get("status") != "proposed":
        return {"error": f"变更状态为「{change.get('status')}」，只能拒绝 proposed 状态的变更"}

    # 3. 更新状态为 abandoned
    try:
        kb.changes.update(change_id, {
            "status": "abandoned",
            "author_decision": "reject",
            "rejection_reason": reason,
        })
        return {
            "action": "rejected",
            "change_id": change_id,
            "target_type": change.get("target_type"),
            "target_id": change.get("target_id"),
            "reason": reason,
            "message": f"变更 {change_id} 已拒绝",
        }
    except Exception as e:
        return {"error": f"变更拒绝失败: {str(e)}"}
