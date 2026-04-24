# backend/app/services/model_providers.py
"""预设模型提供商配置"""

from typing import TypedDict, Optional


class ProviderConfig(TypedDict):
    """提供商配置"""
    name: str  # 显示名称
    base_url: str  # API 基础地址
    provider_type: str  # "single" | "coding_plan"
    default_model: Optional[str]  # 单模型时的默认模型
    models_api: Optional[str]  # 获取模型列表的端点
    auth_type: str  # "bearer" | "access_token"


PRESET_PROVIDERS: dict[str, ProviderConfig] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "provider_type": "single",
        "default_model": "deepseek-chat",
        "models_api": None,
        "auth_type": "bearer"
    },
    "baidu": {
        "name": "百度千帆",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        "provider_type": "coding_plan",
        "default_model": None,
        "models_api": "/models",
        "auth_type": "access_token"
    },
    "volcengine": {
        "name": "火山方舟",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "provider_type": "coding_plan",
        "default_model": None,
        "models_api": "/models",
        "auth_type": "bearer"
    },
    "unicom": {
        "name": "联通云",
        "base_url": "",  # 待确认
        "provider_type": "coding_plan",
        "default_model": None,
        "models_api": "/v1/models",
        "auth_type": "bearer"
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "provider_type": "single",
        "default_model": "",
        "models_api": "/v1/models",
        "auth_type": "bearer"
    }
}


def get_provider_config(provider: str) -> ProviderConfig | None:
    """获取提供商配置

    Args:
        provider: 提供商标识

    Returns:
        提供商配置，不存在则返回 None
    """
    return PRESET_PROVIDERS.get(provider)


def get_all_providers() -> list[dict]:
    """获取所有预设提供商列表

    Returns:
        提供商列表，包含 id 和 name
    """
    return [
        {"id": key, "name": config["name"]}
        for key, config in PRESET_PROVIDERS.items()
    ]
