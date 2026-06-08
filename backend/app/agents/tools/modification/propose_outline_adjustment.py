"""提议大纲调整工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def propose_outline_adjustment(
    description: str,
    affected_plot_blocks: list[int] | None = None,
) -> dict:
    """Propose an adjustment to the story structure.

    Evaluates impact on foreshadowing, plot questions, and already-written chapters.

    Args:
        description: Natural language description of the proposed adjustment
        affected_plot_blocks: List of plot block IDs that would be affected
    """
    kb = _kb()

    blocks = kb.get_plot_blocks()
    foreshadowings = kb.get_foreshadowings(status="active")
    questions = kb.get_plot_questions(status="pending")

    affected_blocks = []
    if affected_plot_blocks:
        affected_blocks = [b for b in blocks if b.id in affected_plot_blocks]
    else:
        for b in blocks:
            block_text = f"{b.title} {' '.join(b.must_happen or [])} {' '.join(b.questions_to_answer or [])}"
            for word in description.split():
                if len(word) >= 2 and word in block_text:
                    affected_blocks.append(b)
                    break

    affected_foreshadowings = []
    for f in foreshadowings:
        for b in affected_blocks:
            if b.chapter_start and f.expected_resolve_chapter:
                if b.chapter_start <= f.expected_resolve_chapter <= (b.chapter_end or 999):
                    affected_foreshadowings.append({
                        "id": f.id,
                        "content": f.content[:60],
                        "expected_resolve_chapter": f.expected_resolve_chapter,
                    })

    affected_questions = []
    for q in questions:
        for b in affected_blocks:
            if q.plot_block_id == b.id:
                affected_questions.append({
                    "id": q.id,
                    "question": q.question_text[:60],
                    "status": q.status,
                })

    impact_level = "minor"
    if affected_foreshadowings or affected_questions:
        impact_level = "moderate"
    if len(affected_blocks) > 2:
        impact_level = "severe"

    change = kb.create_setting_change({
        "target_type": "outline_adjustment",
        "target_id": 0,
        "old_value": {},
        "new_value": {"description": description},
        "description": description,
        "status": "proposed",
        "impact_report": {
            "level": impact_level,
            "affected_blocks": [
                {"id": b.id, "title": b.title, "chapter_range": f"{b.chapter_start}-{b.chapter_end}"}
                for b in affected_blocks
            ],
            "affected_foreshadowings": affected_foreshadowings,
            "affected_questions": affected_questions,
        },
    })

    level_labels = {"minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_blocks": len(affected_blocks),
        "affected_foreshadowings": len(affected_foreshadowings),
        "affected_questions": len(affected_questions),
        "next_steps": "作者需决策：proceed / adjust / abandon",
    }
