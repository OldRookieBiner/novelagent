"""Token 预算计算模块 — 基于模型上下文窗口动态分配 token 预算"""

import re
from typing import Optional

# 上下文窗口默认值：用户未在设置中配置时的兜底值
DEFAULT_CONTEXT_WINDOW = 262144  # 256K

# Agent 聊天输出 token 上限（ReAct 模式：推理文本 + 工具调用）
# 输出上限是模型 API 的独立约束，不应从上下文总长度推算
DEFAULT_AGENT_MAX_OUTPUT_TOKENS = 131072  # 128K

# 预编译 CJK 字符正则，避免每次调用 re.findall 重新编译
_CJK_RE = re.compile(r'[一-龥]')


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数

    基于 DeepSeek V4 分词器参数，保守系数 1.2：
    中文约 0.6 token/字 × 1.2 = 0.72 token/字
    英文约 0.3 token/char × 1.2 = 0.36 token/char
    非空文本最少返回 1，避免 0 值导致上下文策略误判为无内容。
    """
    if not text:
        return 0
    chinese_chars = len(_CJK_RE.findall(text))
    other_chars = len(text) - chinese_chars
    return max(int(chinese_chars * 0.72 + other_chars * 0.36), 1)


def get_context_window(model_config=None, model_name: str | None = None) -> int:
    """获取模型上下文窗口大小

    优先级：
    1. 子模型的 context_window（coding_plan 类型 + model_name 指定时）
    2. 配置级别的 context_window
    3. 默认值 256K

    Args:
        model_config: ModelConfig ORM 对象（可选）
        model_name: 具体子模型名（coding_plan 类型时匹配子模型，可选）
    """
    # 级别 1: 子模型 context_window（coding_plan 类型的配置）
    if model_config and model_name and model_config.models:
        for m in model_config.models:
            if m.get("is_enabled", True) and (m.get("id") == model_name or m.get("name") == model_name):
                if m.get("context_window"):
                    return m["context_window"]
                break

    # 级别 2: 配置级别 context_window
    if model_config and getattr(model_config, 'context_window', None):
        return model_config.context_window

    # 级别 3: 默认值
    return DEFAULT_CONTEXT_WINDOW


def calculate_context_budget(
    model_max_tokens: int,
    target_output_tokens: int,
    system_prompt_tokens: int,
    user_prompt_tokens: int = 0,
    safety_margin: float = 0.1,
) -> int:
    """计算可用于前文上下文的 token 预算

    Args:
        model_max_tokens: 模型最大上下文窗口
        target_output_tokens: 预期输出 token 数
        system_prompt_tokens: system prompt 注入后的估算 token 数
        user_prompt_tokens: user prompt 模板估算 token 数（默认 0，向后兼容）
        safety_margin: 安全余量比例（默认 10%）

    Returns:
        可用于前文上下文的 token 数（非负）
    """
    available = model_max_tokens - target_output_tokens - system_prompt_tokens - user_prompt_tokens
    return max(int(available * (1 - safety_margin)), 0)
