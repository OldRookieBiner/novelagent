"""更新问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_plot_question(
    question_id: int,
    question_text: str | None = None,
    answered_in_chapter: int | None = None,
    status: str | None = None,
) -> dict:
    """更新问题链的问题状态。用于标记问题为已回答或补充答案。

    Args:
        question_id: 问题 ID
        question_text: 问题内容
        answered_in_chapter: 回答问题的章节号
        status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭)
    """
    kb = _kb()

    # 获取当前值用于对比
    all_questions = kb.plots.list_plot_questions()
    before = None
    for q in all_questions:
        if q["id"] == question_id:
            before = q
            break

    if not before:
        return {"error": f"问题链 ID {question_id} 不存在"}

    update_data = {}
    for field in ("question_text", "answered_in_chapter", "status"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "question_id": question_id}

    updated = kb.plots.update_plot_question(question_id, update_data)

    # 构建变更对比
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}

    return {
        "question_id": question_id,
        "updated_fields": list(changes.keys()),
        "changes": changes,
        "message": f"问题链 {question_id} 已更新（{', '.join(changes.keys())}）",
    }
