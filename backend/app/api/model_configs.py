"""模型配置 API 路由"""

import asyncio
import time
import httpx
from datetime import datetime, timezone
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
    ModelHealthResult,
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
    configs = (
        db.query(ModelConfig)
        .filter(ModelConfig.user_id == user_id)
        .order_by(ModelConfig.created_at)
        .all()
    )

    return configs


def build_config_response(c: ModelConfig) -> ModelConfigResponse:
    """构建模型配置响应"""
    # 处理 models 列表：透传所有字段 + 填充默认值
    models = None
    if c.models:
        models = []
        for m in c.models:
            item = {
                "id": m.get("id"),
                "name": m.get("name"),
                "is_enabled": m.get("is_enabled", True),
                "health_status": m.get("health_status"),
                "health_latency": m.get("health_latency"),
                "temperature": m.get("temperature", 0.7),
                "reasoning_effort": m.get("reasoning_effort"),
                "context_window": m.get("context_window"),
            }
            models.append(item)
    elif c.model_name:
        # 旧 single 类型数据：从 model_name 生成单元素 models 列表
        models = [{
            "id": c.model_name,
            "name": c.model_name,
            "is_enabled": True,
            "health_status": None,
            "temperature": 0.7,
            "reasoning_effort": None,
            "context_window": c.context_window,
        }]

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
            base_url=config["base_url"],
            models_api=config.get("models_api"),
        )
        for key, config in PRESET_PROVIDERS.items()
    ]
    return ProvidersListResponse(providers=providers)


