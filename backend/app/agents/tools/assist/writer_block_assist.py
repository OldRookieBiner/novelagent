"""写作卡壳辅助工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def writer_block_assist(current_chapter: int) -> dict:
    """Help overcome writer's block with 2-3 writing directions.

    Suggests scene ideas, reclaimable foreshadowings, and
    question chain prompts based on current progress.

    Args:
        current_chapter: Current chapter number being worked on
    """
    kb = _kb()

    pending = kb.get_pending_foreshadowings()
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    questions = kb.get_questions_for_chapter(current_chapter)
    block = kb.get_current_plot_block(current_chapter)

    suggestions = []

    if overdue:
        f = overdue[0]
        suggestions.append({
            "direction": "回收超期伏笔",
            "detail": f"伏笔「{f.content[:50]}」已超过预期回收章节，可以在本章回收",
            "foreshadowing_id": f.id,
        })

    if questions:
        q = questions[0]
        suggestions.append({
            "direction": "回答待解问题",
            "detail": f"问题「{q.question_text[:50]}」可以在本章回答",
            "question_id": q.id,
        })

    if block:
        must_happen = block.must_happen or []
        if must_happen:
            suggestions.append({
                "direction": "推进情节块",
                "detail": f"当前情节块「{block.title}」必须事件：{must_happen[0][:50] if must_happen else '无'}",
                "plot_block_id": block.id,
            })

    if not suggestions:
        suggestions.append({
            "direction": "自由发挥",
            "detail": "当前没有紧迫的伏笔或问题链需要处理，可以自由推进剧情",
        })

    return {
        "current_chapter": current_chapter,
        "suggestions": suggestions,
        "pending_foreshadowings": len(pending),
        "pending_questions": len(questions),
    }
