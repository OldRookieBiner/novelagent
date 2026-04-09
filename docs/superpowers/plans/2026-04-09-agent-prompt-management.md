# AI 智能体管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现智能体 Prompt 管理功能，支持全局默认配置和项目级别覆盖。

**Architecture:** 新增两张数据库表（agent_prompts, project_agent_prompts）存储 Prompt 配置；新增 API 端点管理全局和项目 Prompts；扩展 Settings 页面新增"智能体管理"标签页；修改现有 LLM 调用逻辑从数据库获取 Prompt。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, Zustand, shadcn/ui

---

## 文件结构

**新增文件：**
```
backend/app/models/agent_prompt.py          # 数据模型
backend/app/schemas/agent_prompt.py         # Pydantic schemas
backend/app/api/agent_prompts.py            # API 路由
backend/app/services/prompt_service.py      # Prompt 服务
backend/alembic/versions/003_add_agent_prompts.py  # 数据库迁移
backend/tests/test_agent_prompts.py         # API 测试
frontend/src/components/settings/AgentPromptEditor.tsx  # Prompt 编辑器组件
frontend/src/components/settings/ProjectPromptConfig.tsx  # 项目配置组件
frontend/src/stores/agentPromptStore.ts     # 状态管理
```

**修改文件：**
```
backend/app/models/__init__.py              # 导入新模型
backend/app/agents/prompts.py               # 添加 DEFAULT_PROMPTS 字典
backend/app/agents/nodes/outline_generation.py  # 使用 prompt_service
backend/app/agents/nodes/info_collection.py      # 使用 prompt_service
backend/app/agents/nodes/chapter_generation.py   # 使用 prompt_service
backend/app/main.py                         # 注册新路由
frontend/src/pages/Settings.tsx             # 添加智能体管理标签页
frontend/src/lib/api.ts                     # 添加 API 调用
frontend/src/types/index.ts                 # 添加类型定义
```

---

## Task 1: 数据库模型和迁移

**Files:**
- Create: `backend/app/models/agent_prompt.py`
- Create: `backend/alembic/versions/003_add_agent_prompts.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 agent_prompt.py 数据模型**

```python
# backend/app/models/agent_prompt.py
"""Agent prompt models"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class AgentPrompt(Base):
    """Global agent prompts for a user"""
    __tablename__ = "agent_prompts"
    __table_args__ = (
        UniqueConstraint('user_id', 'agent_type', name='uq_user_agent_type'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(String(50), nullable=False)
    prompt_content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="agent_prompts")


class ProjectAgentPrompt(Base):
    """Project-specific agent prompt overrides"""
    __tablename__ = "project_agent_prompts"
    __table_args__ = (
        UniqueConstraint('project_id', 'agent_type', name='uq_project_agent_type'),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(String(50), nullable=False)
    prompt_content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="agent_prompts")
```

- [ ] **Step 2: 更新 models/__init__.py 导入**

```python
# backend/app/models/__init__.py
"""Database models"""

from app.models.user import User
from app.models.settings import UserSettings
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt

__all__ = [
    "User", "UserSettings", "Project", "Outline", "ChapterOutline", "Chapter",
    "AgentPrompt", "ProjectAgentPrompt"
]
```

- [ ] **Step 3: 创建 Alembic 迁移脚本**

```python
# backend/alembic/versions/003_add_agent_prompts.py
"""add agent prompts tables

Revision ID: 003
Revises: 002_add_indexes
Create Date: 2026-04-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003'
down_revision = '002_add_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_prompts table
    op.create_table(
        'agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'agent_type', name='uq_user_agent_type')
    )
    op.create_index('ix_agent_prompts_user_id', 'agent_prompts', ['user_id'])

    # Create project_agent_prompts table
    op.create_table(
        'project_agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'agent_type', name='uq_project_agent_type')
    )
    op.create_index('ix_project_agent_prompts_project_id', 'project_agent_prompts', ['project_id'])


def downgrade():
    op.drop_index('ix_project_agent_prompts_project_id', 'project_agent_prompts')
    op.drop_table('project_agent_prompts')
    op.drop_index('ix_agent_prompts_user_id', 'agent_prompts')
    op.drop_table('agent_prompts')
