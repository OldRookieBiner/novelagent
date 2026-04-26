"""Error message sanitization utilities for SSE responses"""

import re
from typing import Union

# 敏感信息模式列表
SENSITIVE_PATTERNS = [
    # API Keys
    re.compile(r'(api[_-]?key["\s:=]+["\']?)([a-zA-Z0-9_-]{20,})', re.IGNORECASE),
    re.compile(r'(Bearer\s+)([a-zA-Z0-9_-]{20,})', re.IGNORECASE),
    # Database connection strings
    re.compile(r'(postgresql://[^:]+:)([^@]+)(@)'),
    re.compile(r'(mysql://[^:]+:)([^@]+)(@)'),
    re.compile(r'(mongodb://[^:]+:)([^@]+)(@)'),
    # Passwords in connection strings
    re.compile(r'(password["\s:=]+["\']?)([^\s"\']+)["\']?', re.IGNORECASE),
    # Secret keys
    re.compile(r'(secret[_-]?key["\s:=]+["\']?)([a-zA-Z0-9_-]{16,})', re.IGNORECASE),
    # JWT tokens
    re.compile(r'(eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*)'),
    # Email addresses (partial redaction)
    re.compile(r'([a-zA-Z0-9._%+-]+@)([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'),
    # File paths that might reveal system info
    re.compile(r'(/(?:home|root|etc|var|usr)/[^\s]+)'),
    # IP addresses
    re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'),
]

# 用户友好的错误映射
USER_FRIENDLY_ERRORS = {
    "connection refused": "无法连接到服务，请稍后重试",
    "timeout": "请求超时，请稍后重试",
    "network": "网络错误，请检查网络连接",
    "unauthorized": "未授权访问，请重新登录",
    "forbidden": "权限不足",
    "not found": "资源不存在",
    "rate limit": "请求过于频繁，请稍后重试",
    "quota": "API 配额已用尽",
    "invalid api key": "API 密钥无效",
    "model not found": "模型不存在",
    "context length": "内容超出模型限制",
}


def sanitize_error_message(error: Union[str, Exception]) -> str:
    """
    清理错误消息，移除敏感信息。

    Args:
        error: 原始错误消息或异常对象

    Returns:
        清理后的安全错误消息
    """
    # 转换为字符串
    if isinstance(error, Exception):
        message = str(error)
    else:
        message = error

    # 检查是否是已知的用户友好错误
    message_lower = message.lower()
    for pattern, friendly_msg in USER_FRIENDLY_ERRORS.items():
        if pattern in message_lower:
            return friendly_msg

    # 应用敏感信息清理模式
    for pattern in SENSITIVE_PATTERNS:
        if pattern.groups > 1:
            # 保留部分信息，隐藏敏感部分
            message = pattern.sub(r'\1***REDACTED***', message)
        else:
            message = pattern.sub('***REDACTED***', message)

    # 如果错误消息过长，截断并添加省略号
    if len(message) > 200:
        message = message[:200] + "..."

    # 如果清理后消息为空，返回通用错误
    if not message.strip():
        return "发生未知错误"

    return message


def format_sse_error(error: Union[str, Exception]) -> str:
    """
    格式化 SSE 错误事件。

    Args:
        error: 原始错误消息或异常对象

    Returns:
        格式化的 SSE 错误事件字符串
    """
    import json
    safe_message = sanitize_error_message(error)
    return f"event: error\ndata: {json.dumps({'error': safe_message})}\n\n"
