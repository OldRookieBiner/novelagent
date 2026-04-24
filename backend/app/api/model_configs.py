"""模型配置 API 路由"""

import time
import httpx
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
    FetchModelsRequest,
    FetchModelsResponse,
    ProviderInfo,
    ProvidersListResponse,
)
from app.utils.auth import get_current_user
from app.services.crypto import encrypt_api_key, decrypt_api_key
from app.services.llm import LLMService
from app.services.model_providers import get_provider_config, PRESET_PROVIDERS

router = APIRouter()


def get_user_model_configs(db: Session, user_id: int) -> list[ModelConfig]:
    """获取用户的模型配置列表（按创建时间排序）"""
    configs = db.query(ModelConfig).filter(
        ModelConfig.user_id == user_id
    ).order_by(ModelConfig.created_at).all()

    return configs


def build_config_response(c: ModelConfig) -> ModelConfigResponse:
    """构建模型配置响应"""
    # 转换 models 字段
    models = None
    if c.models:
        models = [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "is_enabled": m.get("is_enabled", True),
                "health_status": m.get("health_status")
            }
            for m in c.models
        ]

    return ModelConfigResponse(
        id=c.id,
        name=c.name,
        provider=c.provider,
        provider_type=c.provider_type or "single",
        base_url=c.base_url,
        model_name=c.model_name,
        models=models,
        has_api_key=bool(c.api_key_encrypted),
        is_enabled=c.is_enabled,
        is_default=c.is_default,
        health_status=c.health_status,
        health_latency=c.health_latency,
        last_health_check=c.last_health_check,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/providers", response_model=ProvidersListResponse)
async def list_providers():
    """获取所有预设提供商列表"""
    providers = [
        ProviderInfo(
            id=key,
            name=config["name"],
            provider_type=config["provider_type"],
            base_url=config["base_url"]
        )
        for key, config in PRESET_PROVIDERS.items()
    ]
    return ProvidersListResponse(providers=providers)


@router.post("/fetch-models", response_model=FetchModelsResponse)
async def fetch_available_models(
    request: FetchModelsRequest,
    current_user: User = Depends(get_current_user)
):
    """从 Coding Plan API 获取可用模型列表"""
    provider_config = get_provider_config(request.provider)

    if not provider_config:
        return FetchModelsResponse(
            models=[],
            error=f"未知的提供商: {request.provider}",
            allow_manual=True
        )

    if provider_config["provider_type"] != "coding_plan":
        return FetchModelsResponse(
            models=[],
            error="该提供商不是 Coding Plan 类型",
            allow_manual=False
        )

    models_api = provider_config.get("models_api", "/v1/models")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{request.base_url.rstrip('/')}{models_api}",
                headers={
                    "Authorization": f"Bearer {request.api_key}"
                }
            )

            if response.status_code == 200:
                data = response.json()
                models = []
                if isinstance(data, list):
                    models = [{"id": m.get("id", m.get("name")), "name": m.get("id", m.get("name"))} for m in data]
                elif isinstance(data, dict) and "data" in data:
                    models = [{"id": m.get("id", m.get("name")), "name": m.get("id", m.get("name"))} for m in data["data"]]
                elif isinstance(data, dict) and "models" in data:
                    models = [{"id": m.get("id", m.get("name")), "name": m.get("id", m.get("name"))} for m in data["models"]]

                return FetchModelsResponse(models=models)

            return FetchModelsResponse(
                models=[],
                error=f"API 返回错误: {response.status_code}",
                allow_manual=True
            )

    except httpx.TimeoutException:
        return FetchModelsResponse(
            models=[],
            error="请求超时，请检查 API 地址是否正确",
            allow_manual=True
        )
    except Exception as e:
        return FetchModelsResponse(
            models=[],
            error=f"获取模型列表失败: {str(e)}",
            allow_manual=True
        )


@router.get("/", response_model=ModelConfigListResponse)
async def list_model_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的模型配置列表"""
    configs = get_user_model_configs(db, current_user.id)
    return ModelConfigListResponse(
        models=[build_config_response(c) for c in configs]
    )


@router.post("/test", response_model=HealthCheckResponse)
async def test_model_connection(
    request: ModelConfigCreate,
    current_user: User = Depends(get_current_user)
):
    """
    测试模型连接（不创建配置）
    在添加模型前先验证连接是否正常
    """
    if not request.api_key:
        return HealthCheckResponse(
            status="unhealthy",
            error="请输入 API Key"
        )

    # Coding Plan 类型需要选择具体模型测试
    model_to_test = request.model_name
    if request.provider_type == "coding_plan" and not model_to_test:
        return HealthCheckResponse(
            status="unhealthy",
            error="Coding Plan 类型需要选择具体模型"
        )

    try:
        llm = LLMService(
            provider="custom",
            api_key=request.api_key,
            base_url=request.base_url,
            model=model_to_test or "default"
        )

        start_time = time.time()
        # 发送最小请求测试连通性
        await llm.chat(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        latency = int((time.time() - start_time) * 1000)

        return HealthCheckResponse(
            status="healthy",
            latency=latency
        )
    except Exception as e:
        return HealthCheckResponse(
            status="unhealthy",
            error=str(e)
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
        provider_type=request.provider_type,
        base_url=request.base_url,
        model_name=request.model_name,
        models=[m.model_dump() for m in request.models] if request.models else None,
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
    if request.models is not None:
        config.models = [m.model_dump() for m in request.models]
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

    # 确定 model_name
    model_name = config.model_name
    if config.provider_type == "coding_plan" and config.models:
        # 从 models 列表选择第一个启用的模型
        enabled_models = [m for m in config.models if m.get("is_enabled", True)]
        if enabled_models:
            model_name = enabled_models[0].get("id")

    if not model_name:
        return HealthCheckResponse(
            status="unhealthy",
            error="No model available for health check"
        )

    try:
        llm = LLMService(
            provider="custom",
            api_key=api_key,
            base_url=config.base_url,
            model=model_name
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
