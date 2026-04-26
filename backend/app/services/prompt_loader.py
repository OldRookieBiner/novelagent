"""Prompt loader service"""

from sqlalchemy.orm import Session
from app.models.system_config import SystemConfig
from app.agents.prompts import DEFAULT_PROMPTS


def get_system_prompt(db: Session, agent_type: str) -> str:
    """Get system prompt for agent type from database or default"""
    key = f"prompt_{agent_type}"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config and config.value:
        return config.value

    return DEFAULT_PROMPTS.get(agent_type, "")