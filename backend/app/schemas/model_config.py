"""模型配置 Schemas"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel


# 预设模型配置
PRESET_MODELS = [
    {
        "name": "DeepSeek (火山方舟)",
        "provider": "deepseek",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_name": "deepseek-v3-241227",
    },
    {
        "name": "DeepSeek (官方)",
        "provider": "deepseek-official",
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
    },
    {
        "name": "OpenAI",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
    },
]


class ModelConfigBase(BaseModel):
    """模型配置基础"""
    name: str
    provider: str = "custom"
    base_url: str
    model_name: str


class ModelConfigCreate(ModelConfigBase):
    """创建模型配置"""
    api_key: Optional[str] = None


class ModelConfigUpdate(BaseModel):
    """更新模型配置"""
    name: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    is_enabled: Optional[bool] = None
    clear_api_key: Optional[bool] = None


class ModelConfigResponse(BaseModel):
    """模型配置响应"""
    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
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
    status: str  # healthy / unhealthy
    latency: Optional[int] = None
    error: Optional[str] = None
