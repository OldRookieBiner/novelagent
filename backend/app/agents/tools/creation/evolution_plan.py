"""创建关系演变规划工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_evolution_plan(
    relation_id: int,
    trigger_chapter: int,
    event_description: str,
    status_before: str = "",
    status_after: str = "",
    trust_before: int = -1,
    trust_after: int = -1,
) -> dict:
    """Create an evolution plan for a character relationship.

    Use when the user describes how a relationship will change at a specific point in the story.
    This directly writes to the knowledge base.

    Args:
        relation_id: ID of the relationship to add evolution plan to
        trigger_chapter: The chapter number where this evolution is expected to trigger
        event_description: Description of the event that triggers the evolution
        status_before: The relationship status before the event (optional)
        status_after: The relationship status after the event (optional)
        trust_before: Trust level before the event (0-100, optional, -1 to skip)
        trust_after: Trust level after the event (0-100, optional, -1 to skip)
    """
    kb = _kb()

    kwargs = {
        "relation_id": relation_id,
        "trigger_chapter": trigger_chapter,
        "event_description": event_description,
    }
    if status_before:
        kwargs["status_before"] = status_before
    if status_after:
        kwargs["status_after"] = status_after
    if trust_before >= 0:
        kwargs["trust_before"] = trust_before
    if trust_after >= 0:
        kwargs["trust_after"] = trust_after

    plan = kb.create_evolution_plan(**kwargs)
    return {
        "action": "created",
        "id": plan.id,
        "relation_id": relation_id,
        "trigger_chapter": trigger_chapter,
        "message": f"关系演变规划已创建：第{trigger_chapter}章「{event_description[:30]}」",
    }
