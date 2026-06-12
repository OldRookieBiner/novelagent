"""创建情节块工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


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
    import json as _json
    kb = _kb()

    try:
        must = _json.loads(must_happen) if isinstance(must_happen, str) else must_happen
    except _json.JSONDecodeError:
        must = []

    try:
        raise_q = _json.loads(questions_to_raise) if isinstance(questions_to_raise, str) else questions_to_raise
    except _json.JSONDecodeError:
        raise_q = []

    try:
        answer_q = _json.loads(questions_to_answer) if isinstance(questions_to_answer, str) else questions_to_answer
    except _json.JSONDecodeError:
        answer_q = []

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
