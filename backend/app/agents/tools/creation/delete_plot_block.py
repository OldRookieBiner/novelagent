"""删除空情节块工具

R16 修正：安全检查——有未回答问题拒绝删除，已回答问题可断开关联。
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def delete_plot_block(plot_block_id: int) -> dict:
    """删除空情节块。如果有未回答的问题（status=pending），拒绝删除并提示先回答或迁移。

    Args:
        plot_block_id: 情节块 ID
    """
    kb = _kb()

    # 通过 Store 层获取情节块
    blocks = kb.plots.list_plot_blocks()
    target = None
    for b in blocks:
        if b["id"] == plot_block_id:
            target = b
            break

    if not target:
        return {"error": f"情节块 ID {plot_block_id} 不存在"}

    # 安全检查：是否有未回答的问题（通过 Store 层查询，含 project_id 过滤）
    all_questions = kb.plots.list_plot_questions(status="pending")
    pending_questions = [q for q in all_questions if q.get("plot_block_id") == plot_block_id]

    if pending_questions:
        question_ids = [q["id"] for q in pending_questions]
        return {
            "error": f"情节块「{target.get('title', '')}」下有 {len(pending_questions)} 个未回答的问题，请先回答或迁移后再删除",
            "pending_question_ids": question_ids,
            "hint": "使用 update_plot_question 工具将问题标记为已回答，或将问题迁移到其他情节块",
        }

    # 安全检查：是否有活跃伏笔的预期回收章节在此范围内
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active_fs = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]
    chapter_start = target.get("chapter_start")
    chapter_end = target.get("chapter_end")
    affected_foreshadowings = []
    if chapter_start is not None and chapter_end is not None:
        for f in active_fs:
            expected = f.get("expected_resolve_chapter")
            if expected and chapter_start <= expected <= chapter_end:
                affected_foreshadowings.append({"id": f["id"], "content": (f.get("content") or "")[:60]})

    # 执行删除
    kb.plots.delete_plot_block(plot_block_id)

    result = {
        "deleted_plot_block_id": plot_block_id,
        "title": target.get("title", ""),
        "message": f"情节块「{target.get('title', '')}」已删除",
    }
    if affected_foreshadowings:
        result["affected_foreshadowings"] = affected_foreshadowings
        result["foreshadowing_note"] = f"此情节块范围内有 {len(affected_foreshadowings)} 个活跃伏笔的预期回收章节，删除后请确认伏笔仍能被回收"
    return result
