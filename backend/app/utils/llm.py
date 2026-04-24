"""LLM utility functions"""

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.model_config import ModelConfig
from app.services.llm import get_llm_service, get_llm_service_from_config


def get_llm_for_user(
    user_id: int,
    user_settings,
    db: Session,
    llm_config_id: Optional[int] = None
):
    """
    获取用户的 LLM 服务

    优先使用指定的模型配置，如果没有则使用默认模型配置

    Args:
        user_id: 用户 ID
        user_settings: 用户设置
        db: 数据库会话
        llm_config_id: 可选的模型配置 ID

    Returns:
        LLMService 实例

    Raises:
        HTTPException: 如果指定的模型配置不存在
    """
    # 如果指定了模型配置 ID，验证并使用
    if llm_config_id:
        config = db.query(ModelConfig).filter(
            ModelConfig.id == llm_config_id,
            ModelConfig.user_id == user_id
        ).first()
        if config:
            return get_llm_service_from_config(config, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )

    # 否则使用默认模型配置
    default_config = db.query(ModelConfig).filter(
        ModelConfig.user_id == user_id,
        ModelConfig.is_default == True,
        ModelConfig.is_enabled == True
    ).first()

    if default_config:
        return get_llm_service_from_config(default_config, user_id)

    # 兼容旧版本：使用用户设置
    return get_llm_service(user_settings)
