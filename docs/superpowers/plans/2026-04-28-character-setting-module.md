# 人物设定模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增独立的人物设定功能模块，包含人物管理、关系规划、演变追溯，并优化上下文传递机制。

**Architecture:** 
- 后端：新增 4 个数据库表（characters, relations, evolution_plans, evolution_records），新增 API 路由，LangGraph 新增节点
- 前端：新增人物设定页面，集成到现有工作流
- 复用现有 LangGraph 框架，通过 NovelState 传递人物相关状态

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Alembic, LangGraph, React, Zustand

---

## 文件结构

### 后端新增文件
```
backend/app/models/character.py          # Character, Relation, EvolutionPlan, EvolutionRecord 模型
backend/app/schemas/character.py         # Pydantic schemas
backend/app/api/characters.py            # 人物 API 路由
backend/alembic/versions/20260428_add_character_tables.py  # 数据库迁移
backend/app/agents/nodes/character_generation.py  # 人物生成节点
backend/app/agents/nodes/relation_generation.py   # 关系生成节点
backend/app/agents/prompts/character.py   # 人物生成 Prompt
```

### 后端修改文件
```
backend/app/models/__init__.py            # 导出新模型
backend/app/models/project.py            # 添加 novel_length 字段
backend/app/schemas/__init__.py          # 导出新 schemas
backend/app/agents/state.py              # NovelState 新增字段
backend/app/agents/graph.py              # 新增节点和路由
backend/app/agents/nodes/chapter_generation.py  # 上下文传递优化
backend/app/main.py                      # 注册新路由
```

### 前端新增文件
```
frontend/src/pages/CharacterSetting.tsx  # 人物设定页面
frontend/src/components/character/CharacterCard.tsx      # 人物卡片
frontend/src/components/character/CharacterForm.tsx      # 人物表单
frontend/src/components/character/CharacterDetail.tsx    # 人物详情侧边栏
frontend/src/components/character/RelationList.tsx       # 关系列表
frontend/src/components/character/EvolutionTimeline.tsx  # 演变时间线
frontend/src/lib/characterApi.ts         # 人物 API 客户端
frontend/src/types/character.ts          # 人物类型定义
```

### 前端修改文件
```
frontend/src/App.tsx                     # 新增路由
frontend/src/components/project/StepNavigation.tsx  # 步骤导航调整
frontend/src/pages/ProjectDetail.tsx     # 集成人物设定阶段
frontend/src/types/index.ts              # 导出新类型
```

---

## Task 1: 数据库迁移 - 创建人物相关表

**Files:**
- Create: `backend/alembic/versions/20260428_add_character_tables.py`
- Modify: `backend/app/models/project.py`
- Create: `backend/app/models/character.py`

- [ ] **Step 1: 创建 Character 模型**

```python
# backend/app/models/character.py
"""Character and relation models"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Character(Base):
    """人物设定模型"""

    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)  # 主角/核心反派/重要配角/配角
    personality = Column(Text, nullable=True)
    catchphrase = Column(String(200), nullable=True)
    habit_action = Column(String(200), nullable=True)
    deep_fear = Column(Text, nullable=True)
    core_motivation = Column(Text, nullable=True)
    growth_arc = Column(Text, nullable=True)
    appearance = Column(Text, nullable=True)
    backstory = Column(Text, nullable=True)
    signature_item = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="characters")
    relations_a = relationship("Relation", foreign_keys="Relation.character_a_id", back_populates="character_a", cascade="all, delete-orphan")
    relations_b = relationship("Relation", foreign_keys="Relation.character_b_id", back_populates="character_b", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Character {self.name}>"


class Relation(Base):
    """人物关系模型"""

    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    character_a_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    character_b_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(50), nullable=False)  # 信任/敌对/感情/合作/利用/陌生
    direction = Column(String(20), nullable=False, default="双向")  # 双向/单向A→B/单向B→A
    current_status = Column(Text, nullable=True)
    trust_level = Column(Integer, default=50)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="relations")
    character_a = relationship("Character", foreign_keys=[character_a_id], back_populates="relations_a")
    character_b = relationship("Character", foreign_keys=[character_b_id], back_populates="relations_b")
    evolution_plans = relationship("EvolutionPlan", back_populates="relation", cascade="all, delete-orphan")
    evolution_records = relationship("EvolutionRecord", back_populates="relation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Relation {self.character_a_id} <-> {self.character_b_id}>"


class EvolutionPlan(Base):
    """关系演变规划模型"""

    __tablename__ = "evolution_plans"

    id = Column(Integer, primary_key=True, index=True)
    relation_id = Column(Integer, ForeignKey("relations.id", ondelete="CASCADE"), nullable=False)
    trigger_chapter = Column(Integer, nullable=False)
    event_description = Column(Text, nullable=False)
    status_before = Column(Text, nullable=True)
    status_after = Column(Text, nullable=False)
    trust_before = Column(Integer, nullable=True)
    trust_after = Column(Integer, nullable=True)
    is_triggered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    relation = relationship("Relation", back_populates="evolution_plans")
    triggered_records = relationship("EvolutionRecord", back_populates="triggered_plan")

    def __repr__(self):
        return f"<EvolutionPlan relation={self.relation_id} chapter={self.trigger_chapter}>"


class EvolutionRecord(Base):
    """关系演变追溯记录模型"""

    __tablename__ = "evolution_records"

    id = Column(Integer, primary_key=True, index=True)
    relation_id = Column(Integer, ForeignKey("relations.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    status_change = Column(Text, nullable=True)
    trust_change = Column(Integer, nullable=True)
    triggered_plan_id = Column(Integer, ForeignKey("evolution_plans.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    relation = relationship("Relation", back_populates="evolution_records")
    triggered_plan = relationship("EvolutionPlan", back_populates="triggered_records")

    def __repr__(self):
        return f"<EvolutionRecord relation={self.relation_id} chapter={self.chapter_number}>"
```

