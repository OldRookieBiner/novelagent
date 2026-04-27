"""Pydantic schemas for system prompts"""

from datetime import datetime
from typing import Optional, Literal, TypedDict
from pydantic import BaseModel


class AgentTypeMeta(TypedDict):
    """Metadata for an agent type"""
    name: str
    description: str
    variables: list[str]
    variable_descriptions: dict[str, str]


AgentTypeKey = Literal[
    "outline_generation",
    "chapter_outline_generation",
    "chapter_content_generation",
    "review",
    "rewrite"
]


# Agent type metadata with variable descriptions
AGENT_TYPES: dict[AgentTypeKey, AgentTypeMeta] = {
    "outline_generation": {
        "name": "大纲生成",
        "description": "根据灵感信息生成结构化大纲，包含人物设定、世界观、情节节点",
        "variables": ["inspiration_template", "chapter_count"],
        "variable_descriptions": {
            "inspiration_template": "用户输入的创作灵感，包含类型、风格、偏好等",
            "chapter_count": "目标章节数量"
        }
    },
    "chapter_outline_generation": {
        "name": "章节大纲生成",
        "description": "生成每个章节的详细大纲，包含场景、人物、情节、冲突、钩子",
        "variables": ["outline", "plot_points", "chapter_count", "chapter_number", "previous_chapters_info"],
        "variable_descriptions": {
            "outline": "小说整体大纲内容",
            "plot_points": "主要情节节点列表",
            "chapter_count": "总章节数",
            "chapter_number": "当前章节序号",
            "previous_chapters_info": "前几章的内容概要，用于衔接"
        }
    },
    "chapter_content_generation": {
        "name": "正文生成",
        "description": "根据章节大纲写正文，遵循写作原则减少 AI 味",
        "variables": ["chapter_outline", "previous_ending", "genre", "main_characters", "world_setting", "style_preference"],
        "variable_descriptions": {
            "chapter_outline": "当前章节的大纲，包含标题、场景、人物、情节等",
            "previous_ending": "上一章结尾的内容，用于衔接",
            "genre": "小说题材类型，如都市、玄幻、悬疑等",
            "main_characters": "主角及主要人物设定",
            "world_setting": "世界观和背景设定",
            "style_preference": "写作风格偏好"
        }
    },
    "review": {
        "name": "审核",
        "description": "审核章节质量，输出分项评分和修改建议",
        "variables": ["strictness", "chapter_outline", "chapter_content", "genre", "main_characters", "style_preference"],
        "variable_descriptions": {
            "strictness": "审核严格度：loose/standard/strict",
            "chapter_outline": "章节大纲",
            "chapter_content": "待审核的章节正文",
            "genre": "小说题材",
            "main_characters": "主要人物设定",
            "style_preference": "写作风格偏好"
        }
    },
    "rewrite": {
        "name": "重写",
        "description": "根据审核反馈重写章节正文",
        "variables": ["chapter_outline", "review_feedback", "original_content", "genre", "main_characters", "world_setting"],
        "variable_descriptions": {
            "chapter_outline": "章节大纲",
            "review_feedback": "审核反馈，包含问题列表和修改建议",
            "original_content": "需要重写的原始章节内容",
            "genre": "小说题材",
            "main_characters": "主要人物设定",
            "world_setting": "世界观设定"
        }
    }
}


class SystemPromptResponse(BaseModel):
    """Response for a single system prompt"""
    agent_type: str
    agent_name: str
    description: str
    prompt_content: str
    variables: list[str]
    variable_descriptions: dict[str, str]
    updated_at: Optional[datetime] = None


class SystemPromptListResponse(BaseModel):
    """Response for list of system prompts"""
    prompts: list[SystemPromptResponse]


class SystemPromptUpdate(BaseModel):
    """Request to update a system prompt"""
    prompt_content: str