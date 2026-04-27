# Prompt 模板系统级配置实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 简化智能体提示词配置，移除未使用的用户级/项目级功能，仅保留系统级配置。

**Architecture:** 新建 system_config 表存储系统级提示词，删除 agent_prompts 和 project_agent_prompts 表，LangGraph 节点从数据库读取提示词。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, Zustand

---

## 文件结构

**删除：**
- `backend/app/models/agent_prompt.py`
- `backend/app/api/agent_prompts.py`
- `backend/app/services/prompt_service.py`
- `backend/app/schemas/agent_prompt.py`
- `frontend/src/components/settings/ProjectPromptConfig.tsx`

**创建：**
- `backend/app/models/system_config.py` - 系统配置模型
- `backend/app/api/system_prompts.py` - 系统 Prompt API
- `backend/app/schemas/system_prompt.py` - Schema 定义
- `backend/alembic/versions/20260426_system_prompts.py` - 数据库迁移

**修改：**
- `backend/app/models/__init__.py` - 导出新模型
- `backend/app/models/user.py` - 移除 agent_prompts relationship
- `backend/app/models/project.py` - 移除 agent_prompts relationship
- `backend/app/main.py` - 注册新路由
- `backend/app/agents/nodes/*.py` - 从数据库读取提示词
- `frontend/src/pages/Settings.tsx` - 新 UI
- `frontend/src/lib/api.ts` - 新 API 调用
- `frontend/src/types/index.ts` - 类型定义

---

## Task 1: 创建数据库迁移

**Files:**
- Create: `backend/alembic/versions/20260426_system_prompts.py`

- [ ] **Step 1: 创建迁移文件**

```python
"""system prompts migration

Revision ID: 20260426_system_prompts
Revises: 8d29d8d632e5
Create Date: 2026-04-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = '20260426_system_prompts'
down_revision = '8d29d8d632e5'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建 system_config 表
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('key')
    )

    # 2. 插入默认提示词
    op.execute(text("""
        INSERT INTO system_config (key, value, updated_at) VALUES
        ('prompt_outline_generation', '你是一个拥有 20 年经验的资深小说策划师...', NOW()),
        ('prompt_chapter_outline_generation', '你是一个精通伏笔编排和人物弧光的章节策划师...', NOW()),
        ('prompt_chapter_content_generation', '你是一位获得茅盾文学奖的当代小说家...', NOW()),
        ('prompt_review', '你是一位从业 30 年的文学编辑...', NOW()),
        ('prompt_rewrite', '你是一位资深小说编辑兼作家...', NOW())
    """))

    # 3. 删除 project_agent_prompts 表
    op.drop_table('project_agent_prompts')

    # 4. 删除 agent_prompts 表
    op.drop_table('agent_prompts')


def downgrade():
    # 重新创建 agent_prompts 表
    op.create_table(
        'agent_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'agent_type', name='uq_user_agent_type')
    )

    # 重新创建 project_agent_prompts 表
    op.create_table(
        'project_agent_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'agent_type', name='uq_project_agent_type')
    )

    # 删除 system_config 表
    op.drop_table('system_config')
```

- [ ] **Step 2: 运行迁移验证**

Run: `docker exec novelagent-backend-1 alembic upgrade head`
Expected: 迁移成功，无错误

---

## Task 2: 创建 SystemConfig 模型

**Files:**
- Create: `backend/app/models/system_config.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建模型文件**

```python
"""System configuration model"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime

from app.database import Base


class SystemConfig(Base):
    """System-wide configuration key-value store"""
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig key={self.key}>"
```

- [ ] **Step 2: 更新 models/__init__.py**

在 `backend/app/models/__init__.py` 添加导出：

```python
from app.models.system_config import SystemConfig
```

---

## Task 3: 创建 Schema 定义

**Files:**
- Create: `backend/app/schemas/system_prompt.py`

- [ ] **Step 1: 创建 Schema 文件**

```python
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
```

---

## Task 4: 创建系统 Prompt API

**Files:**
- Create: `backend/app/api/system_prompts.py`

- [ ] **Step 1: 创建 API 路由**

```python
"""System prompts API routes"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.system_config import SystemConfig
from app.schemas.system_prompt import (
    SystemPromptResponse,
    SystemPromptListResponse,
    SystemPromptUpdate,
    AGENT_TYPES,
)
from app.agents.prompts import DEFAULT_PROMPTS

router = APIRouter()

# Key mapping from agent_type to database key
PROMPT_KEY_MAP = {
    "outline_generation": "prompt_outline_generation",
    "chapter_outline_generation": "prompt_chapter_outline_generation",
    "chapter_content_generation": "prompt_chapter_content_generation",
    "review": "prompt_review",
    "rewrite": "prompt_rewrite",
}


def get_prompt_key(agent_type: str) -> str:
    """Get database key for agent type"""
    return PROMPT_KEY_MAP.get(agent_type, f"prompt_{agent_type}")


