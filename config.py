# config.py
"""API 配置和模型选择"""

import os

MODEL_CONFIGS = {
    "deepseek": {
        # 火山方舟 API (OpenAI 兼容接口)
        "api_base": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "model": "deepseek-v3-241227"  # DeepSeek V3.2
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "model": "gpt-4"
    },
}

CURRENT_MODEL = "deepseek"

# 信息收集阶段需要满足的标准
INFO_REQUIRED_FIELDS = [
    "genre",           # 题材类型
    "theme",           # 核心主题
    "main_characters", # 主角设定
    "world_setting",   # 世界设定
    "style_preference",# 风格偏好或目标篇幅
]

# 数据存储路径
DATA_DIR = "data/projects"