```

- [ ] **Step 4: 运行迁移验证**

Run: `docker exec novelagent-backend-1 alembic upgrade head`
Expected: 迁移成功，无错误

- [ ] **Step 5: 提交数据库模型**

```bash
git add backend/app/models/agent_prompt.py backend/app/models/__init__.py backend/alembic/versions/003_add_agent_prompts.py
git commit -m "feat: add agent prompt database models and migration"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/agent_prompt.py`

- [ ] **Step 1: 创建 schemas**

```python
# backend/app/schemas/agent_prompt.py
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
```

- [ ] **Step 2: 提交 schemas**

```bash
git add backend/app/schemas/agent_prompt.py
git commit -m "feat: add agent prompt pydantic schemas"
```

---

## Task 3: Prompt Service

**Files:**
- Create: `backend/app/services/prompt_service.py`
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 更新 prompts.py 添加 DEFAULT_PROMPTS 字典**

在 `backend/app/agents/prompts.py` 末尾添加：

```python
# Default prompts dictionary for system defaults
DEFAULT_PROMPTS = {
    "info_collection": INFO_COLLECTION_SYSTEM_PROMPT,
    "outline_generation": GENERATE_OUTLINE_PROMPT,
    "chapter_count_suggestion": SUGGEST_CHAPTER_COUNT_PROMPT,
    "chapter_outline_generation": GENERATE_CHAPTER_OUTLINES_PROMPT,
    "chapter_content_generation": GENERATE_CHAPTER_CONTENT_PROMPT,
    "review": REVIEW_CHAPTER_PROMPT,
    "rewrite": REWRITE_CHAPTER_PROMPT,
}
```

- [ ] **Step 2: 创建 prompt_service.py**

```python
# backend/app/services/prompt_service.py
"""Service for managing and retrieving agent prompts"""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt
from app.agents.prompts import DEFAULT_PROMPTS


def get_effective_prompt(
    db: Session,
    user_id: int,
    project_id: int,
    agent_type: str
) -> tuple[str, str]:
    """
    Get the effective prompt for a project's agent.
    
    Returns: (prompt_content, source)
    - source: "custom" | "global" | "system_default"
    
    Priority: project_custom > global > system_default
    """
    # 1. Check project custom prompt
    custom = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()
    if custom:
        return custom.prompt_content, "custom"
    
    # 2. Check global prompt
    global_prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == user_id,
        AgentPrompt.agent_type == agent_type
    ).first()
    if global_prompt:
        return global_prompt.prompt_content, "global"
    
    # 3. Return system default
    default = DEFAULT_PROMPTS.get(agent_type, "")
    return default, "system_default"


def ensure_user_has_global_prompts(db: Session, user_id: int) -> None:
    """
    Ensure user has global prompt entries for all agent types.
    Called when user first accesses agent management page.
    """
    existing_types = set(
        p.agent_type for p in db.query(AgentPrompt.agent_type).filter(
            AgentPrompt.user_id == user_id
        ).all()
    )
    
    for agent_type, default_content in DEFAULT_PROMPTS.items():
        if agent_type not in existing_types:
            prompt = AgentPrompt(
                user_id=user_id,
                agent_type=agent_type,
                prompt_content=default_content
            )
            db.add(prompt)
    
    db.commit()
```

- [ ] **Step 3: 提交 prompt service**

```bash
git add backend/app/services/prompt_service.py backend/app/agents/prompts.py
git commit -m "feat: add prompt service for managing agent prompts"
```

---

## Task 4: API 端点 - 全局 Prompts

**Files:**
- Create: `backend/app/api/agent_prompts.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 API 路由**

