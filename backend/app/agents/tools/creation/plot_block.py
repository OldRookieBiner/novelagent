"""创建/更新情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, build_changes_diff, parse_json_param


@tool
async def create_plot_block(
    plot_block_id: int = 0,
    title: str | None = None,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    must_happen: str | None = None,
    questions_to_raise: str | None = None,
    questions_to_answer: str | None = None,
    expected_mood: str | None = None,
    completion_summary: str | None = None,
) -> dict:
    """创建新情节块或更新已有情节块. 提供 plot_block_id 时为更新模式.

    - plot_block_id=0(默认): 创建新情节块(title, chapter_start, chapter_end 必填)
    - plot_block_id>0: 更新指定 ID 的情节块. None 表示不修改

    Args:
        plot_block_id: 情节块 ID(非零时更新已有情节块)
        title: 情节块标题
        chapter_start: 起始章节号
        chapter_end: 结束章节号
        must_happen: JSON 字符串列表, 必须发生的事件
        questions_to_raise: JSON 字符串列表, 需要提出的问题
        questions_to_answer: JSON 字符串列表, 需要回答的问题
        expected_mood: 预期情绪基调
        completion_summary: 完成总结(仅更新路径)
    """
    kb = _kb()

    if plot_block_id:
        # --- 更新路径 ---
        before = kb.plots.get_plot_block_by_id(plot_block_id)
        if not before:
            return {"error": f"情节块 ID {plot_block_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "title", "chapter_start", "chapter_end",
            "expected_mood", "completion_summary",
        )
        update_data = {}
        for k in _UPDATABLE_FIELDS:
            v = locals()[k]
            if v is not None:
                update_data[k] = v

        # JSON 参数
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
        changes = build_changes_diff(before, update_data)
        result = {
            "plot_block_id": plot_block_id,
            "title": updated.get("title", before.get("title")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"情节块「{updated.get('title', before.get('title'))}」已更新",
        }
        if warnings:
            result["param_parse_warnings"] = warnings
        return result
    else:
        # --- 创建路径 ---
        if not title or chapter_start is None or chapter_end is None:
            return {"error": "创建情节块时 title, chapter_start, chapter_end 为必填字段"}

        must, _ = parse_json_param(must_happen or "[]", [], "must_happen")
        raise_q, _ = parse_json_param(questions_to_raise or "[]", [], "questions_to_raise")
        answer_q, _ = parse_json_param(questions_to_answer or "[]", [], "questions_to_answer")

        data = {
            "title": title,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "must_happen": must,
            "questions_to_raise": raise_q,
            "questions_to_answer": answer_q,
        }
        if expected_mood:
            data["expected_mood"] = expected_mood

        block = kb.plots.create_plot_block(data)
        return {
            "action": "created",
            "id": block["id"],
            "title": title,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "message": f"情节块「{title}」已创建并写入知识库",
        }
