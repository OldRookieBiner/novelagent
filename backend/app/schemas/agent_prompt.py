"""Pydantic schemas for agent prompts"""

from datetime import datetime
from typing import Optional, Literal, TypedDict
from pydantic import BaseModel


# Type-safe agent type definitions
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
        "name": "大纲生成智能体",
        "description": "根据灵感信息生成结构化大纲，包含人物设定、世界观、情节节点",
        "variables": ["collected_info", "target_words"]
    },
    "chapter_outline_generation": {
        "name": "章节纲生成智能体",
        "description": "生成每个章节的详细大纲，包含场景、人物、情节、冲突、钩子",
        "variables": ["outline", "chapter_count", "chapter_number", "previous_chapters"]
    },
    "chapter_content_generation": {
        "name": "章节正文生成智能体",
        "description": "根据章节纲写正文，遵循写作原则减少 AI 味",
        "variables": ["chapter_outline", "previous_ending", "characters", "world_setting", "style_preference"]
    },
    "review": {
        "name": "审核智能体",
        "description": "审核章节质量，输出分项评分和修改建议",
        "variables": ["chapter_content", "chapter_outline", "characters", "world_setting", "style_preference"]
    },
    "rewrite": {
        "name": "重写智能体",
        "description": "根据审核反馈重写章节正文",
        "variables": ["chapter_outline", "original_content", "review_feedback", "characters", "world_setting"]
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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class ProjectAgentPromptsResponse(BaseModel):
    """Response for project's agent prompts configuration"""
    project_id: int
    project_name: str
    agents: list[ProjectAgentPromptItem]


class EffectivePromptResponse(BaseModel):
    """Response for effective prompt (used internally)"""
    source: Literal["custom", "global", "system_default"]
    prompt_content: str