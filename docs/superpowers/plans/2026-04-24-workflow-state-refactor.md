# v0.6.3 工作流状态架构重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作流状态从 Project 表分离到独立的 WorkflowState 表，统一 stage 命名，清理技术债。

**Architecture:** 新建 WorkflowState 表存储工作流状态，修改 Project 表删除冗余字段，前端统一使用新的 stage 命名，删除 legacy 代码。

**Tech Stack:** SQLAlchemy, Alembic, FastAPI, React, TypeScript, Zustand

---

## 文件结构

**新建文件：**
- `backend/app/models/workflow_state.py` - WorkflowState 模型
- `backend/alembic/versions/20260424_add_workflow_state_table.py` - 数据库迁移
- `backend/alembic/versions/20260424_remove_project_workflow_fields.py` - 删除旧字段迁移
- `backend/tests/test_workflow_state_model.py` - 模型测试

**修改文件：**
- `backend/app/models/project.py` - 删除工作流字段，添加关系
- `backend/app/models/__init__.py` - 导出新模型
- `backend/app/api/workflow.py` - 使用 WorkflowState
- `backend/app/api/projects.py` - 返回 workflow_state
- `backend/app/schemas/project.py` - 更新响应模式
- `backend/app/agents/nodes/chapter_generation.py` - 删除 legacy 代码
- `frontend/src/types/index.ts` - 更新类型定义
- `frontend/src/pages/ProjectDetail.tsx` - stage 命名替换
- `frontend/src/pages/Writing.tsx` - stage 命名替换
- `frontend/src/pages/Reading.tsx` - stage 命名替换
- `frontend/src/components/common/ProjectCard.tsx` - stage 命名替换
- `frontend/src/components/project/StepNavigation.tsx` - stage 命名替换
- `frontend/src/components/project/OutlineWorkflow.tsx` - stage 命名替换
- `frontend/src/lib/api.ts` - 更新 API 类型

---

## Task 1: 创建 WorkflowState 模型

**Files:**
- Create: `backend/app/models/workflow_state.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/project.py`
- Test: `backend/tests/test_workflow_state_model.py`

- [ ] **Step 1: 写测试 - WorkflowState 模型基本功能**

```python
# backend/tests/test_workflow_state_model.py
"""Tests for WorkflowState model"""

import pytest
from datetime import datetime
from app.models.workflow_state import WorkflowState
from app.models.project import Project
from app.models.user import User


def test_workflow_state_defaults():
    """Test WorkflowState default values"""
    state = WorkflowState(project_id=1)
    assert state.thread_id == "main"
    assert state.stage == "inspiration"
    assert state.workflow_mode == "hybrid"
    assert state.max_rewrite_count == 3
    assert state.current_chapter == 1
    assert state.waiting_for_confirmation == False
    assert state.confirmation_type == None


def test_workflow_state_stage_values():
    """Test valid stage values"""
    valid_stages = [
        "inspiration", "outline", "chapter_outlines",
        "writing", "review", "complete"
    ]
    for stage in valid_stages:
        state = WorkflowState(project_id=1, stage=stage)
        assert state.stage == stage


def test_workflow_state_workflow_mode_values():
    """Test valid workflow_mode values"""
    valid_modes = ["step_by_step", "hybrid", "auto"]
    for mode in valid_modes:
        state = WorkflowState(project_id=1, workflow_mode=mode)
        assert state.workflow_mode == mode
```

- [ ] **Step 2: 运行测试验证失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow_state_model.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.models.workflow_state'"

- [ ] **Step 3: 实现 WorkflowState 模型**

```python
# backend/app/models/workflow_state.py
"""WorkflowState model for storing workflow state"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class WorkflowState(Base):
    """工作流状态模型
    
    存储项目的工作流状态，支持多工作流实例。
    与 Project 是 N:1 关系，通过 thread_id 区分不同工作流。
    """
    
    __tablename__ = "workflow_states"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(50), nullable=False, default="main")
    
    # 工作流阶段（统一命名）
    stage = Column(String(30), nullable=False, default="inspiration")
    
    # 工作流模式
    workflow_mode = Column(String(20), nullable=False, default="hybrid")
    max_rewrite_count = Column(Integer, nullable=False, default=3)
    
    # 进度追踪
    current_chapter = Column(Integer, nullable=False, default=1)
    
    # 确认状态
    waiting_for_confirmation = Column(Boolean, nullable=False, default=False)
    confirmation_type = Column(String(30), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    project = relationship("Project", back_populates="workflow_states")
    
    def __repr__(self):
        return f"<WorkflowState project_id={self.project_id} stage={self.stage}>"
```

