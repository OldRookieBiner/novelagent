"""Prompt loader service"""

from sqlalchemy.orm import Session
from app.models.system_config import SystemConfig
from app.agents.prompts import DEFAULT_PROMPTS

# prompt 最小有效长度（低于此值视为测试/无效数据）
MIN_PROMPT_LENGTH = 100


def get_system_prompt(db: Session, agent_type: str) -> str:
    """Get system prompt for agent type from database or default

    优先使用数据库中的 prompt，但如果数据库中的值过短
    （可能是测试数据），则 fallback 到代码中的 DEFAULT_PROMPTS。
    """
    key = f"prompt_{agent_type}"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config and config.value and len(config.value.strip()) >= MIN_PROMPT_LENGTH:
        return config.value

    # 数据库中无有效 prompt，使用代码默认值
    return DEFAULT_PROMPTS.get(agent_type, "")