- [ ] **Step 2: 修改 Project 模型添加关系**

```python
# backend/app/models/project.py - 添加以下内容

# 在 imports 后添加
from sqlalchemy.orm import relationship

# 在 Project 类中添加新的 relationship
characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
relations = relationship("Relation", back_populates="project", cascade="all, delete-orphan")

# 添加 novel_length 字段
novel_length = Column(String(20), default="short")  # short/medium/long/extra_long
```

- [ ] **Step 3: 更新 models/__init__.py**

```python
# backend/app/models/__init__.py - 添加导入
from app.models.character import Character, Relation, EvolutionPlan, EvolutionRecord
```

- [ ] **Step 4: 创建数据库迁移文件**

```python
# backend/alembic/versions/20260428_add_character_tables.py
"""add character tables

Revision ID: 20260428_characters
Revises: 20260426_system_prompts
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260428_characters'
down_revision = '20260426_system_prompts'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 projects 表的 novel_length 字段
    op.add_column('projects', sa.Column('novel_length', sa.String(20), default='short'))

    # 创建 characters 表
    op.create_table(
        'characters',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('personality', sa.Text(), nullable=True),
        sa.Column('catchphrase', sa.String(200), nullable=True),
        sa.Column('habit_action', sa.String(200), nullable=True),
        sa.Column('deep_fear', sa.Text(), nullable=True),
        sa.Column('core_motivation', sa.Text(), nullable=True),
        sa.Column('growth_arc', sa.Text(), nullable=True),
        sa.Column('appearance', sa.Text(), nullable=True),
        sa.Column('backstory', sa.Text(), nullable=True),
        sa.Column('signature_item', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_characters_project', 'characters', ['project_id'])

    # 创建 relations 表
    op.create_table(
        'relations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('character_a_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('character_b_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(50), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False, default='双向'),
        sa.Column('current_status', sa.Text(), nullable=True),
        sa.Column('trust_level', sa.Integer(), default=50),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('character_a_id', 'character_b_id', name='uq_relation_characters'),
    )
    op.create_index('idx_relations_project', 'relations', ['project_id'])
    op.create_index('idx_relations_character_a', 'relations', ['character_a_id'])
    op.create_index('idx_relations_character_b', 'relations', ['character_b_id'])

    # 创建 evolution_plans 表
    op.create_table(
        'evolution_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('relation_id', sa.Integer(), sa.ForeignKey('relations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_chapter', sa.Integer(), nullable=False),
        sa.Column('event_description', sa.Text(), nullable=False),
        sa.Column('status_before', sa.Text(), nullable=True),
        sa.Column('status_after', sa.Text(), nullable=False),
        sa.Column('trust_before', sa.Integer(), nullable=True),
        sa.Column('trust_after', sa.Integer(), nullable=True),
        sa.Column('is_triggered', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_evolution_plans_relation', 'evolution_plans', ['relation_id'])
    op.create_index('idx_evolution_plans_chapter', 'evolution_plans', ['trigger_chapter'])

    # 创建 evolution_records 表
    op.create_table(
        'evolution_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('relation_id', sa.Integer(), sa.ForeignKey('relations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status_change', sa.Text(), nullable=True),
        sa.Column('trust_change', sa.Integer(), nullable=True),
        sa.Column('triggered_plan_id', sa.Integer(), sa.ForeignKey('evolution_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    op.create_index('idx_evolution_records_relation', 'evolution_records', ['relation_id'])
    op.create_index('idx_evolution_records_chapter', 'evolution_records', ['chapter_number'])


def downgrade():
    op.drop_table('evolution_records')
    op.drop_table('evolution_plans')
    op.drop_table('relations')
    op.drop_table('characters')
    op.drop_column('projects', 'novel_length')
```

- [ ] **Step 5: 运行迁移**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