- [ ] **Step 4: 更新 models/__init__.py 导出**

```python
# backend/app/models/__init__.py
"""Models package"""

from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.models.checkpoint import WorkflowCheckpoint
from app.models.settings import UserSettings
from app.models.agent_prompt import AgentPrompt, ProjectAgentPrompt
from app.models.model_config import ModelConfig
from app.models.workflow_state import WorkflowState  # 新增

__all__ = [
    "User",
    "Project",
    "Outline",
    "ChapterOutline",
    "Chapter",
    "WorkflowCheckpoint",
    "UserSettings",
    "AgentPrompt",
    "ProjectAgentPrompt",
    "ModelConfig",
    "WorkflowState",  # 新增
]
```

- [ ] **Step 5: 更新 Project 模型添加关系**

```python
# backend/app/models/project.py
"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """Project model - 项目元数据"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    stage = Column(String(50), default="inspiration_collecting")  # 保留，迁移后删除
    target_words = Column(Integer, default=100000)
    total_words = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 审核设置（保留，迁移后删除）
    review_mode = Column(String(20), default="off", nullable=False)
    max_rewrite_count = Column(Integer, default=3, nullable=False)

    # 工作流模式设置（保留，迁移后删除）
    workflow_mode = Column(String(20), default="hybrid", nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")
    outline = relationship("Outline", back_populates="project", uselist=False, cascade="all, delete-orphan")
    chapter_outlines = relationship("ChapterOutline", back_populates="project", cascade="all, delete-orphan")
    agent_prompts = relationship("ProjectAgentPrompt", back_populates="project", cascade="all, delete-orphan")
    workflow_states = relationship("WorkflowState", back_populates="project", cascade="all, delete-orphan")  # 新增

    def __repr__(self):
        return f"<Project {self.name}>"
```

- [ ] **Step 6: 运行测试验证通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow_state_model.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/workflow_state.py backend/app/models/__init__.py backend/app/models/project.py backend/tests/test_workflow_state_model.py
git commit -m "feat(models): add WorkflowState model for workflow state management

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: 创建数据库迁移脚本 - 新建 workflow_states 表

**Files:**
- Create: `backend/alembic/versions/20260424_add_workflow_state_table.py`

- [ ] **Step 1: 创建迁移脚本**

