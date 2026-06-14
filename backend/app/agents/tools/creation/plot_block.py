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
    """Create a new plot block (story arc segment).

    Use when the user wants to define a plot segment or story arc
    covering a range of chapters.

    Args:
        title: Plot block title (e.g., "初入修仙界")
        chapter_start: Starting chapter number
        chapter_end: Ending chapter number
        must_happen: JSON string list of events that must happen in this block
        questions_to_raise: JSON string list of questions this block raises
        questions_to_answer: JSON string list of questions this block should answer
        expected_mood: Expected mood/tone for this block (e.g., "紧张悬疑", "温馨治愈")
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
        "chapter_range": f"{chapter_start}-{chapter_end}",
        "message": f"情节块「{title}」已创建并写入知识库",
    }