```python
# backend/app/api/agent_prompts.py
"""API routes for agent prompt management"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt
from app.models.project import Project
from app.schemas.agent_prompt import (
    AgentPromptResponse,
    AgentPromptListResponse,
    AgentPromptUpdate,
    ProjectAgentPromptsResponse,
    ProjectAgentPromptItem,
    EffectivePromptResponse,
    AGENT_TYPES,
)
from app.services.prompt_service import get_effective_prompt, ensure_user_has_global_prompts
from app.services.prompt_service import DEFAULT_PROMPTS
from app.utils.auth import get_current_user

router = APIRouter()


# ==================== Global Prompts ====================

@router.get("/agent-prompts", response_model=AgentPromptListResponse)
async def get_global_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all global agent prompts for current user"""
    # Ensure user has prompts initialized
    ensure_user_has_global_prompts(db, current_user.id)
    
    prompts = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id
    ).all()
    
    prompt_map = {p.agent_type: p for p in prompts}
    
    result = []
    for agent_type, meta in AGENT_TYPES.items():
        prompt = prompt_map.get(agent_type)
        is_default = prompt is None or prompt.prompt_content == DEFAULT_PROMPTS.get(agent_type, "")
        
        result.append(AgentPromptResponse(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            prompt_content=prompt.prompt_content if prompt else DEFAULT_PROMPTS.get(agent_type, ""),
            variables=meta["variables"],
            is_default=is_default,
            updated_at=prompt.updated_at if prompt else None
        ))
    
    return AgentPromptListResponse(prompts=result)


@router.put("/agent-prompts/{agent_type}", response_model=AgentPromptResponse)
async def update_global_prompt(
    agent_type: str,
    request: AgentPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a global agent prompt"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id,
        AgentPrompt.agent_type == agent_type
    ).first()
    
    if prompt:
        prompt.prompt_content = request.prompt_content
    else:
        prompt = AgentPrompt(
            user_id=current_user.id,
            agent_type=agent_type,
            prompt_content=request.prompt_content
        )
        db.add(prompt)
    
    db.commit()
    db.refresh(prompt)
    
    meta = AGENT_TYPES[agent_type]
    is_default = prompt.prompt_content == DEFAULT_PROMPTS.get(agent_type, "")
    
    return AgentPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=prompt.prompt_content,
        variables=meta["variables"],
        is_default=is_default,
        updated_at=prompt.updated_at
    )


@router.post("/agent-prompts/{agent_type}/reset", response_model=AgentPromptResponse)
async def reset_global_prompt(
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reset a global agent prompt to system default"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    default_content = DEFAULT_PROMPTS.get(agent_type, "")
    
    prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == current_user.id,
        AgentPrompt.agent_type == agent_type
    ).first()
    
    if prompt:
        prompt.prompt_content = default_content
    else:
        prompt = AgentPrompt(
            user_id=current_user.id,
            agent_type=agent_type,
            prompt_content=default_content
        )
        db.add(prompt)
    
    db.commit()
    db.refresh(prompt)
    
    meta = AGENT_TYPES[agent_type]
    
    return AgentPromptResponse(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        prompt_content=prompt.prompt_content,
        variables=meta["variables"],
        is_default=True,
        updated_at=prompt.updated_at
    )


# ==================== Project Custom Prompts ====================

@router.get("/projects/{project_id}/agent-prompts", response_model=ProjectAgentPromptsResponse)
async def get_project_agent_prompts(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent prompts configuration for a project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get custom prompts for this project
    custom_prompts = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id
    ).all()
    
    custom_map = {p.agent_type: p for p in custom_prompts}
    
    agents = []
    for agent_type, meta in AGENT_TYPES.items():
        custom = custom_map.get(agent_type)
        agents.append(ProjectAgentPromptItem(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            use_custom=custom is not None,
            custom_content=custom.prompt_content if custom else None,
            variables=meta["variables"]
        ))
    
    return ProjectAgentPromptsResponse(
        project_id=project_id,
        project_name=project.name,
        agents=agents
    )


@router.put("/projects/{project_id}/agent-prompts/{agent_type}", response_model=ProjectAgentPromptItem)
async def set_project_custom_prompt(
    project_id: int,
    agent_type: str,
    request: AgentPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set a custom prompt for a project's agent"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    prompt = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()
    
    if prompt:
        prompt.prompt_content = request.prompt_content
    else:
        prompt = ProjectAgentPrompt(
            project_id=project_id,
            agent_type=agent_type,
            prompt_content=request.prompt_content
        )
        db.add(prompt)
    
    db.commit()
    db.refresh(prompt)
    
    meta = AGENT_TYPES[agent_type]
    return ProjectAgentPromptItem(
        agent_type=agent_type,
        agent_name=meta["name"],
        description=meta["description"],
        use_custom=True,
        custom_content=prompt.prompt_content,
        variables=meta["variables"]
    )


@router.delete("/projects/{project_id}/agent-prompts/{agent_type}")
async def delete_project_custom_prompt(
    project_id: int,
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a project's custom prompt, reverting to global default"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    prompt = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()
    
    if prompt:
        db.delete(prompt)
        db.commit()
    
    return {"success": True}


@router.get("/projects/{project_id}/agent-prompts/{agent_type}/effective", response_model=EffectivePromptResponse)
async def get_effective_prompt_api(
    project_id: int,
    agent_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the effective prompt for a project's agent (for internal use)"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    content, source = get_effective_prompt(db, current_user.id, project_id, agent_type)
    
    return EffectivePromptResponse(
        source=source,
        prompt_content=content
    )
```

- [ ] **Step 2: 在 main.py 注册路由**

在 `backend/app/main.py` 中添加导入和路由注册：

```python
# 在 imports 部分添加
from app.api import auth, projects, outline, chapters, settings, agent_prompts

# 在 routers 部分添加
app.include_router(agent_prompts.router, prefix="/api")
```

- [ ] **Step 3: 重启后端验证**

Run: `docker compose restart backend`
Expected: 后端重启成功，无错误

- [ ] **Step 4: 提交 API 路由**

```bash
git add backend/app/api/agent_prompts.py backend/app/main.py
git commit -m "feat: add agent prompts API endpoints"
```

---

## Task 5: 后端测试

**Files:**
- Create: `backend/tests/test_agent_prompts.py`

- [ ] **Step 1: 创建测试文件**