```python
# backend/alembic/versions/20260424_add_workflow_state_table.py
"""add workflow_states table

Revision ID: 20260424_workflow_state
Revises: 20260423_workflow
Create Date: 2026-04-24

创建 workflow_states 表：
- 分离工作流状态与项目元数据
- 支持多工作流实例（thread_id）
- 统一 stage 命名
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260424_workflow_state'
down_revision = '20260423_workflow'
branch_labels = None
depends_on = None

# Stage 值映射
STAGE_MAPPING = {
    'inspiration_collecting': 'inspiration',
    'outline_generating': 'outline',
    'outline_confirming': 'outline',
    'chapter_outlines_generating': 'chapter_outlines',
    'chapter_outlines_confirming': 'chapter_outlines',
    'chapter_writing': 'writing',
    'chapter_reviewing': 'review',
    'completed': 'complete',
    'paused': 'writing',  # paused 默认回到 writing
}


def upgrade() -> None:
    # 创建 workflow_states 表
    op.create_table(
        'workflow_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(50), nullable=False, server_default='main'),
        sa.Column('stage', sa.String(30), nullable=False, server_default='inspiration'),
        sa.Column('workflow_mode', sa.String(20), nullable=False, server_default='hybrid'),
        sa.Column('max_rewrite_count', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('current_chapter', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('waiting_for_confirmation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confirmation_type', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_workflow_states_project', 'workflow_states', ['project_id'])
    op.create_index('idx_workflow_states_thread', 'workflow_states', ['thread_id'])

    # 创建唯一约束
    op.create_unique_constraint(
        'uq_workflow_states_project_thread',
        'workflow_states',
        ['project_id', 'thread_id']
    )

    # 迁移数据：从 projects 表迁移到 workflow_states 表
    # 使用原生 SQL 进行数据迁移
    conn = op.get_bind()
    
    # 获取所有项目的工作流相关字段
    projects = conn.execute(
        sa.text("""
            SELECT id, stage, workflow_mode, max_rewrite_count 
            FROM projects
        """)
    ).fetchall()

    # 为每个项目创建 workflow_state 记录
    for project in projects:
        project_id, old_stage, workflow_mode, max_rewrite_count = project
        
        # 转换 stage 值
        new_stage = STAGE_MAPPING.get(old_stage, 'inspiration')
        
        # 获取当前章节（从 chapter_outlines 表计算）
        current_chapter_result = conn.execute(
            sa.text("""
                SELECT COUNT(*) + 1 
                FROM chapter_outlines co
                JOIN chapters c ON c.chapter_outline_id = co.id
                WHERE co.project_id = :project_id
            """),
            {"project_id": project_id}
        ).fetchone()
        current_chapter = current_chapter_result[0] if current_chapter_result else 1

        conn.execute(
            sa.text("""
                INSERT INTO workflow_states 
                (project_id, thread_id, stage, workflow_mode, max_rewrite_count, current_chapter, 
                 waiting_for_confirmation, created_at, updated_at)
                VALUES (:project_id, 'main', :stage, :workflow_mode, :max_rewrite_count, :current_chapter,
                        false, NOW(), NOW())
            """),
            {
                "project_id": project_id,
                "stage": new_stage,
                "workflow_mode": workflow_mode or 'hybrid',
                "max_rewrite_count": max_rewrite_count or 3,
                "current_chapter": current_chapter
            }
        )


def downgrade() -> None:
    # 删除唯一约束
    op.drop_constraint('uq_workflow_states_project_thread', 'workflow_states')
    
    # 删除索引
    op.drop_index('idx_workflow_states_thread', table_name='workflow_states')
    op.drop_index('idx_workflow_states_project', table_name='workflow_states')
    
    # 删除表
    op.drop_table('workflow_states')
```

- [ ] **Step 2: 提交**

```bash
git add backend/alembic/versions/20260424_add_workflow_state_table.py
git commit -m "feat(db): add migration for workflow_states table with data migration

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: 更新 API - projects.py 使用 WorkflowState

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/app/schemas/project.py`

- [ ] **Step 1: 更新 Project 响应 Schema**

```python
# backend/app/schemas/project.py
"""Project schemas"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class WorkflowStateBase(BaseModel):
    """WorkflowState 基础 Schema"""
    thread_id: str = "main"
    stage: str = "inspiration"
    workflow_mode: str = "hybrid"
    max_rewrite_count: int = 3
    current_chapter: int = 1
    waiting_for_confirmation: bool = False
    confirmation_type: Optional[str] = None


class WorkflowStateResponse(WorkflowStateBase):
    """WorkflowState 响应 Schema"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    """Project 基础 Schema"""
    name: str
    target_words: int = 100000


class ProjectCreate(ProjectBase):
    """Project 创建 Schema"""
    pass


class ProjectUpdate(BaseModel):
    """Project 更新 Schema"""
    name: Optional[str] = None
    target_words: Optional[int] = None


class ProjectResponse(ProjectBase):
    """Project 响应 Schema"""
    id: int
    user_id: int
    total_words: int
    created_at: datetime
    updated_at: datetime
    workflow_state: Optional[WorkflowStateResponse] = None

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Project 详情响应 Schema"""
    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0


class ProjectListResponse(BaseModel):
    """Project 列表响应 Schema"""
    projects: List[ProjectResponse]
    total: int
```

- [ ] **Step 2: 更新 projects API 使用 WorkflowState**

