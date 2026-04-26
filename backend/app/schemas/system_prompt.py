"""Pydantic schemas for system prompts"""

from datetime import datetime
from typing import Optional, Literal, TypedDict
from pydantic import BaseModel


class AgentTypeMeta(TypedDict):
    """Metadata for an agent type"""
    name: str
    description: str
    variables: list[str]


AgentTypeKey = Literal[
    "outline_generation",
    "chapter_outline_generation",
    "chapter_content_generation",
    "review",
    "rewrite"
]


# Agent type metadata
AGENT_TYPES: dict[AgentTypeKey, AgentTypeMeta] = {
    "outline_generation": {
        "name": "大纲生成",
        "description": "根据灵感信息生成结构化大纲，包含人物设定、世界观、情节节点",
        "variables": ["inspiration_template", "chapter_count"]
    },
    "chapter_outline_generation": {
        "name": "章节大纲生成",
        "description": "生成每个章节的详细大纲，包含场景、人物、情节、冲突、钩子",
        "variables": ["outline", "plot_points", "chapter_count", "chapter_number", "previous_chapter_info"]
    },
    "chapter_content_generation": {
        "name": "正文生成",
        "description": "根据章节大纲写正文，遵循写作原则减少 AI 味",
        "variables": ["chapter_outline", "previous_ending", "genre", "main_characters", "world_setting", "style_preference"]
    },
    "review": {
        "name": "审核",
        "description": "审核章节质量，输出分项评分和修改建议",
        "variables": ["strictness", "chapter_outline", "chapter_content", "genre", "main_characters", "style_preference"]
    },
    "rewrite": {
        "name": "重写",
        "description": "根据审核反馈重写章节正文",
        "variables": ["chapter_outline", "review_feedback", "original_content", "genre", "main_characters", "world_setting"]
    }
}


class SystemPromptResponse(BaseModel):
    """Response for a single system prompt"""
    agent_type: str
    agent_name: str
    description: str
    prompt_content: str
    variables: list[str]
    updated_at: Optional[datetime] = None


class SystemPromptListResponse(BaseModel):
    """Response for list of system prompts"""
    prompts: list[SystemPromptResponse]


class SystemPromptUpdate(BaseModel):
    """Request to update a system prompt"""
    prompt_content: str
