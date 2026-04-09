# backend/app/services/prompt_service.py
"""Service for managing and retrieving agent prompts"""

from sqlalchemy.orm import Session

from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt
from app.agents.prompts import DEFAULT_PROMPTS


def get_effective_prompt(
    db: Session,
    user_id: int,
    project_id: int,
    agent_type: str
) -> tuple[str, str]:
    """
    Get the effective prompt for a project's agent.

    Returns: (prompt_content, source)
    - source: "custom" | "global" | "system_default"

    Priority: project_custom > global > system_default
    """
    # 1. Check project custom prompt
    custom = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()
    if custom:
        return custom.prompt_content, "custom"

    # 2. Check global prompt
    global_prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == user_id,
        AgentPrompt.agent_type == agent_type
    ).first()
    if global_prompt:
        return global_prompt.prompt_content, "global"

    # 3. Return system default
    default = DEFAULT_PROMPTS.get(agent_type, "")
    return default, "system_default"


def ensure_user_has_global_prompts(db: Session, user_id: int) -> None:
    """
    Ensure user has global prompt entries for all agent types.
    Called when user first accesses agent management page.
    """
    existing_types = set(
        p.agent_type for p in db.query(AgentPrompt.agent_type).filter(
            AgentPrompt.user_id == user_id
        ).all()
    )

    for agent_type, default_content in DEFAULT_PROMPTS.items():
        if agent_type not in existing_types:
            prompt = AgentPrompt(
                user_id=user_id,
                agent_type=agent_type,
                prompt_content=default_content
            )
            db.add(prompt)

    db.commit()