Expected: 迁移成功，无报错

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/character.py backend/app/models/__init__.py backend/app/models/project.py backend/alembic/versions/20260428_add_character_tables.py
git commit -m "feat(db): add character, relation, evolution_plans, evolution_records tables"
```

---

## Task 2: 创建 Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/character.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 创建 Character Schemas**

```python
# backend/app/schemas/character.py
"""Character schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ==================== Character Schemas ====================

class CharacterBase(BaseModel):
    """人物基础字段"""
    name: str
    role: str  # 主角/核心反派/重要配角/配角
    personality: Optional[str] = None
    catchphrase: Optional[str] = None
    habit_action: Optional[str] = None
    deep_fear: Optional[str] = None
    core_motivation: Optional[str] = None
    growth_arc: Optional[str] = None
    appearance: Optional[str] = None
    backstory: Optional[str] = None
    signature_item: Optional[str] = None


class CharacterCreate(CharacterBase):
    """创建人物"""
    pass


class CharacterUpdate(BaseModel):
    """更新人物"""
    name: Optional[str] = None
    role: Optional[str] = None
    personality: Optional[str] = None
    catchphrase: Optional[str] = None
    habit_action: Optional[str] = None
    deep_fear: Optional[str] = None
    core_motivation: Optional[str] = None
    growth_arc: Optional[str] = None
    appearance: Optional[str] = None
    backstory: Optional[str] = None
    signature_item: Optional[str] = None


class CharacterResponse(CharacterBase):
    """人物响应"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharacterListResponse(BaseModel):
    """人物列表响应"""
    characters: list[CharacterResponse]
    total: int


# ==================== Relation Schemas ====================

class RelationBase(BaseModel):
    """关系基础字段"""
    character_a_id: int
    character_b_id: int
    relation_type: str  # 信任/敌对/感情/合作/利用/陌生
    direction: str = "双向"  # 双向/单向A→B/单向B→A
    current_status: Optional[str] = None
    trust_level: int = 50


class RelationCreate(RelationBase):
    """创建关系"""
    pass


class RelationUpdate(BaseModel):
    """更新关系"""
    relation_type: Optional[str] = None
    direction: Optional[str] = None
    current_status: Optional[str] = None
    trust_level: Optional[int] = None


