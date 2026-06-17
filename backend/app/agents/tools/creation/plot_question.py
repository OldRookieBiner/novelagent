"""创建/更新问题链工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff


@tool
async def create_plot_question(
    question_id: int = 0,
    question_text: str | None = None,
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
    answered_in_chapter: int | None = None,
    status: str | None = None,
) -> dict:
    """创建新问题或更新已有问题. 提供 question_id 时为更新模式.

    - question_id=0(默认): 创建新问题(question_text 必填)
    - question_id>0: 更新指定 ID 的问题. None 表示不修改

    Args:
        question_id: 问题 ID(非零时更新已有问题)
        question_text: 问题内容
        raised_in_chapter: 提出问题的章节号
        plot_block_id: 所属情节块 ID
        answered_in_chapter: 回答问题的章节号(仅更新路径)
        status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭, 仅更新路径)
    """
    kb = _kb()

    if question_id:
        # --- 更新路径 ---
        before = kb.plots.get_plot_question_by_id(question_id)
        if not before:
            return {"error": f"问题链 ID {question_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "question_text", "raised_in_chapter", "plot_block_id",
            "answered_in_chapter", "status",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "question_id": question_id}

        updated = kb.plots.update_plot_question(question_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "question_id": question_id,
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"问题链 {question_id} 已更新（{', '.join(changes.keys())}）",
        }
    else:
        # --- 创建路径 ---
        if not question_text:
            return {"error": "创建问题时 question_text 为必填字段"}

        data = {"question_text": question_text, "status": "pending"}
        if raised_in_chapter is not None:
            data["raised_in_chapter"] = raised_in_chapter
        if plot_block_id is not None:
            data["plot_block_id"] = plot_block_id

        q = kb.plots.create_plot_question(data)
        return {
            "action": "created",
            "id": q["id"],
            "question_text": question_text[:80],
            "message": f"问题「{question_text[:60]}」已创建并写入知识库",
        }
