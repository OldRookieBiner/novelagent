"""LLM utility functions"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.model_config import ModelConfig
from app.services.llm import LLMService, get_llm_service, get_llm_service_from_config

logger = logging.getLogger(__name__)

# 线程池用于在 async 上下文中执行同步 DB 操作
_db_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db-")


def get_llm_for_user(
    user_id: int, user_settings, db: Session, llm_config_id: Optional[int] = None,
    llm_model_name: Optional[str] = None
):
    """
    获取用户的 LLM 服务

    优先使用指定的模型配置，如果没有则使用默认模型配置

    Args:
        user_id: 用户 ID
        user_settings: 用户设置
        db: 数据库会话
        llm_config_id: 可选的模型配置 ID
        llm_model_name: 可选的模型名称（覆盖配置中的默认模型）

    Returns:
        LLMService 实例

    Raises:
        HTTPException: 如果指定的模型配置不存在
    """
    # 如果指定了模型配置 ID，验证并使用
    if llm_config_id:
        config = (
            db.query(ModelConfig)
            .filter(ModelConfig.id == llm_config_id, ModelConfig.user_id == user_id)
            .first()
        )
        if config:
            return get_llm_service_from_config(config, user_id, llm_model_name)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    # 否则使用默认模型配置
    default_config = (
        db.query(ModelConfig)
        .filter(
            ModelConfig.user_id == user_id,
            ModelConfig.is_default,
            ModelConfig.is_enabled,
        )
        .first()
    )

    if default_config:
        return get_llm_service_from_config(default_config, user_id)

    # 兼容旧版本：使用用户设置
    return get_llm_service(user_settings)


def get_llm_from_state(state: dict, db: Optional["Session"] = None) -> "LLMService":
    """从工作流状态获取 LLM 服务（同步版本）

    根据 state 中的 llm_config_id 和 project_id 获取对应的 LLM 服务。
    优先级：指定模型配置 > 默认模型配置 > 用户设置

    警告：此函数使用同步数据库连接，在 async 上下文中会阻塞 event loop。
    在 async 节点中请使用 get_llm_from_state_async()。

    Args:
        state: NovelState 字典
        db: 可选的数据库会话。如果提供，直接使用而不创建新 session。

    Returns:
        LLMService 实例

    Raises:
        ValueError: 项目未找到或用户设置未找到
    """
    from app.database import SessionLocal
    from app.models.project import Project
    from app.models.settings import UserSettings

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        project_id = state.get("project_id")
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        user_id = project.user_id
        user_settings = (
            db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        )

        if not user_settings:
            raise ValueError(f"User settings not found for user {user_id}")

        return get_llm_for_user(user_id, user_settings, db, state.get("llm_config_id"), state.get("llm_model_name"))
    finally:
        if should_close:
            db.close()


async def get_llm_from_state_async(state: dict, db: Optional["Session"] = None, for_review: bool = False) -> "LLMService":
    """从工作流状态获取 LLM 服务（异步版本，推荐在 async 节点使用）

    将同步数据库操作放到线程池中执行，避免阻塞 event loop。
    如果传入 db 参数，直接使用该会话，不再创建新的 SessionLocal。

    Args:
        state: NovelState 字典
        db: 可选的数据库会话。如果提供，直接使用而不创建新 session。
        for_review: 是否获取审核专用 LLM。为 True 时优先使用 review_llm_config_id，
                    加载失败则回退到主模型。

    Returns:
        LLMService 实例

    Raises:
        ValueError: 项目未找到或用户设置未找到
    """
    # 审核专用 LLM 路径：优先使用 review_llm_config_id，失败则回退主模型
    if for_review:
        review_config_id = state.get("review_llm_config_id")
        if review_config_id:
            try:
                review_state = {**state, "llm_config_id": review_config_id}
                return await get_llm_from_state_async(review_state, db)
            except Exception as e:
                logger.warning(f"审核 LLM 配置 {review_config_id} 加载失败，回退到主模型: {e}")
                # 回退到主模型，继续执行下方逻辑

    if db is not None:
        # 直接在同一线程执行（调用方负责线程安全）
        return get_llm_from_state(state, db)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_db_executor, get_llm_from_state, state)


def resolve_llm_service(model_config_id: int | None = None, user_id: int | None = None, model_name: str | None = None):
    """统一的 LLM 服务解析入口

    优先级：model_config_id > user_settings > error
    所有 Agent 相关代码统一使用此函数获取 LLMService。

    Args:
        model_config_id: 模型配置 ID
        user_id: 用户 ID
        model_name: 具体模型名称（用于 coding_plan 类型配置中选择子模型）
    """
    from app.database import SessionLocal
    from app.models.model_config import ModelConfig
    from app.models.settings import UserSettings
    from app.services.llm import get_llm_service_from_config, get_llm_service

    if model_config_id and user_id:
        db = SessionLocal()
        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
            if config:
                return get_llm_service_from_config(config, user_id, model_override=model_name)
        finally:
            db.close()

    if user_id:
        db = SessionLocal()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                return get_llm_service(settings)
        finally:
            db.close()

    raise ValueError("无法获取 LLM 配置：请先在设置中配置 API Key")
