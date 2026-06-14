"""更新问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_plot_question(
    question_id: int,
    question: str | None = None,
    answer: str | None = None,
    status: str | None = None,
) -> dict:
    """更新问题链的问题状态。用于标记问题为已回答或补充答案。

    Args:
        question_id: 问题 ID
        question: 问题内容
        answer: 回答内容
        status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭)
    """
    kb = _kb()

    update_data = {}
    for field in ("question", "answer", "status"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    if not update_data:
        return {"message": "无字段需要更新", "question_id": question_id}

    updated = kb.plots.update_plot_question(question_id, update_data)

    return {
        "question_id": question_id,
        "updated_fields": list(update_data.keys()),
        "message": f"问题链 {question_id} 已更新",
    }
