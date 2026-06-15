"""创建情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param


@tool
async def create_plot_block(
    title: str,
    chapter_start: int,
    chapter_end: int,
    must_happen: str = "[]",
    questions_to_raise: str = "[]",
    questions_to_answer: str = "[]",
    expected_mood: str = "",
) -> dict:
    """创建新的情节块（故事弧线段）。

    当用户需要规划故事的情节弧线段时使用。情节块定义了某一章节范围内必须发生的事件和需要提出/回答的问题。

    Args:
        title: 情节块标题
        chapter_start: 起始章节号
        chapter_end: 结束章节号
        must_happen: JSON 字符串列表，必须发生的事件
        questions_to_raise: JSON 字符串列表，需要提出的问题
        questions_to_answer: JSON 字符串列表，需要回答的问题
        expected_mood: 预期情绪基调
    """
    kb = _kb()

    must, must_warn = parse_json_param(must_happen, [], "must_happen")

    raise_q, raise_q_warn = parse_json_param(questions_to_raise, [], "questions_to_raise")

    answer_q, answer_q_warn = parse_json_param(questions_to_answer, [], "questions_to_answer")

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
