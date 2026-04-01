# config.py
"""API 配置和模型选择"""

MODEL_CONFIGS = {
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "",  # 用户需要填入自己的 API Key
        "model": "deepseek-chat"
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "api_key": "",
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