@router.get("/", response_model=SystemPromptListResponse)
async def get_system_prompts(db: Session = None):
    """Get all system prompts"""
    # 快速获取 db session
    from app.database import SessionLocal
    db = db or SessionLocal()
    
    try:
        prompts = []
        for agent_type, meta in AGENT_TYPES.items():
            key = get_prompt_key(agent_type)
            config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            
            content = config.value if config else DEFAULT_PROMPTS.get(agent_type, "")
            updated_at = config.updated_at if config else None
            
            prompts.append(SystemPromptResponse(
                agent_type=agent_type,
                agent_name=meta["name"],
                description=meta["description"],
                prompt_content=content,
                variables=meta["variables"],
                updated_at=updated_at
            ))
        
        return SystemPromptListResponse(prompts=prompts)
    finally:
        if db:
            db.close()


@router.put("/{agent_type}", response_model=SystemPromptResponse)
async def update_system_prompt(
    agent_type: str,
    request: SystemPromptUpdate,
    db: Session = None
):
    """Update a system prompt"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    from app.database import SessionLocal
    db = db or SessionLocal()
    
    try:
        key = get_prompt_key(agent_type)
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        
        if config:
            config.value = request.prompt_content
        else:
            config = SystemConfig(key=key, value=request.prompt_content)
            db.add(config)
        
        db.commit()
        db.refresh(config)
        
        meta = AGENT_TYPES[agent_type]
        return SystemPromptResponse(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            prompt_content=config.value,
            variables=meta["variables"],
            updated_at=config.updated_at
        )
    finally:
        if db:
            db.close()


@router.post("/{agent_type}/reset", response_model=SystemPromptResponse)
async def reset_system_prompt(agent_type: str, db: Session = None):
    """Reset a system prompt to default"""
    if agent_type not in AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent type: {agent_type}")
    
    from app.database import SessionLocal
    db = db or SessionLocal()
    
    try:
        key = get_prompt_key(agent_type)
        default_content = DEFAULT_PROMPTS.get(agent_type, "")
        
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        
        if config:
            config.value = default_content
        else:
            config = SystemConfig(key=key, value=default_content)
            db.add(config)
        
        db.commit()
        db.refresh(config)
        
        meta = AGENT_TYPES[agent_type]
        return SystemPromptResponse(
            agent_type=agent_type,
            agent_name=meta["name"],
            description=meta["description"],
            prompt_content=config.value,
            variables=meta["variables"],
            updated_at=config.updated_at
        )
    finally:
        if db:
            db.close()
```

---

## Task 5: 注册 API 路由

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 添加路由导入和注册**

找到 `main.py` 中的路由注册部分，添加：

```python
from app.api.system_prompts import router as system_prompts_router
app.include_router(system_prompts_router, prefix="/api/system/prompts", tags=["system-prompts"])
```

并移除旧的 agent_prompts 路由：

```python
# 删除这行（如果存在）
# from app.api.agent_prompts import router as agent_prompts_router
# app.include_router(agent_prompts_router, prefix="/api", tags=["agent-prompts"])
```

---

## Task 6: 删除旧模型关系

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/project.py`

- [ ] **Step 1: 修改 user.py**

移除 `agent_prompts` relationship：

```python
# 删除这行
agent_prompts = relationship("AgentPrompt", back_populates="user", cascade="all, delete-orphan")
```

- [ ] **Step 2: 修改 project.py**

移除 `agent_prompts` relationship：

```python
# 删除这行
agent_prompts = relationship("ProjectAgentPrompt", back_populates="project", cascade="all, delete-orphan")
```

---

## Task 7: 删除旧文件

**Files:**
- Delete: `backend/app/models/agent_prompt.py`
- Delete: `backend/app/api/agent_prompts.py`
- Delete: `backend/app/services/prompt_service.py`
- Delete: `backend/app/schemas/agent_prompt.py`
- Delete: `frontend/src/components/settings/ProjectPromptConfig.tsx`

- [ ] **Step 1: 删除后端文件**

```bash
rm backend/app/models/agent_prompt.py
rm backend/app/api/agent_prompts.py
rm backend/app/services/prompt_service.py
rm backend/app/schemas/agent_prompt.py
```

- [ ] **Step 2: 删除前端文件**

```bash
rm frontend/src/components/settings/ProjectPromptConfig.tsx
```

---

## Task 8: 更新前端类型定义

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 添加新类型，移除旧类型**

```typescript
// 添加 SystemPrompt 类型
export interface SystemPrompt {
  agent_type: string
  agent_name: string
  description: string
  prompt_content: string
  variables: string[]
  updated_at?: string
}

export interface SystemPromptListResponse {
  prompts: SystemPrompt[]
}

export interface SystemPromptUpdate {
  prompt_content: string
}

// 移除旧的 AgentPrompt, ProjectAgentPrompt 等类型
```

---

## Task 9: 更新前端 API

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 替换 agentPromptsApi 为 systemPromptsApi**

```typescript
export const systemPromptsApi = {
  list: () => {
    return request<SystemPromptListResponse>("/api/system/prompts");
  },

  update: (agentType: string, data: SystemPromptUpdate) => {
    return request<SystemPrompt>(
      `/api/system/prompts/${agentType}`,
      {
        method: "PUT",
        body: JSON.stringify(data),
      }
    );
  },

  reset: (agentType: string) => {
    return request<SystemPrompt>(
      `/api/system/prompts/${agentType}/reset`,
      { method: "POST" }
    );
  },
};
```

并移除旧的 `agentPromptsApi`。

---

## Task 10: 重构前端设置页面

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 重写智能体管理 Tab**

使用顶部标签 + 大编辑区布局：

```tsx
{/* 智能体管理 */}
{activeTab === 'agents' && (
  <div id="agents-panel" role="tabpanel" className="max-w-4xl">
    <h3 className="text-lg font-semibold mb-1">智能体管理</h3>
    <p className="text-muted-foreground text-sm mb-6">配置系统级 Prompt 模板</p>

    {/* 标签切换 */}
    <Tabs value={selectedAgent} onValueChange={setSelectedAgent}>
      <TabsList>
        <TabsTrigger value="outline_generation">大纲生成</TabsTrigger>
        <TabsTrigger value="chapter_outline_generation">章节大纲</TabsTrigger>
        <TabsTrigger value="chapter_content_generation">正文生成</TabsTrigger>
        <TabsTrigger value="review">审核</TabsTrigger>
        <TabsTrigger value="rewrite">重写</TabsTrigger>
      </TabsList>

      {/* 编辑区 */}
      <div className="mt-4">
        {currentPrompt && (
          <>
            {/* 变量提示 */}
            <div className="p-4 bg-muted rounded-lg mb-4">
              <div className="text-sm text-muted-foreground mb-2">可用变量</div>
              <div className="flex flex-wrap gap-2">
                {currentPrompt.variables.map((v) => (
                  <code key={v} className="bg-background px-2 py-1 rounded text-sm">
                    {`{${v}}`}
                  </code>
                ))}
              </div>
            </div>

            {/* 编辑器 */}
            <Textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="min-h-[400px] font-mono text-sm"
            />

            {/* 操作按钮 */}
            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                {currentPrompt.updated_at && `上次更新：${new Date(currentPrompt.updated_at).toLocaleString()}`}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleReset} disabled={resetting}>
                  {resetting ? '重置中...' : '重置默认'}
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? '保存中...' : '保存'}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </Tabs>
  </div>
)}
```

---

## Task 11: 修改 LangGraph 节点读取提示词

**Files:**
- Modify: `backend/app/agents/nodes/outline_generation.py`
- Modify: `backend/app/agents/nodes/chapter_generation.py`
- Modify: `backend/app/agents/nodes/review.py`
- Modify: `backend/app/agents/nodes/rewrite.py`

- [ ] **Step 1: 创建提示词服务函数**

在 `backend/app/services/` 创建 `prompt_loader.py`：

```python
"""Prompt loader service"""

from sqlalchemy.orm import Session
from app.models.system_config import SystemConfig
from app.agents.prompts import DEFAULT_PROMPTS


def get_system_prompt(db: Session, agent_type: str) -> str:
    """Get system prompt for agent type from database or default"""
    key = f"prompt_{agent_type}"
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    
    if config and config.value:
        return config.value
    
    return DEFAULT_PROMPTS.get(agent_type, "")
```

- [ ] **Step 2: 修改 outline_generation.py**

移除直接导入，改用服务：

```python
# 移除
# from app.agents.prompts import OUTLINE_GENERATION_PROMPT

# 添加
from app.services.prompt_loader import get_system_prompt
from app.database import SessionLocal

def prepare_outline_prompt(state: NovelState) -> tuple[str, int]:
    """准备大纲生成提示词和章节数"""
    db = SessionLocal()
    try:
        prompt_template = get_system_prompt(db, "outline_generation")
        # ... 其余逻辑不变
        prompt = prompt_template.format(
            inspiration_template=inspiration_template,
            chapter_count=chapter_count
        )
        return prompt, chapter_count
    finally:
        db.close()
```

- [ ] **Step 3: 同样修改其他节点文件**

对 `chapter_generation.py`、`review.py`、`rewrite.py` 应用相同模式。

---

## Task 12: 端到端测试

- [ ] **Step 1: 运行后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

Expected: 所有测试通过

- [ ] **Step 2: 手动测试前端**

1. 打开设置页面 → 智能体管理
2. 切换标签，确认提示词内容显示正确
3. 编辑提示词，保存，刷新页面确认保存成功
4. 点击"重置默认"，确认恢复到默认值

- [ ] **Step 3: 测试工作流**

1. 创建新项目，运行工作流
2. 确认使用的是数据库中的提示词
3. 修改提示词后重新运行，确认生效

---

## Task 13: 提交代码

- [ ] **Step 1: 提交更改**

```bash
git add -A
git commit -m "refactor: simplify prompt config to system-level only

- Remove user-level and project-level prompt customization
- Add system_config table for system-level prompts
- Update LangGraph nodes to read prompts from database
- Simplify frontend UI with tab-based editor

BREAKING CHANGE: agent_prompts and project_agent_prompts tables removed"
```
