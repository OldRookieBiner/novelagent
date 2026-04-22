"""模型配置 API 路由"""

import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.model_config import ModelConfig
from app.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelConfigListResponse,
    HealthCheckResponse,
    PRESET_MODELS,
)
from app.utils.auth import get_current_user
from app.services.crypto import encrypt_api_key, decrypt_api_key
from app.services.llm import LLMService

router = APIRouter()


def get_or_create_default_configs(db: Session, user_id: int) -> list[ModelConfig]:
    """获取或创建用户的默认模型配置"""
    configs = db.query(ModelConfig).filter(
        ModelConfig.user_id == user_id
    ).all()

    # 如果用户没有配置，创建预设模型
    if not configs:
        for preset in PRESET_MODELS:
            config = ModelConfig(
                user_id=user_id,
                name=preset["name"],
                provider=preset["provider"],
                base_url=preset["base_url"],
                model_name=preset["model_name"],
                is_enabled=True,
                is_default=(preset["provider"] == "deepseek"),  # 默认选中 DeepSeek
                health_status="unknown",
            )
            db.add(config)
        db.commit()
        configs = db.query(ModelConfig).filter(
            ModelConfig.user_id == user_id
        ).all()

    return configs


def build_config_response(c: ModelConfig) -> ModelConfigResponse:
    """构建模型配置响应"""
    return ModelConfigResponse(
        id=c.id,
        name=c.name,
        provider=c.provider,
        base_url=c.base_url,
        model_name=c.model_name,
        has_api_key=bool(c.api_key_encrypted),
        is_enabled=c.is_enabled,
        is_default=c.is_default,
        health_status=c.health_status,
        health_latency=c.health_latency,
        last_health_check=c.last_health_check,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/", response_model=ModelConfigListResponse)
async def list_model_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的模型配置列表"""
    configs = get_or_create_default_configs(db, current_user.id)
    return ModelConfigListResponse(
        models=[build_config_response(c) for c in configs]
    )


@router.post("/", response_model=ModelConfigResponse)
async def create_model_config(
    request: ModelConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的模型配置"""
    config = ModelConfig(
        user_id=current_user.id,
        name=request.name,
        provider=request.provider,
        base_url=request.base_url,
        model_name=request.model_name,
        is_enabled=True,
        is_default=False,
        health_status="unknown",
    )

    if request.api_key:
        config.api_key_encrypted = encrypt_api_key(request.api_key, current_user.id)

    db.add(config)
    db.commit()
    db.refresh(config)

    return build_config_response(config)


@router.put("/{config_id}", response_model=ModelConfigResponse)
async def update_model_config(
    config_id: int,
    request: ModelConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模型配置"""
    config = db.query(ModelConfig).filter(
        ModelConfig.id == config_id,
        ModelConfig.user_id == current_user.id
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )

    if request.name is not None:
        config.name = request.name
    if request.base_url is not None:
        config.base_url = request.base_url
    if request.model_name is not None:
        config.model_name = request.model_name
    if request.is_enabled is not None:
        config.is_enabled = request.is_enabled
    if request.api_key is not None:
        config.api_key_encrypted = encrypt_api_key(request.api_key, current_user.id)
    if request.clear_api_key is True:
        config.api_key_encrypted = None

    db.commit()
    db.refresh(config)

    return build_config_response(config)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模型配置"""
    config = db.query(ModelConfig).filter(
        ModelConfig.id == config_id,
        ModelConfig.user_id == current_user.id
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )

    # 不允许删除预设模型，只能禁用
    if config.provider != "custom":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete preset models. Disable them instead."
        )

    db.delete(config)
    db.commit()

    return {"success": True}


@router.post("/{config_id}/health", response_model=HealthCheckResponse)
async def check_model_health(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查模型健康状态"""
    config = db.query(ModelConfig).filter(
        ModelConfig.id == config_id,
        ModelConfig.user_id == current_user.id
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )

    if not config.api_key_encrypted:
        return HealthCheckResponse(
            status="unhealthy",
            error="API Key not configured"
        )

    api_key = decrypt_api_key(config.api_key_encrypted, current_user.id)

    try:
        llm = LLMService(
            provider="custom",
            api_key=api_key,
            base_url=config.base_url,
            model=config.model_name
        )

        start_time = time.time()
        # 发送最小请求测试连通性
        await llm.chat(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        latency = int((time.time() - start_time) * 1000)

        # 更新健康状态
        config.health_status = "healthy"
        config.health_latency = latency
        config.last_health_check = datetime.utcnow()
        db.commit()

        return HealthCheckResponse(
            status="healthy",
            latency=latency
        )
    except Exception as e:
        # 更新健康状态
        config.health_status = "unhealthy"
        config.health_latency = None
        config.last_health_check = datetime.utcnow()
        db.commit()

        return HealthCheckResponse(
            status="unhealthy",
            error=str(e)
        )


@router.put("/{config_id}/default", response_model=ModelConfigResponse)
async def set_default_model(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """设置默认模型"""
    config = db.query(ModelConfig).filter(
        ModelConfig.id == config_id,
        ModelConfig.user_id == current_user.id
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model config not found"
        )

    if not config.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set a disabled model as default"
        )

    # 清除其他默认设置
    db.query(ModelConfig).filter(
        ModelConfig.user_id == current_user.id
    ).update({"is_default": False})

    # 设置新的默认
    config.is_default = True
    db.commit()
    db.refresh(config)

    return build_config_response(config)