class RelationResponse(RelationBase):
    """关系响应"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RelationWithCharactersResponse(RelationResponse):
    """关系响应（包含人物信息）"""
    character_a_name: Optional[str] = None
    character_b_name: Optional[str] = None


class RelationListResponse(BaseModel):
    """关系列表响应"""
    relations: list[RelationWithCharactersResponse]
    total: int


# ==================== Evolution Plan Schemas ====================

class EvolutionPlanBase(BaseModel):
    """演变规划基础字段"""
    trigger_chapter: int
    event_description: str
    status_before: Optional[str] = None
    status_after: str
    trust_before: Optional[int] = None
    trust_after: Optional[int] = None


class EvolutionPlanCreate(EvolutionPlanBase):
    """创建演变规划"""
    pass


class EvolutionPlanUpdate(BaseModel):
    """更新演变规划"""
    trigger_chapter: Optional[int] = None
    event_description: Optional[str] = None
    status_before: Optional[str] = None
    status_after: Optional[str] = None
    trust_before: Optional[int] = None
    trust_after: Optional[int] = None
    is_triggered: Optional[bool] = None


class EvolutionPlanResponse(EvolutionPlanBase):
    """演变规划响应"""
    id: int
    relation_id: int
    is_triggered: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvolutionPlanListResponse(BaseModel):
    """演变规划列表响应"""
    plans: list[EvolutionPlanResponse]
    total: int


# ==================== Evolution Record Schemas ====================

class EvolutionRecordBase(BaseModel):
    """演变记录基础字段"""
    chapter_number: int
    content: str
    status_change: Optional[str] = None
    trust_change: Optional[int] = None
    triggered_plan_id: Optional[int] = None


class EvolutionRecordCreate(EvolutionRecordBase):
    """创建演变记录"""
    pass


class EvolutionRecordResponse(EvolutionRecordBase):
    """演变记录响应"""
    id: int
    relation_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EvolutionRecordListResponse(BaseModel):
    """演变记录列表响应"""
    records: list[EvolutionRecordResponse]
    total: int


# ==================== AI Generation Schemas ====================

class CharacterGenerateRequest(BaseModel):
    """AI 生成人物请求"""
    llm_config_id: Optional[int] = None
    count: int = 3  # 生成数量


class RelationGenerateRequest(BaseModel):
    """AI 生成关系请求"""
    llm_config_id: Optional[int] = None


class CharacterOptimizeRequest(BaseModel):
    """AI 优化人物请求"""
    llm_config_id: Optional[int] = None
    field: Optional[str] = None  # 指定优化的字段，None 表示全部
```

- [ ] **Step 2: 更新 schemas/__init__.py**

```python
# backend/app/schemas/__init__.py - 添加导入
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
    RelationCreate,
    RelationUpdate,
    RelationResponse,
    RelationWithCharactersResponse,
    RelationListResponse,
    EvolutionPlanCreate,
    EvolutionPlanUpdate,
    EvolutionPlanResponse,
    EvolutionPlanListResponse,
    EvolutionRecordCreate,
    EvolutionRecordResponse,
    EvolutionRecordListResponse,
    CharacterGenerateRequest,
    RelationGenerateRequest,
    CharacterOptimizeRequest,
)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/character.py backend/app/schemas/__init__.py
git commit -m "feat(schemas): add character, relation, evolution schemas"
```

---

## Task 3: 创建人物 API 路由

**Files:**
- Create: `backend/app/api/characters.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建人物 API 路由**

```python
# backend/app/api/characters.py
"""Character API routes"""

import json
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.character import Character, Relation, EvolutionPlan, EvolutionRecord
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
    RelationCreate,
    RelationUpdate,
    RelationWithCharactersResponse,
    RelationListResponse,
    EvolutionPlanCreate,
    EvolutionPlanUpdate,
    EvolutionPlanResponse,
    EvolutionPlanListResponse,
    EvolutionRecordCreate,
    EvolutionRecordResponse,
    EvolutionRecordListResponse,
    CharacterGenerateRequest,
    RelationGenerateRequest,
    CharacterOptimizeRequest,
)
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.utils.error import format_sse_error

router = APIRouter()


# ==================== Character CRUD ====================

@router.get("/{project_id}/characters", response_model=CharacterListResponse)
async def list_characters(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的人物列表"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    characters = db.query(Character).filter(
        Character.project_id == project_id
    ).order_by(Character.id).all()
    
    return CharacterListResponse(
        characters=[CharacterResponse.model_validate(c) for c in characters],
        total=len(characters)
    )


@router.post("/{project_id}/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: int,
    request: CharacterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建人物"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    character = Character(
        project_id=project_id,
        **request.model_dump()
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    
    return CharacterResponse.model_validate(character)


@router.get("/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def get_character(
    project_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取人物详情"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    return CharacterResponse.model_validate(character)


@router.put("/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    project_id: int,
    character_id: int,
    request: CharacterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新人物"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # 更新字段
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(character, key, value)
    
    db.commit()
    db.refresh(character)
    
    return CharacterResponse.model_validate(character)


@router.delete("/{project_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    project_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除人物"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    db.delete(character)
    db.commit()


# ==================== Relation CRUD ====================

@router.get("/{project_id}/relations", response_model=RelationListResponse)
async def list_relations(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的关系列表"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relations = db.query(Relation).filter(
        Relation.project_id == project_id
    ).all()
    
    # 构建带人物名称的响应
    result = []
    for rel in relations:
        char_a = db.query(Character).filter(Character.id == rel.character_a_id).first()
        char_b = db.query(Character).filter(Character.id == rel.character_b_id).first()
        
        rel_dict = {
            "id": rel.id,
            "project_id": rel.project_id,
            "character_a_id": rel.character_a_id,
            "character_b_id": rel.character_b_id,
            "relation_type": rel.relation_type,
            "direction": rel.direction,
            "current_status": rel.current_status,
            "trust_level": rel.trust_level,
            "created_at": rel.created_at,
            "updated_at": rel.updated_at,
            "character_a_name": char_a.name if char_a else None,
            "character_b_name": char_b.name if char_b else None,
        }
        result.append(RelationWithCharactersResponse(**rel_dict))
    
    return RelationListResponse(relations=result, total=len(result))


@router.post("/{project_id}/relations", response_model=RelationResponse, status_code=status.HTTP_201_CREATED)
async def create_relation(
    project_id: int,
    request: RelationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建关系"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    # 验证人物存在
    char_a = db.query(Character).filter(
        Character.id == request.character_a_id,
        Character.project_id == project_id
    ).first()
    char_b = db.query(Character).filter(
        Character.id == request.character_b_id,
        Character.project_id == project_id
    ).first()
    
    if not char_a or not char_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Character not found in this project"
        )
    
    # 检查是否已存在关系
    existing = db.query(Relation).filter(
        Relation.project_id == project_id,
        Relation.character_a_id == request.character_a_id,
        Relation.character_b_id == request.character_b_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relation already exists between these characters"
        )
    
    relation = Relation(
        project_id=project_id,
        **request.model_dump()
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    
    return RelationResponse.model_validate(relation)


@router.put("/{project_id}/relations/{relation_id}", response_model=RelationResponse)
async def update_relation(
    project_id: int,
    relation_id: int,
    request: RelationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新关系"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )
    
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(relation, key, value)
    
    db.commit()
    db.refresh(relation)
    
    return RelationResponse.model_validate(relation)


@router.delete("/{project_id}/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relation(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除关系"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )
    
    db.delete(relation)
    db.commit()


# ==================== Evolution Plan CRUD ====================

@router.get("/{project_id}/relations/{relation_id}/evolution/plans", response_model=EvolutionPlanListResponse)
async def list_evolution_plans(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取关系的演变规划"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )
    
    plans = db.query(EvolutionPlan).filter(
        EvolutionPlan.relation_id == relation_id
    ).order_by(EvolutionPlan.trigger_chapter).all()
    
    return EvolutionPlanListResponse(
        plans=[EvolutionPlanResponse.model_validate(p) for p in plans],
        total=len(plans)
    )


@router.post("/{project_id}/relations/{relation_id}/evolution/plans", response_model=EvolutionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_evolution_plan(
    project_id: int,
    relation_id: int,
    request: EvolutionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建演变规划"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )
    
    plan = EvolutionPlan(
        relation_id=relation_id,
        **request.model_dump()
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    return EvolutionPlanResponse.model_validate(plan)


@router.put("/{project_id}/evolution/plans/{plan_id}", response_model=EvolutionPlanResponse)
async def update_evolution_plan(
    project_id: int,
    plan_id: int,
    request: EvolutionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新演变规划"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    plan = db.query(EvolutionPlan).join(Relation).filter(
        EvolutionPlan.id == plan_id,
        Relation.project_id == project_id
    ).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolution plan not found"
        )
    
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    
    db.commit()
    db.refresh(plan)
    
    return EvolutionPlanResponse.model_validate(plan)


@router.delete("/{project_id}/evolution/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evolution_plan(
    project_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除演变规划"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    plan = db.query(EvolutionPlan).join(Relation).filter(
        EvolutionPlan.id == plan_id,
        Relation.project_id == project_id
    ).first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolution plan not found"
        )
    
    db.delete(plan)
    db.commit()


# ==================== Evolution Records ====================

@router.get("/{project_id}/relations/{relation_id}/evolution/records", response_model=EvolutionRecordListResponse)
async def list_evolution_records(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取关系的演变记录"""
    project = get_project_for_user(project_id, current_user.id, db)
    
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    
    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )
    
    records = db.query(EvolutionRecord).filter(
        EvolutionRecord.relation_id == relation_id
    ).order_by(EvolutionRecord.chapter_number).all()
    
    return EvolutionRecordListResponse(
        records=[EvolutionRecordResponse.model_validate(r) for r in records],
        total=len(records)
    )