```python
# backend/tests/test_agent_prompts.py
"""Tests for agent prompts API endpoints"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.project import Project
from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt


class TestGlobalAgentPromptsAPI:
    """Tests for global agent prompts API"""

    def test_get_global_prompts(self, client: TestClient, auth_headers: dict):
        """Should return all global prompts"""
        response = client.get("/api/agent-prompts", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert len(data["prompts"]) == 7  # 7 agent types

    def test_update_global_prompt(self, client: TestClient, auth_headers: dict, db: Session):
        """Should update a global prompt"""
        response = client.put(
            "/api/agent-prompts/info_collection",
            json={"prompt_content": "Custom prompt content"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "info_collection"
        assert data["prompt_content"] == "Custom prompt content"
        assert data["is_default"] is False

    def test_reset_global_prompt(self, client: TestClient, auth_headers: dict):
        """Should reset a global prompt to default"""
        # First update
        client.put(
            "/api/agent-prompts/info_collection",
            json={"prompt_content": "Custom prompt"},
            headers=auth_headers
        )
        
        # Then reset
        response = client.post(
            "/api/agent-prompts/info_collection/reset",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True

    def test_update_unknown_agent_type(self, client: TestClient, auth_headers: dict):
        """Should return 404 for unknown agent type"""
        response = client.put(
            "/api/agent-prompts/unknown_type",
            json={"prompt_content": "test"},
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestProjectAgentPromptsAPI:
    """Tests for project agent prompts API"""

    @pytest.fixture
    def test_project(self, client: TestClient, auth_headers: dict) -> int:
        """Create a test project and return its ID"""
        response = client.post(
            "/api/projects/",
            json={"name": "Test Project"},
            headers=auth_headers
        )
        return response.json()["id"]

    def test_get_project_prompts(self, client: TestClient, auth_headers: dict, test_project: int):
        """Should return project prompts configuration"""
        response = client.get(
            f"/api/projects/{test_project}/agent-prompts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == test_project
        assert len(data["agents"]) == 7
        # All should use global by default
        for agent in data["agents"]:
            assert agent["use_custom"] is False

    def test_set_project_custom_prompt(self, client: TestClient, auth_headers: dict, test_project: int):
        """Should set a custom prompt for project"""
        response = client.put(
            f"/api/projects/{test_project}/agent-prompts/outline_generation",
            json={"prompt_content": "Project specific prompt"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["use_custom"] is True
        assert data["custom_content"] == "Project specific prompt"

    def test_delete_project_custom_prompt(self, client: TestClient, auth_headers: dict, test_project: int):
        """Should delete custom prompt and revert to global"""
        # Set custom
        client.put(
            f"/api/projects/{test_project}/agent-prompts/outline_generation",
            json={"prompt_content": "Custom"},
            headers=auth_headers
        )
        
        # Delete
        response = client.delete(
            f"/api/projects/{test_project}/agent-prompts/outline_generation",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify reverted
        get_response = client.get(
            f"/api/projects/{test_project}/agent-prompts",
            headers=auth_headers
        )
        agents = get_response.json()["agents"]
        outline_agent = next(a for a in agents if a["agent_type"] == "outline_generation")
        assert outline_agent["use_custom"] is False

    def test_get_effective_prompt(self, client: TestClient, auth_headers: dict, test_project: int):
        """Should return effective prompt"""
        response = client.get(
            f"/api/projects/{test_project}/agent-prompts/outline_generation/effective",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert "prompt_content" in data
```

- [ ] **Step 2: 运行测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_agent_prompts.py -v`
Expected: 所有测试通过

- [ ] **Step 3: 提交测试**

```bash
git add backend/tests/test_agent_prompts.py
git commit -m "test: add agent prompts API tests"
```

---

## Task 6: 前端类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 添加类型定义**

在 `frontend/src/types/index.ts` 末尾添加：

```typescript
// ==================== Agent Prompt Types ====================

export interface AgentPrompt {
  agent_type: string;
  agent_name: string;
  description: string;
  prompt_content: string;
  variables: string[];
  is_default: boolean;
  updated_at?: string;
}

export interface AgentPromptListResponse {
  prompts: AgentPrompt[];
}

export interface AgentPromptUpdate {
  prompt_content: string;
}

export interface ProjectAgentPromptItem {
  agent_type: string;
  agent_name: string;
  description: string;
  use_custom: boolean;
  custom_content?: string;
  variables: string[];
}

export interface ProjectAgentPromptsResponse {
  project_id: number;
  project_name: string;
  agents: ProjectAgentPromptItem[];
}

export interface EffectivePromptResponse {
  source: string;
  prompt_content: string;
}
```

- [ ] **Step 2: 提交类型定义**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add agent prompt type definitions"
```

---

## Task 7: 前端 API 客户端

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 添加 API 调用**

在 `frontend/src/lib/api.ts` 末尾添加：

```typescript
// ==================== Agent Prompts API ====================

export const agentPromptsApi = {
  async getGlobal(): Promise<AgentPromptListResponse> {
    return request<AgentPromptListResponse>("/api/agent-prompts");
  },

  async updateGlobal(
    agentType: string,
    data: AgentPromptUpdate
  ): Promise<AgentPrompt> {
    return request<AgentPrompt>(`/api/agent-prompts/${agentType}`, {
      method: "PUT",
      body: data,
    });
  },

  async resetGlobal(agentType: string): Promise<AgentPrompt> {
    return request<AgentPrompt>(`/api/agent-prompts/${agentType}/reset`, {
      method: "POST",
    });
  },

  async getProject(projectId: number): Promise<ProjectAgentPromptsResponse> {
    return request<ProjectAgentPromptsResponse>(
      `/api/projects/${projectId}/agent-prompts`
    );
  },

  async setProjectCustom(
    projectId: number,
    agentType: string,
    data: AgentPromptUpdate
  ): Promise<ProjectAgentPromptItem> {
    return request<ProjectAgentPromptItem>(
      `/api/projects/${projectId}/agent-prompts/${agentType}`,
      {
        method: "PUT",
        body: data,
      }
    );
  },

  async deleteProjectCustom(
    projectId: number,
    agentType: string
  ): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(
      `/api/projects/${projectId}/agent-prompts/${agentType}`,
      { method: "DELETE" }
    );
  },
};
```

