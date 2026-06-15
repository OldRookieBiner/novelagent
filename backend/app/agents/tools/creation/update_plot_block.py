"""更新情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def update_plot_block(
    plot_block_id: int,
    title: str | None = None,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    must_happen: str | None = None,
    questions_to_raise: str | None = None,
    questions_to_answer: str | None = None,
    completion_summary: str | None = None,
) -> dict:
    """更新已有情节块的范围或必须事件。None 表示不修改。

    Args:
        plot_block_id: 情节块 ID
        title: 情节块标题
        chapter_start: 起始章节号
        chapter_end: 结束章节号
        must_happen: JSON 字符串列表，必须发生的事件
        questions_to_raise: JSON 字符串列表，需要提出的问题
        questions_to_answer: JSON 字符串列表，需要回答的问题
        completion_summary: 完成总结
    """
    from app.agents.tools.utils import parse_json_param

    kb = _kb()

    # 获取当前值
    blocks = kb.plots.list_plot_blocks()
    before = None
    for b in blocks:
        if b["id"] == plot_block_id:
            before = b
            break

    if not before:
        return {"error": f"情节块 ID {plot_block_id} 不存在"}

    # 构建更新数据
    update_data = {}
    for field in ("title", "chapter_start", "chapter_end", "completion_summary"):
        value = locals()[field]
        if value is not None:
            update_data[field] = value

    # 处理 JSON 参数
    warnings = []
    if must_happen is not None:
        parsed, warn = parse_json_param(must_happen, [], "must_happen")
        update_data["must_happen"] = parsed
        if warn:
            warnings.append(warn)
    if questions_to_raise is not None:
        parsed, warn = parse_json_param(questions_to_raise, [], "questions_to_raise")
        update_data["questions_to_raise"] = parsed
        if warn:
            warnings.append(warn)
    if questions_to_answer is not None:
        parsed, warn = parse_json_param(questions_to_answer, [], "questions_to_answer")
        update_data["questions_to_answer"] = parsed
        if warn:
            warnings.append(warn)

    if not update_data:
        return {"message": "无字段需要更新", "plot_block_id": plot_block_id}

    updated = kb.plots.update_plot_block(plot_block_id, update_data)

    result = {
        "plot_block_id": plot_block_id,
        "title": updated.get("title", before.get("title")),
        "updated_fields": list(update_data.keys()),
        "message": f"情节块「{updated.get('title', before.get('title'))}」已更新",
    }
    if warnings:
        result["param_parse_warnings"] = warnings
    return result