```python
# backend/app/api/projects.py
"""Projects API routes"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.workflow_state import WorkflowState
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.utils.auth import get_current_user
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectListResponse,
    WorkflowStateResponse,
)

router = APIRouter()


def get_or_create_workflow_state(
    db: Session, 
    project_id: int, 
    thread_id: str = "main"
) -> WorkflowState:
    """获取或创建工作流状态"""
    state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == thread_id
    ).first()
    
    if not state:
        state = WorkflowState(project_id=project_id, thread_id=thread_id)
        db.add(state)
        db.commit()
        db.refresh(state)
    
    return state


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户的所有项目"""
    projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.updated_at.desc()).all()

    # 为每个项目附加 workflow_state
    project_responses = []
    for p in projects:
        ws = get_or_create_workflow_state(db, p.id)
        project_responses.append(ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            target_words=p.target_words,
            total_words=p.total_words,
            created_at=p.created_at,
            updated_at=p.updated_at,
            workflow_state=WorkflowStateResponse.model_validate(ws) if ws else None
        ))

    return ProjectListResponse(projects=project_responses, total=len(project_responses))


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目详情"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # 获取工作流状态
    ws = get_or_create_workflow_state(db, project_id)

    # 获取章节统计
    chapter_count = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id
    ).scalar() or 0

    completed_chapters = db.query(func.count(ChapterOutline.id)).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).scalar() or 0

    progress_percentage = (completed_chapters / chapter_count * 100) if chapter_count > 0 else 0.0

    return ProjectDetailResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(ws) if ws else None,
        chapter_count=chapter_count,
        completed_chapters=completed_chapters,
        progress_percentage=round(progress_percentage, 1)
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新项目"""
    project = Project(
        user_id=current_user.id,
        name=data.name,
        target_words=data.target_words
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # 创建默认工作流状态
    ws = WorkflowState(project_id=project.id)
    db.add(ws)
    db.commit()
    db.refresh(ws)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(ws)
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新项目"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if data.name is not None:
        project.name = data.name
    if data.target_words is not None:
        project.target_words = data.target_words

    db.commit()
    db.refresh(project)

    ws = get_or_create_workflow_state(db, project_id)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(ws) if ws else None
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除项目"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    db.delete(project)
    db.commit()
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/projects.py backend/app/schemas/project.py
git commit -m "feat(api): update projects API to use WorkflowState model

- Add WorkflowState schema
- Update ProjectResponse to include workflow_state
- Add get_or_create_workflow_state helper

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: 更新 workflow API 使用 WorkflowState

**Files:**
- Modify: `backend/app/api/workflow.py`

- [ ] **Step 1: 更新 workflow.py**

修改 `build_initial_state` 函数使用 WorkflowState，删除 stage 映射代码：

```python
# backend/app/api/workflow.py
# 修改 build_initial_state 函数