同时在文件顶部的 import type 中添加新类型：

```typescript
import type {
  // ... existing types ...
  AgentPrompt,
  AgentPromptListResponse,
  AgentPromptUpdate,
  ProjectAgentPromptItem,
  ProjectAgentPromptsResponse,
  EffectivePromptResponse,
} from "@/types";
```

- [ ] **Step 2: 提交 API 客户端**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add agent prompts API client"
```

---

## Task 8: 前端状态管理

**Files:**
- Create: `frontend/src/stores/agentPromptStore.ts`

- [ ] **Step 1: 创建 Zustand store**

```typescript
// frontend/src/stores/agentPromptStore.ts
import { create } from 'zustand'
import type { AgentPrompt, ProjectAgentPromptItem } from '@/types'

interface AgentPromptState {
  // Global prompts
  globalPrompts: AgentPrompt[]
  loadingGlobal: boolean
  
  // Project prompts
  projectPrompts: Map<number, ProjectAgentPromptItem[]>
  loadingProject: number | null
  
  // Editing state
  editingAgent: string | null
  editingProjectId: number | null
  
  // Actions
  setGlobalPrompts: (prompts: AgentPrompt[]) => void
  updateGlobalPrompt: (agentType: string, content: string) => void
  setProjectPrompts: (projectId: number, agents: ProjectAgentPromptItem[]) => void
  updateProjectCustom: (projectId: number, agentType: string, content: string) => void
  removeProjectCustom: (projectId: number, agentType: string) => void
  setEditingAgent: (agentType: string | null, projectId: number | null) => void
  setLoadingGlobal: (loading: boolean) => void
  setLoadingProject: (projectId: number | null) => void
}

export const useAgentPromptStore = create<AgentPromptState>((set) => ({
  globalPrompts: [],
  loadingGlobal: false,
  projectPrompts: new Map(),
  loadingProject: null,
  editingAgent: null,
  editingProjectId: null,
  
  setGlobalPrompts: (prompts) => set({ globalPrompts: prompts }),
  
  updateGlobalPrompt: (agentType, content) =>
    set((state) => ({
      globalPrompts: state.globalPrompts.map((p) =>
        p.agent_type === agentType
          ? { ...p, prompt_content: content, is_default: false }
          : p
      ),
    })),
  
  setProjectPrompts: (projectId, agents) =>
    set((state) => {
      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, agents)
      return { projectPrompts: newMap }
    }),
  
  updateProjectCustom: (projectId, agentType, content) =>
    set((state) => {
      const agents = state.projectPrompts.get(projectId)
      if (!agents) return state
      
      const newAgents = agents.map((a) =>
        a.agent_type === agentType
          ? { ...a, use_custom: true, custom_content: content }
          : a
      )
      
      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, newAgents)
      return { projectPrompts: newMap }
    }),
  
  removeProjectCustom: (projectId, agentType) =>
    set((state) => {
      const agents = state.projectPrompts.get(projectId)
      if (!agents) return state
      
      const newAgents = agents.map((a) =>
        a.agent_type === agentType
          ? { ...a, use_custom: false, custom_content: undefined }
          : a
      )
      
      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, newAgents)
      return { projectPrompts: newMap }
    }),
  
  setEditingAgent: (agentType, projectId) =>
    set({ editingAgent: agentType, editingProjectId: projectId }),
  
  setLoadingGlobal: (loading) => set({ loadingGlobal: loading }),
  
  setLoadingProject: (projectId) => set({ loadingProject: projectId }),
}))
```

- [ ] **Step 2: 提交状态管理**

```bash
git add frontend/src/stores/agentPromptStore.ts
git commit -m "feat: add agent prompt Zustand store"
```

---

## Task 9: Prompt 编辑器组件

**Files:**
- Create: `frontend/src/components/settings/AgentPromptEditor.tsx`

- [ ] **Step 1: 创建编辑器组件**

```tsx
// frontend/src/components/settings/AgentPromptEditor.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { AgentPrompt } from '@/types'

interface AgentPromptEditorProps {
  prompt: AgentPrompt
  onSave: (content: string) => Promise<void>
  onReset?: () => Promise<void>
  isProjectLevel?: boolean
  onCancel?: () => void
}

