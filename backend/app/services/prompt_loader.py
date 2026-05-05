"""Prompt loader service with in-memory cache"""

import time
import logging
from sqlalchemy.orm import Session
from app.models.system_config import SystemConfig
from app.agents.prompts import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)

# prompt 最小有效长度（低于此值视为测试/无效数据）
MIN_PROMPT_LENGTH = 100

# 内存缓存：{key: (value, timestamp)}
_prompt_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 300  # 5 分钟


def get_system_prompt(db: Session, agent_type: str) -> str:
    """Get system prompt for agent type from database or default

    优先使用内存缓存，其次数据库，最后代码默认值。
    """
    key = f"prompt_{agent_type}"

    # 检查内存缓存
    now = time.time()
    cached = _prompt_cache.get(key)
    if cached and (now - cached[1]) < CACHE_TTL:
        return cached[0]

    # 从数据库加载
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()

    if config and config.value and len(config.value.strip()) >= MIN_PROMPT_LENGTH:
        _prompt_cache[key] = (config.value, now)
        return config.value

    # 数据库中无有效 prompt，使用代码默认值
    default = DEFAULT_PROMPTS.get(agent_type, "")
    _prompt_cache[key] = (default, now)
    return default


def invalidate_prompt_cache(agent_type: str | None = None):
    """清除 Prompt 缓存

    Args:
        agent_type: 特定 agent type 的缓存，None 则清除所有
    """
    if agent_type:
        key = f"prompt_{agent_type}"
        _prompt_cache.pop(key, None)
        logger.debug("Prompt cache invalidated for: %s", agent_type)
    else:
        _prompt_cache.clear()
        logger.debug("All prompt caches invalidated")