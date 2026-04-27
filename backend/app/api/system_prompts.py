"""System prompts API routes"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system_config import SystemConfig
from app.schemas.system_prompt import (
    SystemPromptResponse,
    SystemPromptListResponse,
    SystemPromptUpdate,
    AGENT_TYPES,
)
from app.agents.prompts import DEFAULT_PROMPTS

router = APIRouter()

# Key mapping from agent_type to database key
PROMPT_KEY_MAP = {
    "outline_generation": "prompt_outline_generation",
    "chapter_outline_generation": "prompt_chapter_outline_generation",
    "chapter_content_generation": "prompt_chapter_content_generation",
    "review": "prompt_review",
    "rewrite": "prompt_rewrite",
}


def get_prompt_key(agent_type: str) -> str:
    """Get database key for agent type"""
    return PROMPT_KEY_MAP.get(agent_type, f"prompt_{agent_type}")


@router.get("/", response_model=SystemPromptListResponse)
async def get_system_prompts(db: Session = Depends(get_db)):
    """获取所有系统提示词"""
    prompts = []
    for agent_type, meta in AGENT_TYPES.items():
        key = get_prompt_key(agent_type)
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

        content = config.value if config else DEFAULT_PROMPTS.get(agent_type, "")
        updated_at = config.updated_at if config else None

        prompts.append(SystemPromptResponse(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            prompt_content=content,
            variables=meta["variables"],
            variable_descriptions=meta["variable_descriptions"],
            updated_at=updated_at
        ))

    return SystemPromptListResponse(prompts=prompts)


@router.put("/{agent_type}", response_model=SystemPromptResponse)
async def update_system_prompt(
    agent_type: str,
    request: SystemPromptUpdate,
    db: Session = Depends(get_db)
):
    """更新系统提示词"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    key = get_prompt_key(agent_type)
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config:
        config.value = request.prompt_content
    else:
        config = SystemConfig(key=key, value=request.prompt_content)
        db.add(config)

    db.commit()
    db.refresh(config)

    meta = AGENT_TYPES[agent_type]
    return SystemPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=config.value,
        variables=meta["variables"],
        variable_descriptions=meta["variable_descriptions"],
        updated_at=config.updated_at
    )


@router.post("/{agent_type}/reset", response_model=SystemPromptResponse)
async def reset_system_prompt(agent_type: str, db: Session = Depends(get_db)):
    """重置系统提示词为默认值"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")

    key = get_prompt_key(agent_type)
    default_content = DEFAULT_PROMPTS.get(agent_type, "")

    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config:
        config.value = default_content
    else:
        config = SystemConfig(key=key, value=default_content)
        db.add(config)

    db.commit()
    db.refresh(config)

    meta = AGENT_TYPES[agent_type]
    return SystemPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=config.value,
        variables=meta["variables"],
        variable_descriptions=meta["variable_descriptions"],
        updated_at=config.updated_at
    )
