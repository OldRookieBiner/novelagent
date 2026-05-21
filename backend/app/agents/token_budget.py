"""Token 预算计算模块 — 基于模型上下文窗口动态分配 token 预算"""

import re
from typing import Optional

from app.agents.constants import MODEL_CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW


def estimate_tokens(text: str) -> int:
    """估算中文文本的 token 数（保守估计）

    中文约 1.5-2 token/字，取 2 保守估算。
    英文约 0.25-0.5 token/char，取 0.5 估算。
    """
    chinese_chars = len(re.findall(r'[一-龥]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 2 + other_chars * 0.5)


def get_context_window(model_name: str, model_config=None) -> int:
    """获取模型上下文窗口大小（三级策略）

    1. DB 配置优先（ModelConfig.context_window）
    2. 硬编码映射（MODEL_CONTEXT_WINDOWS）
    3. 安全默认值（DEFAULT_CONTEXT_WINDOW = 32K）
    """
    # 级别 1: DB 配置
    if model_config and getattr(model_config, 'context_window', None):
        return model_config.context_window
    # 级别 2: 硬编码映射
    if model_name in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_name]
    # 级别 3: 安全默认值
    return DEFAULT_CONTEXT_WINDOW


def calculate_context_budget(
    model_max_tokens: int,
    target_output_tokens: int,
    system_prompt_tokens: int,
    safety_margin: float = 0.1,
) -> int:
    """计算可用于前文上下文的 token 预算

    Args:
        model_max_tokens: 模型最大上下文窗口
        target_output_tokens: 预期输出 token 数
        system_prompt_tokens: system prompt 注入后的估算 token 数
        safety_margin: 安全余量比例（默认 10%）

    Returns:
        可用于前文上下文的 token 数（非负）
    """
    available = model_max_tokens - target_output_tokens - system_prompt_tokens
    return max(int(available * (1 - safety_margin)), 0)
