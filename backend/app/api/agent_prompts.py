# backend/app/api/agent_prompts.py
"""API routes for agent prompt management"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt
from app.models.project import Project
from app.schemas.agent_prompt import (
    AgentPromptResponse,
    AgentPromptListResponse,
    AgentPromptUpdate,
    ProjectAgentPromptsResponse,
    ProjectAgentPromptItem,
    EffectivePromptResponse,
    AGENT_TYPES,
)
from app.services.prompt_service import get_effective_prompt, ensure_user_has_global_prompts
from app.agents.prompts import DEFAULT_PROMPTS
from app.utils.auth import get_current_user

router = APIRouter()


# ==================== Global Prompts ====================

@router.get("/agent-prompts", response_model=AgentPromptListResponse)
async def get_global_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all global agent prompts for current user"""
    # Ensure user has prompts initialized
    ensure_user_has_global_prompts(db, current_user.id)

    prompts = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id
    ).all()

    prompt_map = {p.agent_type: p for p in prompts}

    result = []
    for agent_type, meta in AGENT_TYPES.items():
        prompt = prompt_map.get(agent_type)
        is_default = prompt is None or prompt.prompt_content == DEFAULT_PROMPTS.get(agent_type, "")

        result.append(AgentPromptResponse(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            prompt_content=prompt.prompt_content if prompt else DEFAULT_PROMPTS.get(agent_type, ""),
            variables=meta["variables"],
            is_default=is_default,
            updated_at=prompt.updated_at if prompt else None
        ))

    return AgentPromptListResponse(prompts=result)


@router.put("/agent-prompts/{agent_type}", response_model=AgentPromptResponse)
async def update_global_prompt(
    agent_type: str,
    request: AgentPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a global agent prompt"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id,
        AgentPrompt.agent_type == agent_type
    ).first()

    if prompt:
        prompt.prompt_content = request.prompt_content
    else:
        prompt = AgentPrompt(
            user_id=current_user.id,
            agent_type=agent_type,
            prompt_content=request.prompt_content
        )
        db.add(prompt)

    db.commit()
    db.refresh(prompt)

    meta = AGENT_TYPES[agent_type]
    is_default = prompt.prompt_content == DEFAULT_PROMPTS.get(agent_type, "")

    return AgentPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=prompt.prompt_content,
        variables=meta["variables"],
        is_default=is_default,
        updated_at=prompt.updated_at
    )


@router.post("/agent-prompts/{agent_type}/reset", response_model=AgentPromptResponse)
async def reset_global_prompt(
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reset a global agent prompt to system default"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    default_content = DEFAULT_PROMPTS.get(agent_type, "")

    prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id,
        AgentPrompt.agent_type == agent_type
    ).first()

    if prompt:
        prompt.prompt_content = default_content
    else:
        prompt = AgentPrompt(
            user_id=current_user.id,
            agent_type=agent_type,
            prompt_content=default_content
        )
        db.add(prompt)

    db.commit()
    db.refresh(prompt)

    meta = AGENT_TYPES[agent_type]

    return AgentPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=prompt.prompt_content,
        variables=meta["variables"],
        is_default=True,
        updated_at=prompt.updated_at
    )


# ==================== Project Custom Prompts ====================

@router.get("/projects/{project_id}/agent-prompts", response_model=ProjectAgentPromptsResponse)
async def get_project_agent_prompts(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent prompts configuration for a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get custom prompts for this project
    custom_prompts = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id
    ).all()

    custom_map = {p.agent_type: p for p in custom_prompts}

    agents = []
    for agent_type, meta in AGENT_TYPES.items():
        custom = custom_map.get(agent_type)
        agents.append(ProjectAgentPromptItem(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            use_custom=custom is not None,
            custom_content=custom.prompt_content if custom else None,
            variables=meta["variables"]
        ))

    return ProjectAgentPromptsResponse(
        project_id=project_id,
        project_name=project.name,
        agents=agents
    )


@router.put("/projects/{project_id}/agent-prompts/{agent_type}", response_model=ProjectAgentPromptItem)
async def set_project_custom_prompt(
    project_id: int,
    agent_type: str,
    request: AgentPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set a custom prompt for a project's agent"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()

    if prompt:
        prompt.prompt_content = request.prompt_content
    else:
        prompt = ProjectAgentPrompt(
            project_id=project_id,
            agent_type=agent_type,
            prompt_content=request.prompt_content
        )
        db.add(prompt)

    db.commit()
    db.refresh(prompt)

    meta = AGENT_TYPES[agent_type]
    return ProjectAgentPromptItem(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        use_custom=True,
        custom_content=prompt.prompt_content,
        variables=meta["variables"]
    )


@router.delete("/projects/{project_id}/agent-prompts/{agent_type}")
async def delete_project_custom_prompt(
    project_id: int,
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a project's custom prompt, reverting to global default"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    prompt = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()

    if prompt:
        db.delete(prompt)
        db.commit()

    return {"success": True}


@router.get("/projects/{project_id}/agent-prompts/{agent_type}/effective", response_model=EffectivePromptResponse)
async def get_effective_prompt_api(
    project_id: int,
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the effective prompt for a project's agent (for internal use)"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    content, source = get_effective_prompt(db, current_user.id, project_id, agent_type)

    return EffectivePromptResponse(
        source=source,
        prompt_content=content
    )