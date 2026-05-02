"""API 端点依赖注入工具函数"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.settings import UserSettings


def get_user_settings_or_raise(user: User, db: Session) -> UserSettings:
    """获取用户设置，如果不存在则抛出 400 错误"""
    user_settings = (
        db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    )

    if not user_settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User settings not found"
        )

    return user_settings


def get_llm_for_context(request, user: User, user_settings: UserSettings, db: Session):
    """根据请求和用户上下文获取 LLM 服务

    优先使用请求中指定的模型配置，回退到默认配置，最后使用用户设置中的全局 API key。
    """
    from app.utils.llm import get_llm_for_user

    # 使用 getattr 安全访问，因为 request 可能是 Starlette Request（无 llm_config_id）
    # 也可能是 Pydantic schema（有 llm_config_id）
    llm_config_id = getattr(request, 'llm_config_id', None) if request else None
    return get_llm_for_user(user.id, user_settings, db, llm_config_id)