@router.post("/fetch-models", response_model=FetchModelsResponse)
async def fetch_available_models(
    request: FetchModelsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从提供商 API 获取可用模型列表（支持所有配置了 models_api 的提供商）"""
    # 解析 api_key：优先从数据库解密，回退到请求体
    api_key = request.api_key

    if request.config_id:
        config = (
            db.query(ModelConfig)
            .filter(
                ModelConfig.id == request.config_id,
                ModelConfig.user_id == current_user.id,
            )
            .first()
        )
        if config and config.api_key_encrypted:
            api_key = decrypt_api_key(config.api_key_encrypted, current_user.id)

    if not api_key or not api_key.strip():
        return FetchModelsResponse(
            models=[], error="请输入 API Key", allow_manual=True
        )

    provider_config = get_provider_config(request.provider)

    if not provider_config:
        return FetchModelsResponse(
            models=[], error=f"未知的提供商: {request.provider}", allow_manual=True
        )

    if not provider_config.get("models_api"):
        return FetchModelsResponse(
            models=[], error="该提供商不支持获取模型列表", allow_manual=False
        )

    models_api = provider_config.get("models_api", "/v1/models")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{request.base_url.rstrip('/')}{models_api}",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code == 200:
                data = response.json()
                models = []
                if isinstance(data, list):
                    models = [
                        {
                            "id": m.get("id", m.get("name")),
                            "name": m.get("id", m.get("name")),
                        }
                        for m in data
                    ]
                elif isinstance(data, dict) and "data" in data:
                    models = [
                        {
                            "id": m.get("id", m.get("name")),
                            "name": m.get("id", m.get("name")),
                        }
                        for m in data["data"]
                    ]
                elif isinstance(data, dict) and "models" in data:
                    models = [
                        {
                            "id": m.get("id", m.get("name")),
                            "name": m.get("id", m.get("name")),
                        }
                        for m in data["models"]
                    ]

                return FetchModelsResponse(models=models)

            return FetchModelsResponse(
                models=[],
                error=f"API 返回错误: {response.status_code}",
                allow_manual=True,
            )

    except httpx.TimeoutException:
        return FetchModelsResponse(
            models=[], error="请求超时，请检查 API 地址是否正确", allow_manual=True
        )
    except Exception as e:
        return FetchModelsResponse(
            models=[], error=f"获取模型列表失败: {str(e)}", allow_manual=True
        )


@router.get("/", response_model=ModelConfigListResponse)
async def list_model_configs(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取用户的模型配置列表"""
    configs = get_user_model_configs(db, current_user.id)
    return ModelConfigListResponse(models=[build_config_response(c) for c in configs])


@router.post("/test", response_model=HealthCheckResponse)
async def test_model_connection(
    request: ModelConfigCreate, current_user: User = Depends(get_current_user)
):
    """
    测试模型连接（不创建配置）
    在添加模型前先验证连接是否正常
    """
    if not request.api_key:
        return HealthCheckResponse(status="unhealthy", error="请输入 API Key")

    # 确定 model_to_test
    model_to_test = request.model_name
    # 如果未指定 model_name，从 models 列表中取第一个启用的模型
    if not model_to_test and request.models:
        enabled_models = [m for m in request.models if m.is_enabled]
        if enabled_models:
            model_to_test = enabled_models[0].id
    if not model_to_test:
        return HealthCheckResponse(status="unhealthy", error="请选择至少一个模型")

    try:
        llm = LLMService(
            provider="custom",
            api_key=request.api_key,
            base_url=request.base_url,
            model=model_to_test or "default",
        )

        start_time = time.time()
        # 发送最小请求测试连通性
        await llm.chat(messages=[{"role": "user", "content": "Hi"}], max_tokens=5)
        latency = int((time.time() - start_time) * 1000)

        return HealthCheckResponse(status="healthy", latency=latency)
    except Exception as e:
        return HealthCheckResponse(status="unhealthy", error=str(e))


@router.post("/", response_model=ModelConfigResponse)
async def create_model_config(
    request: ModelConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的模型配置"""
    # 该用户若尚无默认配置，则将本次创建的首个配置自动设为默认。
    # 否则后端无显式 config_id 时会查不到 is_default 而静默降级到旧版
    # user_settings 路径（可能拿不到可用 api_key），健壮性依赖前端兜底。
    has_default = (
        db.query(ModelConfig)
        .filter(
            ModelConfig.user_id == current_user.id,
            ModelConfig.is_default,
        )
        .first()
        is not None
    )

    config = ModelConfig(
        user_id=current_user.id,
        name=request.name,
        provider=request.provider,
        provider_type=request.provider_type,
        base_url=request.base_url,
        model_name=request.model_name,
        models=[m.model_dump() for m in request.models] if request.models else None,
        is_enabled=True,
        is_default=not has_default,
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
    current_user: User = Depends(get_current_user),
):
    """更新模型配置"""
    config = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == config_id, ModelConfig.user_id == current_user.id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    if request.name is not None:
        config.name = request.name
    if request.provider is not None:
        config.provider = request.provider
    if request.base_url is not None:
        config.base_url = request.base_url
    if request.model_name is not None:
        config.model_name = request.model_name
    if request.models is not None:
        # 保留已有模型的健康状态
        existing_health = {}
        if config.models:
            for m in config.models:
                existing_health[m.get("id")] = {
                    "health_status": m.get("health_status"),
                    "health_latency": m.get("health_latency"),
                }
        updated_models = []
        for m in request.models:
            item = m.model_dump()
            if m.id in existing_health:
                item["health_status"] = existing_health[m.id].get("health_status")
                item["health_latency"] = existing_health[m.id].get("health_latency")
            updated_models.append(item)
        config.models = updated_models
    if request.is_enabled is not None:
        config.is_enabled = request.is_enabled
    if request.api_key is not None:
        config.api_key_encrypted = encrypt_api_key(request.api_key, current_user.id)
    if request.clear_api_key is True:
        config.api_key_encrypted = None
    if request.context_window is not None:
        config.context_window = request.context_window

    db.commit()
    db.refresh(config)

    return build_config_response(config)


@router.delete("/{config_id}")
async def delete_model_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模型配置"""
    config = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == config_id, ModelConfig.user_id == current_user.id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    db.delete(config)
    db.commit()

    return {"success": True}


@router.post("/{config_id}/health", response_model=HealthCheckResponse)
async def check_model_health(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查模型健康状态 — 并发测试所有已添加模型"""
    config = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == config_id, ModelConfig.user_id == current_user.id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    if not config.api_key_encrypted:
        return HealthCheckResponse(status="unhealthy", error="API Key 未配置")

    api_key = decrypt_api_key(config.api_key_encrypted, current_user.id)

    # 收集所有需要测试的模型
    models_to_test = []
    if config.models:
        for m in config.models:
            models_to_test.append({"id": m.get("id"), "name": m.get("name", m.get("id"))})
    elif config.model_name:
        models_to_test.append({"id": config.model_name, "name": config.model_name})

    if not models_to_test:
        return HealthCheckResponse(status="unhealthy", error="无可测试的模型")

    # 并发测试所有模型
    async def test_single_model(model_id: str, model_name: str) -> ModelHealthResult:
        try:
            llm = LLMService(
                provider="custom",
                api_key=api_key,
                base_url=config.base_url,
                model=model_id,
            )
            start = time.time()
            await asyncio.wait_for(
                llm.chat(messages=[{"role": "user", "content": "Hi"}], max_tokens=5),
                timeout=30,
            )
            latency = int((time.time() - start) * 1000)
            return ModelHealthResult(model_id=model_id, model_name=model_name, status="healthy", latency=latency)
        except Exception as e:
            return ModelHealthResult(model_id=model_id, model_name=model_name, status="unhealthy", error=str(e)[:200])

    # 并发执行，总超时 60s
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[test_single_model(m["id"], m["name"]) for m in models_to_test]),
            timeout=60,
        )
    except asyncio.TimeoutError:
        return HealthCheckResponse(status="unhealthy", error="健康检查超时")

    # 将逐模型健康状态写回 config.models JSON
    if config.models:
        result_map = {r.model_id: r for r in results}
        updated_models = []
        for m in config.models:
            item = dict(m)
            r = result_map.get(m.get("id"))
            if r:
                item["health_status"] = r.status
                item["health_latency"] = r.latency
            updated_models.append(item)
        config.models = updated_models

    # 聚合顶层健康状态
    healthy_count = sum(1 for r in results if r.status == "healthy")
    unhealthy_count = len(results) - healthy_count

    if unhealthy_count == 0:
        config.health_status = "healthy"
        config.health_latency = min((r.latency for r in results if r.latency is not None), default=None)
    else:
        config.health_status = "unhealthy"
        config.health_latency = None

    config.last_health_check = datetime.now(timezone.utc)
    db.commit()

    return HealthCheckResponse(
        status=config.health_status,
        latency=config.health_latency,
        model_results=results,
    )


@router.put("/{config_id}/default", response_model=ModelConfigResponse)
async def set_default_model(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置默认模型"""
    config = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == config_id, ModelConfig.user_id == current_user.id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    if not config.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set a disabled model as default",
        )

    # 清除其他默认设置
    db.query(ModelConfig).filter(ModelConfig.user_id == current_user.id).update(
        {"is_default": False}
    )

    # 设置新的默认
    config.is_default = True
    db.commit()
    db.refresh(config)

    return build_config_response(config)
