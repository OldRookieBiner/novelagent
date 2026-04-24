"""模型配置 Schemas"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ModelItem(BaseModel):
    """Coding Plan 中的单个模型"""
    id: str
    name: str
    is_enabled: bool = True
    health_status: Optional[str] = None


class ModelConfigBase(BaseModel):
    """模型配置基础"""
    name: str
    provider: str
    provider_type: str = "single"
    base_url: str
    model_name: Optional[str] = None
    models: Optional[list[ModelItem]] = None
    api_key: Optional[str] = None


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置"""
    pass


class ModelConfigUpdate(BaseModel):
    """更新模型配置"""
    name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    models: Optional[list[ModelItem]] = None
    is_enabled: Optional[bool] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False


class ModelConfigResponse(BaseModel):
    """模型配置响应"""
    id: int
    name: str
    provider: str
    provider_type: str = "single"
    base_url: str
    model_name: Optional[str] = None
    models: Optional[list[ModelItem]] = None
    has_api_key: bool
    is_enabled: bool
    is_default: bool
    health_status: Optional[str] = None
    health_latency: Optional[int] = None
    last_health_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelConfigListResponse(BaseModel):
    """模型配置列表响应"""
    models: list[ModelConfigResponse]


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str  # "healthy" | "unhealthy"
    latency: Optional[int] = None
    error: Optional[str] = None


class FetchModelsRequest(BaseModel):
    """获取模型列表请求"""
    provider: str
    base_url: str
    api_key: str


class FetchModelsResponse(BaseModel):
    """获取模型列表响应"""
    models: list[dict]  # [{"id": str, "name": str}]
    error: Optional[str] = None
    allow_manual: bool = False


class ProviderInfo(BaseModel):
    """提供商信息"""
    id: str
    name: str
    provider_type: str
    base_url: str


class ProvidersListResponse(BaseModel):
    """提供商列表响应"""
    providers: list[ProviderInfo]