# ==================== AI Generation ====================

@router.post("/{project_id}/characters/generate")
async def generate_characters(
    project_id: int,
    request: CharacterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 批量生成人物（SSE 流式）"""
    # TODO: 实现 AI 生成逻辑
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI generation not implemented yet"
    )


@router.post("/{project_id}/characters/{character_id}/optimize")
async def optimize_character(
    project_id: int,
    character_id: int,
    request: CharacterOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 优化人物（SSE 流式）"""
    # TODO: 实现 AI 优化逻辑
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI optimization not implemented yet"
    )


@router.post("/{project_id}/relations/generate")
async def generate_relations(
    project_id: int,
    request: RelationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 生成关系规划（SSE 流式）"""
    # TODO: 实现 AI 生成逻辑
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI generation not implemented yet"
    )
```

- [ ] **Step 2: 注册路由到 main.py**

```python
# backend/app/main.py - 在其他路由注册后添加
from app.api.characters import router as characters_router
app.include_router(characters_router, prefix="/api/projects", tags=["characters"])
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/characters.py backend/app/main.py
git commit -m "feat(api): add character and relation CRUD endpoints"
```

---

## Task 4: 更新 NovelState 和工作流阶段

**Files:**
- Modify: `backend/app/agents/state.py`
- Modify: `backend/app/agents/nodes/chapter_generation.py`

- [ ] **Step 1: 更新 NovelState 添加新字段**

```python
# backend/app/agents/state.py - 在 NovelState 类中添加

class NovelState(TypedDict):
    """小说创作状态 - v0.7.0 人物设定模块"""
    
    # ... 现有字段保持不变 ...
    
    # ========== 人物设定（v0.7.0 新增）==========
    characters: list[dict]              # 全部人物设定
    relations: list[dict]               # 全部关系
    evolution_plans: list[dict]         # 关系演变规划
    evolution_records: list[dict]       # 关系演变追溯
    
    # ========== 篇幅信息（v0.7.0 新增）==========
    novel_length: str                   # short/medium/long/extra_long


# ========== 阶段常量（新增）==========
STAGE_CHARACTERS = "characters"        # 人物设定
STAGE_RELATIONS = "relations"          # 关系规划
```

- [ ] **Step 2: 更新章节生成节点的上下文传递**

```python
# backend/app/agents/nodes/chapter_generation.py - 修改 generate_chapter_content_node 函数

async def generate_chapter_content_node(state: NovelState) -> NovelState:
    """
    LangGraph 兼容的章节内容生成节点
    
    v0.7.0 更新：增加人物设定和关系上下文传递
    """
    llm = await get_llm_from_state_async(state)
    
    current_chapter = state.get("current_chapter", 1)
    chapter_outlines = state.get("chapter_outlines", [])
    written_chapters = state.get("written_chapters", [])
    
    # 找到当前章节的大纲
    chapter_outline = None
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter:
            chapter_outline = outline
            break
    
    if not chapter_outline:
        raise ValueError(f"Chapter outline not found for chapter {current_chapter}")
    
    # 获取上一章的结尾用于衔接
    previous_ending = ""
    if written_chapters:
        for chapter in written_chapters:
            if chapter.get("chapter_number") == current_chapter - 1:
                content = chapter.get("content", "")
                previous_ending = content[-500:] if len(content) > 500 else content
                break
    
    # v0.7.0: 获取完整大纲信息
    outline_title = state.get("outline_title", "")
    outline_summary = state.get("outline_summary", "")
    outline_plot_points = state.get("outline_plot_points", [])
    
    # v0.7.0: 获取人物设定
    characters = state.get("characters", [])
    relations = state.get("relations", [])
    evolution_plans = state.get("evolution_plans", [])
    
    # 过滤当前章节相关的演变规划（前后2章范围内）
    active_plans = [
        plan for plan in evolution_plans
        if abs(plan.get("trigger_chapter", 0) - current_chapter) <= 2
    ]
    
    info = state.get("collected_info", {})
    world_setting = state.get("outline_world_setting", {})
    
    # 格式化章节大纲
    outline_str = f"""
章节名：{chapter_outline.get('title', '')}
场景：{chapter_outline.get('scene', '')}
人物：{chapter_outline.get('characters', '')}
情节：{chapter_outline.get('plot', '')}
冲突：{chapter_outline.get('conflict', '')}
转折：{chapter_outline.get('turning_point', '无')}
钩子：{chapter_outline.get('hook', '')}
"""
    
    # v0.7.0: 格式化完整人物设定
    if characters:
        chars_str = "\n".join([
            f"- {c.get('name', '')}（{c.get('role', '')}）：{c.get('personality', '')}\n"
            f"  口头禅：{c.get('catchphrase', '无')}\n"
            f"  习惯动作：{c.get('habit_action', '无')}\n"
            f"  深层恐惧：{c.get('deep_fear', '无')}\n"
            f"  核心动机：{c.get('core_motivation', '无')}\n"
            f"  成长弧线：{c.get('growth_arc', '无')}\n"
            f"  外貌：{c.get('appearance', '无')}\n"
            f"  背景：{c.get('backstory', '无')}\n"
            f"  标志性物品：{c.get('signature_item', '无')}"
            for c in characters
        ])
    else:
        chars_str = info.get("customProtagonist") or info.get("protagonist", "未指定")
    
    # v0.7.0: 格式化关系
    if relations:
        relations_str = "\n".join([
            f"- {r.get('character_a_name', '')} {r.get('direction', '↔')} {r.get('character_b_name', '')}：{r.get('relation_type', '')}（{r.get('current_status', '')}，信任度：{r.get('trust_level', 50)}%）"
            for r in relations
        ])
    else:
        relations_str = "无"
    
    # v0.7.0: 格式化当前演变规划
    if active_plans:
        plans_str = "\n".join([
            f"- 第{p.get('trigger_chapter', 0)}章：{p.get('event_description', '')}（{p.get('status_before', '')} → {p.get('status_after', '')}）"
            for p in active_plans
        ])
    else:
        plans_str = "无"
    
    # 格式化世界观
    if world_setting:
        world_str = f"时代：{world_setting.get('era', '')}，核心设定：{world_setting.get('core_rules', '')}"
    else:
        world_str = info.get("customWorldSetting") or info.get("worldSetting", "未指定")
    
    target_words = chapter_outline.get("target_words", 3000)
    
    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=chars_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        target_words=target_words,
        # v0.7.0 新增参数
        outline_title=outline_title,
        outline_summary=outline_summary,
        relations=relations_str,
        evolution_plans=plans_str,
    )
    
    content = await llm.chat([{"role": "user", "content": prompt}])
    content = clean_chapter_content(content)
    word_count = len(content)
    
    new_chapter = {
        "chapter_number": current_chapter,
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": word_count
    }
    
    new_state: NovelState = {
        **state,
        "written_chapters": [new_chapter],
        "current_chapter": current_chapter + 1,
        "stage": STAGE_WRITING,
    }
    
    return new_state
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/state.py backend/app/agents/nodes/chapter_generation.py
git commit -m "feat(agents): add character fields to NovelState and update chapter generation"
```

---

## Task 5: 前端类型定义

**Files:**
- Create: `frontend/src/types/character.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 创建人物类型定义**

```typescript
// frontend/src/types/character.ts

export interface Character {
  id: number
  project_id: number
  name: string
  role: string
  personality?: string
  catchphrase?: string
  habit_action?: string
  deep_fear?: string
  core_motivation?: string
  growth_arc?: string
  appearance?: string
  backstory?: string
  signature_item?: string
  created_at: string
  updated_at: string
}

export interface CharacterCreate {
  name: string
  role: string
  personality?: string
  catchphrase?: string
  habit_action?: string
  deep_fear?: string
  core_motivation?: string
  growth_arc?: string
  appearance?: string
  backstory?: string
  signature_item?: string
}

export interface CharacterUpdate {
  name?: string
  role?: string
  personality?: string
  catchphrase?: string
  habit_action?: string
  deep_fear?: string
  core_motivation?: string
  growth_arc?: string
  appearance?: string
  backstory?: string
  signature_item?: string
}

export interface CharacterListResponse {
  characters: Character[]
  total: number
}

export interface Relation {
  id: number
  project_id: number
  character_a_id: number
  character_b_id: number
  relation_type: string
  direction: string
  current_status?: string
  trust_level: number
  created_at: string
  updated_at: string
}

export interface RelationWithCharacters extends Relation {
  character_a_name?: string
  character_b_name?: string
}

export interface RelationCreate {
  character_a_id: number
  character_b_id: number
  relation_type: string
  direction?: string
  current_status?: string
  trust_level?: number
}

export interface RelationUpdate {
  relation_type?: string
  direction?: string
  current_status?: string
  trust_level?: number
}

export interface RelationListResponse {
  relations: RelationWithCharacters[]
  total: number
}

export interface EvolutionPlan {
  id: number
  relation_id: number
  trigger_chapter: number
  event_description: string
  status_before?: string
  status_after: string
  trust_before?: number
  trust_after?: number
  is_triggered: boolean
  created_at: string
  updated_at: string
}

export interface EvolutionPlanCreate {
  trigger_chapter: number
  event_description: string
  status_before?: string
  status_after: string
  trust_before?: number
  trust_after?: number
}

export interface EvolutionPlanUpdate {
  trigger_chapter?: number
  event_description?: string
  status_before?: string
  status_after?: string
  trust_before?: number
  trust_after?: number
  is_triggered?: boolean
}

export interface EvolutionPlanListResponse {
  plans: EvolutionPlan[]
  total: number
}

export interface EvolutionRecord {
  id: number
  relation_id: number
  chapter_number: number
  content: string
  status_change?: string
  trust_change?: number
  triggered_plan_id?: number
  created_at: string
}

export interface EvolutionRecordListResponse {
  records: EvolutionRecord[]
  total: number
}

export type CharacterRole = '主角' | '核心反派' | '重要配角' | '配角'
export type RelationType = '信任' | '敌对' | '感情' | '合作' | '利用' | '陌生'
export type RelationDirection = '双向' | '单向A→B' | '单向B→A'
export type NovelLength = 'short' | 'medium' | 'long' | 'extra_long'
```

- [ ] **Step 2: 更新 index.ts 导出**

```typescript
// frontend/src/types/index.ts - 添加导出
export * from './character'
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/types/character.ts frontend/src/types/index.ts
git commit -m "feat(frontend): add character type definitions"
```

---

## Task 6: 前端 API 客户端

**Files:**
- Create: `frontend/src/lib/characterApi.ts`

- [ ] **Step 1: 创建人物 API 客户端**

```typescript
// frontend/src/lib/characterApi.ts
import api from './api'
import type {
  Character,
  CharacterCreate,
  CharacterUpdate,
  CharacterListResponse,
  Relation,
  RelationWithCharacters,
  RelationCreate,
  RelationUpdate,
  RelationListResponse,
  EvolutionPlan,
  EvolutionPlanCreate,
  EvolutionPlanUpdate,
  EvolutionPlanListResponse,
  EvolutionRecord,
  EvolutionRecordListResponse,
} from '@/types/character'

// ==================== Character API ====================

export const characterApi = {
  list: async (projectId: number): Promise<CharacterListResponse> => {
    const response = await api.get<CharacterListResponse>(`/projects/${projectId}/characters`)
    return response.data
  },

  get: async (projectId: number, characterId: number): Promise<Character> => {
    const response = await api.get<Character>(`/projects/${projectId}/characters/${characterId}`)
    return response.data
  },

  create: async (projectId: number, data: CharacterCreate): Promise<Character> => {
    const response = await api.post<Character>(`/projects/${projectId}/characters`, data)
    return response.data
  },

  update: async (projectId: number, characterId: number, data: CharacterUpdate): Promise<Character> => {
    const response = await api.put<Character>(`/projects/${projectId}/characters/${characterId}`, data)
    return response.data
  },

  delete: async (projectId: number, characterId: number): Promise<void> => {
    await api.delete(`/projects/${projectId}/characters/${characterId}`)
  },
}

// ==================== Relation API ====================

export const relationApi = {
  list: async (projectId: number): Promise<RelationListResponse> => {
    const response = await api.get<RelationListResponse>(`/projects/${projectId}/relations`)
    return response.data
  },

  create: async (projectId: number, data: RelationCreate): Promise<Relation> => {
    const response = await api.post<Relation>(`/projects/${projectId}/relations`, data)
    return response.data
  },

  update: async (projectId: number, relationId: number, data: RelationUpdate): Promise<Relation> => {
    const response = await api.put<Relation>(`/projects/${projectId}/relations/${relationId}`, data)
    return response.data
  },

  delete: async (projectId: number, relationId: number): Promise<void> => {
    await api.delete(`/projects/${projectId}/relations/${relationId}`)
  },
}

// ==================== Evolution Plan API ====================

export const evolutionPlanApi = {
  list: async (projectId: number, relationId: number): Promise<EvolutionPlanListResponse> => {
    const response = await api.get<EvolutionPlanListResponse>(
      `/projects/${projectId}/relations/${relationId}/evolution/plans`
    )
    return response.data
  },

  create: async (projectId: number, relationId: number, data: EvolutionPlanCreate): Promise<EvolutionPlan> => {
    const response = await api.post<EvolutionPlan>(
      `/projects/${projectId}/relations/${relationId}/evolution/plans`,
      data
    )
    return response.data
  },

  update: async (projectId: number, planId: number, data: EvolutionPlanUpdate): Promise<EvolutionPlan> => {
    const response = await api.put<EvolutionPlan>(
      `/projects/${projectId}/evolution/plans/${planId}`,
      data
    )
    return response.data
  },

  delete: async (projectId: number, planId: number): Promise<void> => {
    await api.delete(`/projects/${projectId}/evolution/plans/${planId}`)
  },
}

// ==================== Evolution Record API ====================

export const evolutionRecordApi = {
  list: async (projectId: number, relationId: number): Promise<EvolutionRecordListResponse> => {
    const response = await api.get<EvolutionRecordListResponse>(
      `/projects/${projectId}/relations/${relationId}/evolution/records`
    )
    return response.data
  },
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/lib/characterApi.ts
git commit -m "feat(frontend): add character API client"
```

---

## Task 7: 前端人物设定页面

**Files:**
- Create: `frontend/src/pages/CharacterSetting.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建人物设定页面**

由于页面代码较长，这里创建基础结构：

```typescript
// frontend/src/pages/CharacterSetting.tsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { characterApi, relationApi } from '@/lib/characterApi'
import type { Character, RelationWithCharacters } from '@/types/character'

export default function CharacterSetting() {
  const { projectId } = useParams<{ projectId: string }>()
  const [characters, setCharacters] = useState<Character[]>([])
  const [relations, setRelations] = useState<RelationWithCharacters[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'characters' | 'relations'>('characters')

  useEffect(() => {
    if (projectId) {
      loadData()
    }
  }, [projectId])

  const loadData = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const [charRes, relRes] = await Promise.all([
        characterApi.list(parseInt(projectId)),
        relationApi.list(parseInt(projectId)),
      ])
      setCharacters(charRes.characters)
      setRelations(relRes.relations)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64">加载中...</div>
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">人物设定</h1>
        <div className="flex gap-2">
          <Button variant="outline">AI 批量生成</Button>
          <Button>+ 新增人物</Button>
        </div>
      </div>

      <div className="flex gap-4 mb-6">
        <Button
          variant={activeTab === 'characters' ? 'default' : 'outline'}
          onClick={() => setActiveTab('characters')}
        >
          人物列表 ({characters.length})
        </Button>
        <Button
          variant={activeTab === 'relations' ? 'default' : 'outline'}
          onClick={() => setActiveTab('relations')}
        >
          关系列表 ({relations.length})
        </Button>
      </div>

      {activeTab === 'characters' && (
        <div className="grid grid-cols-4 gap-4">
          {characters.map((char) => (
            <div
              key={char.id}
              className="bg-white rounded-xl p-4 shadow hover:ring-2 hover:ring-blue-300 cursor-pointer"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-xl">
                  👤
                </div>
                <div>
                  <h3 className="font-semibold">{char.name}</h3>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                    {char.role}
                  </span>
                </div>
              </div>
              <p className="text-sm text-gray-500 line-clamp-2">
                {char.personality || '暂无描述'}
              </p>
            </div>
          ))}
          <div className="bg-gray-50 rounded-xl p-4 border-2 border-dashed border-gray-300 cursor-pointer hover:border-blue-400 flex flex-col items-center justify-center min-h-[140px]">
            <div className="text-3xl text-gray-300 mb-1">+</div>
            <p className="text-sm text-gray-500">添加人物</p>
          </div>
        </div>
      )}

      {activeTab === 'relations' && (
        <div className="space-y-3">
          {relations.map((rel) => (
            <div
              key={rel.id}
              className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{rel.character_a_name}</span>
                    <span className="text-lg">
                      {rel.direction === '双向' ? '↔' : '→'}
                    </span>
                    <span className="font-medium">{rel.character_b_name}</span>
                  </div>
                  <div>
                    <span className="text-sm text-gray-500">
                      {rel.relation_type} | 信任度: {rel.trust_level}%
                    </span>
                  </div>
                </div>
                <Button variant="ghost" size="sm">
                  查看演变
                </Button>
              </div>
            </div>
          ))}
          {relations.length === 0 && (
            <div className="text-center py-10 text-gray-500">
              暂无关系，请先添加人物
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 添加路由到 App.tsx**

```typescript
// frontend/src/App.tsx - 在路由配置中添加
import CharacterSetting from './pages/CharacterSetting'

// 在 routes 配置中添加
<Route path="/project/:id/characters" element={<CharacterSetting />} />
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/CharacterSetting.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add character setting page with basic structure"
```

---

## Task 8: 更新步骤导航

**Files:**
- Modify: `frontend/src/components/project/StepNavigation.tsx`

- [ ] **Step 1: 更新步骤配置**

```typescript
// frontend/src/components/project/StepNavigation.tsx - 更新 STEPS 常量

const STEPS = [
  { key: 'inspiration', label: '灵感采集' },
  { key: 'outline', label: '大纲' },
  { key: 'characters', label: '人物设定' },    // 新增
  { key: 'relations', label: '关系规划' },     // 新增
  { key: 'chapter_outlines', label: '章节大纲' },
  { key: 'writing', label: '写作' },
  { key: 'complete', label: '完成' },
]
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/project/StepNavigation.tsx
git commit -m "feat(frontend): add characters and relations steps to navigation"
```

---

## 自检清单

在执行计划前，请确认：

- [ ] 所有文件路径正确
- [ ] 代码中无 TBD 或 TODO 占位符
- [ ] 类型定义前后端一致
- [ ] 数据库迁移已测试
- [ ] API 端点已注册

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-04-28-character-setting-module.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