def build_initial_state(
    project: Project,
    outline: Outline,
    workflow_state: WorkflowState,  # 新增参数
    llm_config_id: Optional[int] = None
) -> NovelState:
    """
    从项目、大纲和工作流状态构建初始 NovelState。

    Args:
        project: 项目实例
        outline: 大纲实例
        workflow_state: 工作流状态实例
        llm_config_id: 模型配置 ID

    Returns:
        NovelState 字典
    """
    # 获取章节大纲
    chapter_outlines = [
        {
            "chapter_number": co.chapter_number,
            "title": co.title,
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot,
            "conflict": co.conflict,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
    ]

    # 获取已写入的章节
    written_chapters = []
    for co in project.chapter_outlines:
        if co.chapter and co.chapter.content:
            written_chapters.append({
                "chapter_number": co.chapter_number,
                "content": co.chapter.content,
                "word_count": co.chapter.word_count,
            })

    # 从 WorkflowState 获取阶段（无需映射）
    stage = workflow_state.stage

    # 构建状态
    state: NovelState = {
        # 基本信息
        "project_id": project.id,

        # 阶段控制
        "stage": stage,

        # 灵感/输入
        "collected_info": outline.collected_info or {},
        "inspiration_template": outline.inspiration_template,

        # 大纲
        "outline_title": outline.title,
        "outline_summary": outline.summary,
        "outline_plot_points": outline.plot_points or [],
        "outline_characters": outline.characters or [],
        "outline_world_setting": outline.world_setting,
        "outline_emotional_curve": outline.emotional_curve,
        "outline_confirmed": outline.confirmed,

        # 章节大纲
        "chapter_count": outline.chapter_count_suggested or 0,
        "chapter_outlines": chapter_outlines,
        "chapter_outlines_confirmed": all(co.confirmed for co in project.chapter_outlines) if chapter_outlines else False,

        # 章节正文
        "written_chapters": written_chapters,
        "current_chapter": workflow_state.current_chapter,

        # 审核/重写
        "review_mode": workflow_state.workflow_mode,  # 使用 workflow_mode
        "review_result": None,
        "rewrite_count": 0,
        "max_rewrite_count": workflow_state.max_rewrite_count,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
        "confirmation_type": workflow_state.confirmation_type,

        # LLM 服务
        "llm_config_id": llm_config_id,
    }

    return state
```

同时更新 `run_workflow` 端点获取 WorkflowState：

```python
# backend/app/api/workflow.py
# 在 run_workflow 端点中添加获取 WorkflowState

@router.post("/{project_id}/workflow/run")
async def run_workflow(
    project_id: int,
    request: WorkflowRunRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启动或恢复工作流（SSE 流式）"""
    # 验证项目所有权
    project = get_project_with_ownership(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    # 获取或创建 WorkflowState
    from app.models.workflow_state import WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()
    
    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()

    # 获取 LLM 配置 ID
    llm_config_id = None
    if request:
        llm_config_id = request.llm_config_id

    # 构建初始状态
    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id)

    # ... 后续代码不变
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/workflow.py
git commit -m "refactor(workflow): use WorkflowState instead of Project fields

- Remove stage mapping code
- Use workflow_state.stage directly
- Use workflow_state.workflow_mode for review_mode

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: 删除 Legacy 代码

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py`

- [ ] **Step 1: 删除 legacy 函数**

删除以下函数：
- `parse_chapter_outlines()` (行 123-195)
- `generate_chapter_outlines_node()` (行 268-289) - legacy 同步版本

- [ ] **Step 2: 删除过时 TODO 注释**

删除行 331 的 TODO 注释：
```python
previous_ending="",  # TODO: 从上一章获取
```

改为：
```python
previous_ending=previous_ending,  # 从 written_chapters 获取
```

并确保 `generate_chapter_content_stream` 函数正确使用 `previous_ending` 参数。

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "chore: remove legacy code and outdated TODO

- Remove parse_chapter_outlines() legacy function
- Remove generate_chapter_outlines_node() legacy version
- Fix outdated TODO comment for previous_ending

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: 更新前端类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 更新 Project 和 WorkflowState 类型**

```typescript
// frontend/src/types/index.ts

// ==================== Project Types ====================

/**
 * 工作流状态（后端 WorkflowState 模型）
 */
export interface WorkflowStateData {
  id: number
  project_id: number
  thread_id: string
  stage: WorkflowStage
  workflow_mode: WorkflowMode
  max_rewrite_count: number
  current_chapter: number
  waiting_for_confirmation: boolean
  confirmation_type: ConfirmationType | null
  created_at: string
  updated_at: string
}

export interface Project {
  id: number
  user_id: number
  name: string
  target_words: number
  total_words: number
  created_at: string
  updated_at: string
  workflow_state: WorkflowStateData | null
}

export interface ProjectDetail extends Project {
  chapter_count: number
  completed_chapters: number
  progress_percentage: number
}

export interface ProjectListResponse {
  projects: Project[]
  total: number
}

export interface ProjectCreate {
  name: string
  target_words?: number
}

export interface ProjectUpdate {
  name?: string
  target_words?: number
}

// 删除旧的 stage 相关类型，使用 WorkflowStage
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): update Project and WorkflowState types

- Add WorkflowStateData interface
- Update Project to include workflow_state
- Remove stage field from Project

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: 更新前端页面 - ProjectDetail.tsx

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 更新 STAGE_LABELS 使用新命名**

```typescript
// frontend/src/pages/ProjectDetail.tsx
// 替换 STAGE_LABELS

const STAGE_LABELS: Record<string, string> = {
  inspiration: '灵感采集',
  outline: '大纲生成',
  chapter_outlines: '章节大纲',
  writing: '写作中',
  review: '审核中',
  complete: '已完成',
}
```

- [ ] **Step 2: 更新 stage 比较逻辑**

将所有 `project.stage` 替换为 `project.workflow_state?.stage`，并使用新命名：

```typescript
// 旧代码
project.stage === 'inspiration_collecting'
project.stage === 'outline_generating'
project.stage === 'chapter_writing'
project.stage !== 'chapter_writing'

// 新代码
const stage = project.workflow_state?.stage
stage === 'inspiration'
stage === 'outline'
stage === 'writing'
stage !== 'writing'
```

- [ ] **Step 3: 更新 showInspirationCollection 和相关逻辑**

```typescript
// 更新 stage 相关条件
const stage = project?.workflow_state?.stage

const showInspirationCollection = stage === 'inspiration'

const showOutlineStage = ['outline', 'chapter_outlines'].includes(stage || '')

const showWritingStage = ['writing', 'review'].includes(stage || '')

const showCompleteStage = stage === 'complete'
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "refactor(frontend): update ProjectDetail to use new stage names

- Update STAGE_LABELS with new naming
- Replace project.stage with workflow_state.stage
- Update stage comparison logic

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: 更新前端其他文件

**Files:**
- Modify: `frontend/src/pages/Writing.tsx`
- Modify: `frontend/src/pages/Reading.tsx`
- Modify: `frontend/src/components/common/ProjectCard.tsx`
- Modify: `frontend/src/components/project/StepNavigation.tsx`
- Modify: `frontend/src/components/project/OutlineWorkflow.tsx`

- [ ] **Step 1: 更新 Writing.tsx**

```typescript
// 替换 stage 命名
// 'chapter_writing' → 'writing'
// project.stage → project.workflow_state?.stage

const stage = projectData?.workflow_state?.stage

if (stage !== 'writing' && stage !== 'review') {
  // 更新 stage 的逻辑需要通过 WorkflowState API
  // 暂时保留或创建更新 WorkflowState 的 API
}
```

- [ ] **Step 2: 更新 Reading.tsx**

```typescript
// 替换 stage 命名
// 'chapter_writing' → 'writing'

if (projectData.workflow_state?.stage === 'writing') {
  // ...
}
```

- [ ] **Step 3: 更新 ProjectCard.tsx**

```typescript
// 更新 STAGE_CONFIG
const STAGE_CONFIG: Record<string, StageConfig> = {
  inspiration: { label: '灵感采集', color: 'bg-gray-500', icon: Lightbulb, isProcessing: false, isCompleted: false },
  outline: { label: '大纲生成', color: 'bg-blue-500', icon: Loader2, isProcessing: true, isCompleted: false },
  chapter_outlines: { label: '章节大纲', color: 'bg-purple-500', icon: List, isProcessing: true, isCompleted: false },
  writing: { label: '写作中', color: 'bg-green-500', icon: PenLine, isProcessing: false, isCompleted: false },
  review: { label: '审核中', color: 'bg-yellow-500', icon: CheckCircle, isProcessing: true, isCompleted: false },
  complete: { label: '已完成', color: 'bg-emerald-500', icon: CheckCircle, isProcessing: false, isCompleted: true },
}

// 使用 workflow_state.stage
const stage = project.workflow_state?.stage || 'inspiration'
const config = STAGE_CONFIG[stage] || STAGE_CONFIG.inspiration
```

- [ ] **Step 4: 更新 StepNavigation.tsx**

```typescript
// 更新 STEPS 配置
export const STEPS: StepConfig[] = [
  { index: 0, name: '灵感采集', stages: ['inspiration'] },
  { index: 1, name: '大纲生成', stages: ['outline'] },
  { index: 2, name: '章节大纲', stages: ['chapter_outlines'] },
  { index: 3, name: '写作', stages: ['writing', 'review'] },
  { index: 4, name: '完成', stages: ['complete'] },
]

// 更新 isStepActive 和 isStepCompleted 逻辑
const stage = project?.workflow_state?.stage
```

- [ ] **Step 5: 更新 OutlineWorkflow.tsx**

```typescript
// 替换所有 stage 比较使用新命名
// 'outline_generating' → 'outline'
// 'chapter_writing' → 'writing'

const stage = project?.workflow_state?.stage

// 更新条件判断
if (stage === 'outline') {
  // ...
}
```

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/Writing.tsx frontend/src/pages/Reading.tsx frontend/src/components/common/ProjectCard.tsx frontend/src/components/project/StepNavigation.tsx frontend/src/components/project/OutlineWorkflow.tsx
git commit -m "refactor(frontend): update all components to use new stage names

- Replace old stage names with new unified names
- Use workflow_state.stage instead of project.stage
- Update STAGE_CONFIG in ProjectCard
- Update STEPS in StepNavigation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: 创建删除旧字段的迁移脚本

**Files:**
- Create: `backend/alembic/versions/20260424_remove_project_workflow_fields.py`

- [ ] **Step 1: 创建迁移脚本**

```python
# backend/alembic/versions/20260424_remove_project_workflow_fields.py
"""remove workflow fields from projects table

Revision ID: 20260424_remove_workflow
Revises: 20260424_workflow_state
Create Date: 2026-04-24

从 projects 表删除已迁移到 workflow_states 的字段：
- stage
- review_mode
- workflow_mode
- max_rewrite_count
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260424_remove_workflow'
down_revision = '20260424_workflow_state'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 删除旧字段
    op.drop_column('projects', 'stage')
    op.drop_column('projects', 'review_mode')
    op.drop_column('projects', 'workflow_mode')
    op.drop_column('projects', 'max_rewrite_count')


def downgrade() -> None:
    # 恢复旧字段
    op.add_column('projects', sa.Column('stage', sa.String(50), server_default='inspiration_collecting'))
    op.add_column('projects', sa.Column('review_mode', sa.String(20), server_default='off'))
    op.add_column('projects', sa.Column('workflow_mode', sa.String(20), server_default='hybrid'))
    op.add_column('projects', sa.Column('max_rewrite_count', sa.Integer, server_default='3'))
```

- [ ] **Step 2: 更新 Project 模型删除旧字段**

```python
# backend/app/models/project.py
"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """Project model - 项目元数据"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    target_words = Column(Integer, default=100000)
    total_words = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="projects")
    outline = relationship("Outline", back_populates="project", uselist=False, cascade="all, delete-orphan")
    chapter_outlines = relationship("ChapterOutline", back_populates="project", cascade="all, delete-orphan")
    agent_prompts = relationship("ProjectAgentPrompt", back_populates="project", cascade="all, delete-orphan")
    workflow_states = relationship("WorkflowState", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"
```

- [ ] **Step 3: 提交**

```bash
git add backend/alembic/versions/20260424_remove_project_workflow_fields.py backend/app/models/project.py
git commit -m "feat(db): remove workflow fields from projects table

- Remove stage, review_mode, workflow_mode, max_rewrite_count
- These fields are now in workflow_states table

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: 运行测试验证

**Files:**
- Test: `backend/tests/`

- [ ] **Step 1: 运行后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: All tests pass

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: All tests pass

- [ ] **Step 3: 手动测试工作流**

1. 启动服务：`docker compose up -d`
2. 创建新项目
3. 运行完整工作流
4. 验证暂停/恢复功能

- [ ] **Step 4: 提交最终版本**

```bash
git tag -a v0.6.3 -m "v0.6.3: Workflow state architecture refactor

- New WorkflowState table for workflow state management
- Unified stage naming (inspiration, outline, chapter_outlines, writing, review, complete)
- Removed review_mode, workflow_mode from Project
- Deleted legacy code and outdated TODOs
- Support for multi-workflow instances (thread_id)"
```

---

## 成功标准

- [ ] 所有后端测试通过
- [ ] 所有前端测试通过
- [ ] 工作流功能正常运行
- [ ] 无 stage 映射转换代码
- [ ] 无 review_mode 字段
- [ ] 无 legacy 代码和过时 TODO
- [ ] v0.6.3 标签创建