export function AgentPromptEditor({
  prompt,
  onSave,
  onReset,
  isProjectLevel = false,
  onCancel,
}: AgentPromptEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [content, setContent] = useState(prompt.prompt_content)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(content)
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to save prompt:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!onReset) return
    if (!confirm('确定要重置为默认值吗？您的修改将丢失。')) return

    setResetting(true)
    try {
      await onReset()
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to reset prompt:', error)
    } finally {
      setResetting(false)
    }
  }

  const handleCancel = () => {
    setContent(prompt.prompt_content)
    setIsEditing(false)
    onCancel?.()
  }

  if (!isEditing) {
    return (
      <div className="border rounded-lg p-4 mb-3 bg-white hover:border-blue-300 transition-colors">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h4 className="font-medium text-gray-900">{prompt.agent_name}</h4>
            <p className="text-sm text-gray-500">{prompt.description}</p>
          </div>
          <div className="flex items-center gap-2">
            {!prompt.is_default && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                已修改
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditing(true)}
            >
              编辑
            </Button>
          </div>
        </div>
        <div className="text-sm text-gray-600 line-clamp-2 font-mono bg-gray-50 p-2 rounded">
          {prompt.prompt_content.slice(0, 100)}...
        </div>
      </div>
    )
  }

  return (
    <div className="border-2 border-blue-300 rounded-lg p-4 mb-3 bg-blue-50/30">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-blue-700">
          {prompt.agent_name} {isProjectLevel && '(本项目自定义)'}
        </h4>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            取消
          </Button>
          {onReset && !isProjectLevel && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              disabled={resetting}
            >
              {resetting ? '重置中...' : '重置默认'}
            </Button>
          )}
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? '保存中...' : '保存'}
          </Button>
        </div>
      </div>

      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-[200px] font-mono text-sm"
        placeholder="输入 Prompt 内容..."
      />

      <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
        <span>可用变量:</span>
        <div className="flex flex-wrap gap-1">
          {prompt.variables.map((v) => (
            <code
              key={v}
              className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono"
            >
              {`{${v}}`}
            </code>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交编辑器组件**

```bash
git add frontend/src/components/settings/AgentPromptEditor.tsx
git commit -m "feat: add AgentPromptEditor component"
```

---

## Task 10: 项目 Prompt 配置组件

**Files:**
- Create: `frontend/src/components/settings/ProjectPromptConfig.tsx`

- [ ] **Step 1: 创建项目配置组件**

```tsx
// frontend/src/components/settings/ProjectPromptConfig.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { agentPromptsApi } from '@/lib/api'
import type { ProjectAgentPromptItem, ProjectAgentPromptsResponse } from '@/types'

interface ProjectPromptConfigProps {
  projectId: number
  projectName: string
  initialAgents?: ProjectAgentPromptItem[]
  onClose?: () => void
}

export function ProjectPromptConfig({
  projectId,
  projectName,
  initialAgents,
  onClose,
}: ProjectPromptConfigProps) {
  const [agents, setAgents] = useState<ProjectAgentPromptItem[]>(initialAgents || [])
  const [loading, setLoading] = useState(!initialAgents)
  const [editingType, setEditingType] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!initialAgents) {
      loadAgents()
    }
  }, [projectId])

  const loadAgents = async () => {
    setLoading(true)
    try {
      const data = await agentPromptsApi.getProject(projectId)
      setAgents(data.agents)
    } catch (error) {
      console.error('Failed to load project prompts:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStartEdit = (agent: ProjectAgentPromptItem) => {
    setEditingType(agent.agent_type)
    setEditContent(agent.custom_content || '')
  }

  const handleSave = async (agentType: string) => {
    setSaving(true)
    try {
      await agentPromptsApi.setProjectCustom(projectId, agentType, {
        prompt_content: editContent,
      })
      setAgents((prev) =>
        prev.map((a) =>
          a.agent_type === agentType
            ? { ...a, use_custom: true, custom_content: editContent }
            : a
        )
      )
      setEditingType(null)
    } catch (error) {
      console.error('Failed to save:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCustom = async (agentType: string) => {
    if (!confirm('确定要删除自定义配置，恢复使用全局默认吗？')) return

    try {
      await agentPromptsApi.deleteProjectCustom(projectId, agentType)
      setAgents((prev) =>
        prev.map((a) =>
          a.agent_type === agentType
            ? { ...a, use_custom: false, custom_content: undefined }
            : a
        )
      )
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  if (loading) {
    return <div className="p-4">加载中...</div>
  }

  return (
    <div className="border rounded-lg bg-white">
      <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
        <h3 className="font-semibold">{projectName} - 智能体配置</h3>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            关闭
          </Button>
        )}
      </div>

      <div className="p-4 space-y-2">
        {agents.map((agent) => (
          <div key={agent.agent_type} className="border rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="font-medium">{agent.agent_name}</span>
                {agent.use_custom && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                    使用自定义
                  </span>
                )}
              </div>
              
              {editingType === agent.agent_type ? null : agent.use_custom ? (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleStartEdit(agent)}
                  >
                    编辑
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600"
                    onClick={() => handleDeleteCustom(agent.agent_type)}
                  >
                    恢复全局
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleStartEdit(agent)}
                >
                  为此项目自定义
                </Button>
              )}
            </div>

            {editingType === agent.agent_type && (
              <div className="mt-3">
                <Textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="min-h-[150px] font-mono text-sm"
                  placeholder="输入自定义 Prompt..."
                />
                <div className="mt-2 flex items-center justify-between">
                  <div className="text-sm text-gray-500">
                    变量: {agent.variables.map((v) => `{${v}}`).join(' ')}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingType(null)}
                    >
                      取消
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleSave(agent.agent_type)}
                      disabled={saving}
                    >
                      {saving ? '保存中...' : '保存'}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交项目配置组件**

```bash
git add frontend/src/components/settings/ProjectPromptConfig.tsx
git commit -m "feat: add ProjectPromptConfig component"
```

---

## Task 11: 更新 Settings 页面

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 更新 Settings.tsx**

完整更新 `frontend/src/pages/Settings.tsx`：

```tsx
// frontend/src/pages/Settings.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { settingsApi, agentPromptsApi, projectsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import { AgentPromptEditor } from '@/components/settings/AgentPromptEditor'
import { ProjectPromptConfig } from '@/components/settings/ProjectPromptConfig'
import type { UserSettings, SettingsUpdate, AgentPrompt, Project } from '@/types'

const MODEL_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek (火山方舟)' },
  { value: 'deepseek-official', label: 'DeepSeek (官方)' },
  { value: 'openai', label: 'OpenAI' },
]

const REVIEW_STRICTNESS = [
  { value: 'loose', label: '宽松' },
  { value: 'standard', label: '标准' },
  { value: 'strict', label: '严格' },
] as const

type ReviewStrictnessValue = typeof REVIEW_STRICTNESS[number]['value']

const SETTINGS_TABS = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
  { id: 'agents', label: '智能体管理' },
] as const

type SettingsTab = typeof SETTINGS_TABS[number]['id']

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [clearingKey, setClearingKey] = useState(false)

  // Form state
  const [modelProvider, setModelProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [reviewEnabled, setReviewEnabled] = useState(true)
  const [reviewStrictness, setReviewStrictness] = useState<ReviewStrictnessValue>('standard')

  // Agent prompts state
  const [globalPrompts, setGlobalPrompts] = useState<AgentPrompt[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)

  useEffect(() => {
    fetchSettings()
  }, [])

  useEffect(() => {
    if (activeTab === 'agents') {
      fetchGlobalPrompts()
      fetchProjects()
    }
  }, [activeTab])

  const fetchSettings = async () => {
    try {
      const data = await settingsApi.get()
      setSettings(data)
      setModelProvider(data.model_provider)
      setReviewEnabled(data.review_enabled)
      setReviewStrictness(data.review_strictness as ReviewStrictnessValue)
      useSettingsStore.getState().setSettings(data)
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchGlobalPrompts = async () => {
    setLoadingPrompts(true)
    try {
      const data = await agentPromptsApi.getGlobal()
      setGlobalPrompts(data.prompts)
    } catch (err) {
      console.error('Failed to fetch prompts:', err)
    } finally {
      setLoadingPrompts(false)
    }
  }

  const fetchProjects = async () => {
    try {
      const data = await projectsApi.list()
      setProjects(data.projects)
    } catch (err) {
      console.error('Failed to fetch projects:', err)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)

    try {
      const update: SettingsUpdate = {
        model_provider: modelProvider,
        review_enabled: reviewEnabled,
        review_strictness: reviewStrictness,
      }

      if (apiKey) {
        update.api_key = apiKey
      }

      const updated = await settingsApi.update(update)
      setSettings(updated)
      useSettingsStore.getState().setSettings(updated)
      setApiKey('')
      setSaved(true)
    } catch (err) {
      console.error('Failed to save settings:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleClearApiKey = async () => {
    if (!confirm('确定要删除已配置的 API Key 吗？删除后将无法使用 AI 功能。')) {
      return
    }

    setClearingKey(true)
    try {
      const updated = await settingsApi.update({ clear_api_key: true })
      setSettings(updated)
      useSettingsStore.getState().setSettings(updated)
    } catch (err) {
      console.error('Failed to clear API key:', err)
    } finally {
      setClearingKey(false)
    }
  }

  const handleSaveGlobalPrompt = async (agentType: string, content: string) => {
    const updated = await agentPromptsApi.updateGlobal(agentType, { prompt_content: content })
    setGlobalPrompts((prev) =>
      prev.map((p) => (p.agent_type === agentType ? updated : p))
    )
  }

  const handleResetGlobalPrompt = async (agentType: string) => {
    const updated = await agentPromptsApi.resetGlobal(agentType)
    setGlobalPrompts((prev) =>
      prev.map((p) => (p.agent_type === agentType ? updated : p))
    )
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="flex flex-1">
      {/* 左侧导航栏 */}
      <nav className="w-[220px] border-r bg-background">
        <div className="p-4 border-b">
          <h2 className="font-semibold">设置</h2>
        </div>
        <div className="p-3 space-y-1" role="tablist">
          {SETTINGS_TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full px-3 py-2 text-sm rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-secondary text-foreground font-medium'
                  : 'bg-transparent text-muted-foreground hover:bg-secondary/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* 右侧内容区 */}
      <div className="flex-1 p-6 flex flex-col overflow-auto">
        {activeTab === 'model' && (
          <div id="model-panel" role="tabpanel" className="max-w-xl">
            <h3 className="text-lg font-semibold mb-1">模型配置</h3>
            <p className="text-muted-foreground text-sm mb-6">配置 AI 模型和 API Key</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">模型提供商</label>
                <select
                  className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  value={modelProvider}
                  onChange={(e) => setModelProvider(e.target.value)}
                >
                  {MODEL_PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  API Key {settings?.has_api_key && <span className="text-green-600">(已设置)</span>}
                </label>
                <Input
                  type="password"
                  placeholder={settings?.has_api_key ? '输入新的 API Key 以更新' : '输入 API Key'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">API Key 会被加密存储</p>
              </div>

              {settings?.has_api_key && (
                <Button
                  variant="outline"
                  onClick={handleClearApiKey}
                  disabled={clearingKey}
                  className="text-red-600 hover:text-red-700"
                >
                  {clearingKey ? '删除中...' : '删除 API Key'}
                </Button>
              )}
            </div>
          </div>
        )}

        {activeTab === 'review' && (
          <div id="review-panel" role="tabpanel" className="max-w-xl">
            <h3 className="text-lg font-semibold mb-1">审核设置</h3>
            <p className="text-muted-foreground text-sm mb-6">配置章节审核行为</p>

            <div className="space-y-4">
              <div className="flex items-center justify-between py-2">
                <label className="text-sm font-medium">启用审核</label>
                <input
                  type="checkbox"
                  checked={reviewEnabled}
                  onChange={(e) => setReviewEnabled(e.target.checked)}
                  className="h-4 w-4"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">审核严格度</label>
                <select
                  className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  value={reviewStrictness}
                  onChange={(e) => setReviewStrictness(e.target.value as ReviewStrictnessValue)}
                  disabled={!reviewEnabled}
                >
                  {REVIEW_STRICTNESS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <div id="agents-panel" role="tabpanel" className="flex-1">
            {/* 全局默认 Prompts */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">全局默认 Prompts</h3>
                <span className="text-sm text-muted-foreground">所有项目默认使用</span>
              </div>

              {loadingPrompts ? (
                <div>加载中...</div>
              ) : (
                <div className="max-w-3xl">
                  {globalPrompts.map((prompt) => (
                    <AgentPromptEditor
                      key={prompt.agent_type}
                      prompt={prompt}
                      onSave={(content) => handleSaveGlobalPrompt(prompt.agent_type, content)}
                      onReset={() => handleResetGlobalPrompt(prompt.agent_type)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* 项目自定义 Prompts */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">项目自定义 Prompts</h3>
                <span className="text-sm text-muted-foreground">覆盖特定项目的智能体配置</span>
              </div>

              <div className="max-w-3xl bg-white rounded-lg border">
                {projects.map((project) => (
                  <div
                    key={project.id}
                    className="p-4 border-b last:border-b-0 flex items-center justify-between hover:bg-gray-50"
                  >
                    <div>
                      <h4 className="font-medium">{project.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {project.stage}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setSelectedProjectId(
                          selectedProjectId === project.id ? null : project.id
                        )
                      }
                    >
                      {selectedProjectId === project.id ? '关闭' : '管理'}
                    </Button>
                  </div>
                ))}

                {projects.length === 0 && (
                  <div className="p-4 text-center text-muted-foreground">
                    暂无项目
                  </div>
                )}
              </div>

              {/* 项目配置展开 */}
              {selectedProjectId && (
                <div className="mt-4 max-w-3xl">
                  <ProjectPromptConfig
                    projectId={selectedProjectId}
                    projectName={projects.find((p) => p.id === selectedProjectId)?.name || ''}
                    onClose={() => setSelectedProjectId(null)}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Save button section - only for model and review tabs */}
        {(activeTab === 'model' || activeTab === 'review') && (
          <div className="max-w-xl mt-6 pt-4 border-t">
            <div className="flex items-center gap-4">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? '保存中...' : '保存设置'}
              </Button>
              {saved && <span className="text-sm text-green-600">已保存</span>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 重新构建前端**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 前端构建成功，服务启动

- [ ] **Step 3: 提交 Settings 页面更新**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: add agent management tab to Settings page"
```

---

## Task 12: 集成测试和验证

**Files:**
- 无新增文件

- [ ] **Step 1: 运行后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试通过

- [ ] **Step 2: 手动测试全局 Prompts**

在浏览器中：
1. 打开 Settings 页面
2. 切换到"智能体管理"标签
3. 验证 7 个智能体显示正常
4. 点击"编辑"修改一个 Prompt
5. 点击"保存"
6. 验证"已修改"标签显示
7. 点击"重置默认"
8. 验证恢复成功

- [ ] **Step 3: 手动测试项目自定义**

在浏览器中：
1. 在"项目自定义 Prompts"区域
2. 点击一个项目的"管理"
3. 验证智能体列表显示
4. 点击"为此项目自定义"
5. 输入自定义内容
6. 保存并验证
7. 点击"恢复全局"验证删除成功

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: complete agent prompt management feature (v0.3.0)"
```

---

## 验收清单

- [ ] 数据库迁移成功执行
- [ ] 全局 Prompts API 正常工作
- [ ] 项目自定义 Prompts API 正常工作
- [ ] 前端 Settings 页面显示智能体管理标签
- [ ] Prompt 编辑器可正常编辑保存
- [ ] 变量提示正确显示
- [ ] 重置默认功能正常
- [ ] 项目自定义覆盖功能正常
- [ ] 后端测试全部通过
- [ ] 现有功能不受影响