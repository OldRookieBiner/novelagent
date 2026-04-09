"""Pydantic schemas for agent prompts"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# Agent type metadata
AGENT_TYPES = {
    "info_collection": {
        "name": "信息收集智能体",
        "description": "对话式收集小说创作信息",
        "variables": ["collected_info", "genre", "theme", "main_characters", "world_setting", "style_preference"]
    },
    "outline_generation": {
        "name": "大纲生成智能体",
        "description": "根据收集的信息生成小说大纲",
        "variables": ["collected_info", "genre", "theme", "main_characters", "world_setting", "style_preference"]
    },
    "chapter_count_suggestion": {
        "name": "章节数建议智能体",
        "description": "根据大纲建议章节数",
        "variables": ["outline"]
    },
    "chapter_outline_generation": {
        "name": "章节纲生成智能体",
        "description": "生成每个章节的详细大纲",
        "variables": ["outline", "chapter_count", "genre", "theme", "main_characters", "world_setting", "style_preference"]
    },
    "chapter_content_generation": {
        "name": "章节正文生成智能体",
        "description": "根据章节纲写正文",
        "variables": ["chapter_outline", "previous_ending", "genre", "theme", "main_characters", "world_setting", "style_preference"]
    },
    "review": {
        "name": "审核智能体",
        "description": "审核章节质量",
        "variables": ["chapter_content", "chapter_outline", "strictness", "genre", "theme", "main_characters", "style_preference"]
    },
    "rewrite": {
        "name": "重写智能体",
        "description": "根据审核反馈重写章节",
        "variables": ["chapter_outline", "review_feedback", "original_content", "genre", "theme", "main_characters", "world_setting", "style_preference"]
    }
}


class AgentPromptResponse(BaseModel):
    """Response for a single agent prompt"""
    agent_type: str
    agent_name: str
    description: str
    prompt_content: str
    variables: list[str]
    is_default: bool  # True if using system default (not customized)
    updated_at: Optional[datetime] = None


class AgentPromptListResponse(BaseModel):
    """Response for list of agent prompts"""
    prompts: list[AgentPromptResponse]


class AgentPromptUpdate(BaseModel):
    """Request to update an agent prompt"""
    prompt_content: str


class ProjectAgentPromptItem(BaseModel):
    """Single agent prompt status for a project"""
    agent_type: str
    agent_name: str
    description: str
    use_custom: bool
    custom_content: Optional[str] = None
    variables: list[str]


class ProjectAgentPromptsResponse(BaseModel):
    """Response for project's agent prompts configuration"""
    project_id: int
    project_name: str
    agents: list[ProjectAgentPromptItem]


class EffectivePromptResponse(BaseModel):
    """Response for effective prompt (used internally)"""
    source: str  # "custom", "global", "system_default"
    prompt_content: str