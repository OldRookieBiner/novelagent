# Agent 模式深化 + 工作台融合 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 5 个 Agent tools、将 Agent 深度融入工作台（模型选择器、并发控制、context 自动刷新）、优化交互体验（tool 可展开详情、生成结果预览卡片）。

**Architecture:**
- Service 层全部 **async**（因为 LLMService.chat/chat_stream 是 async）
- Tool 使用 `@tool` + async 函数体（`create_react_agent` 原生支持 async tool）
- 运行时上下文通过 **contextvars** 传递（model_config_id, user_id），线程安全+async 安全
- 生成类 tool MVP **不做 side channel 流式**——`astream_events` 在 tool 执行期间不产出事件，双源 SSE 方案不可行。改为：tool 执行期间前端显示"生成中..."，完成后返回摘要+预览卡片，完整内容写入 DB 后在 WritingPanel 查看
- 并发控制通过 project 表 is_busy 字段实现乐观锁（5 分钟超时自动释放）

**Tech Stack:** FastAPI + LangGraph (create_react_agent + async tools) + SQLAlchemy | React + Zustand + shadcn/ui | PostgreSQL + Alembic

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `backend/app/agents/services/__init__.py` | 包初始化 |
| `backend/app/agents/services/outline_service.py` | 大纲读写（从 agent_tools 抽出） |
| `backend/app/agents/services/chapter_service.py` | 章节生成/审核/重写核心逻辑 |
| `backend/app/agents/services/character_service.py` | 角色 CRUD |
| `backend/app/agents/services/relation_service.py` | 关系读写 |
| `backend/app/agents/tool_context.py` | contextvars 运行时上下文 |
| `backend/alembic/versions/20260523_add_project_busy_fields.py` | 数据库迁移 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/agents/agent_tools.py` | 全部改为 async tool + 调 services + 新增 5 tools |
| `backend/app/api/agent.py` | 并发控制 + tool_context 设置/清理 + 生成类 tool 预览卡片事件 |
| `backend/app/agents/sse_events.py` | 新增 format_agent_review 事件 |
| `backend/app/models/project.py` | 新增 is_busy / busy_since / busy_by 字段 |
| `frontend/src/stores/workbenchStore.ts` | AiMessage segments + isAgentBusy + AiAction 含 args/result |
| `frontend/src/lib/agentApi.ts` | 处理 chunk/review 事件 + 传递 modelConfigId |
| `frontend/src/components/workbench/AICompanionSidebar.tsx` | 模型选择器 + 并发禁用 + segments 处理 |
| `frontend/src/components/workbench/AICompanionChat.tsx` | segments 混合内容渲染 |
| `frontend/src/components/workbench/AIActionCard.tsx` | 可展开详情 |

---

## Task 1: 数据库迁移 — is_busy 字段

**Files:**
- Create: `backend/alembic/versions/20260523_add_project_busy_fields.py`
- Modify: `backend/app/models/project.py`

- [ ] **Step 1: 写迁移文件**

最新 migration 是 `20260518_arc_outline`，以此作为 down_revision。

```python
# backend/alembic/versions/20260523_add_project_busy_fields.py
"""add is_busy fields to projects

Revision ID: 20260523_busy
Revises: 20260518_arc_outline
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa

revision = '20260523_busy'
down_revision = '20260518_arc_outline'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('projects', sa.Column('is_busy', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('projects', sa.Column('busy_since', sa.DateTime(), nullable=True))
    op.add_column('projects', sa.Column('busy_by', sa.String(20), nullable=True))

def downgrade():
    op.drop_column('projects', 'busy_by')
    op.drop_column('projects', 'busy_since')
    op.drop_column('projects', 'is_busy')
```

- [ ] **Step 2: 更新 Project model**

在 `backend/app/models/project.py` 的 `Project` 类中，`updated_at` 之后添加：

```python
    # 并发控制
    is_busy = Column(Boolean, default=False)
    busy_since = Column(DateTime, nullable=True)
    busy_by = Column(String(20), nullable=True)  # "agent" | "workflow"
```

顶部 import 改为：`from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey`

- [ ] **Step 3: 运行迁移**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

Expected: 迁移成功

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/20260523_add_project_busy_fields.py backend/app/models/project.py
git commit -m "feat(db): add is_busy fields to projects table for concurrency control"
```

---

## Task 2: Tool 运行时上下文 — contextvars

**Files:**
- Create: `backend/app/agents/tool_context.py`

用 contextvars 替代全局变量传递 model_config_id 和 user_id，线程安全且 async 安全。

- [ ] **Step 1: 创建 tool_context.py**

```python
# backend/app/agents/tool_context.py
"""Agent tool 运行时上下文

使用 contextvars 在 async 环境中安全传递请求级别的上下文，
避免全局变量在并发请求间交叉污染。
"""

from contextvars import ContextVar

# 当前请求的模型配置 ID
_current_model_config_id: ContextVar[int | None] = ContextVar('model_config_id', default=None)

# 当前请求的用户 ID
_current_user_id: ContextVar[int | None] = ContextVar('user_id', default=None)


def set_tool_context(model_config_id: int | None = None, user_id: int | None = None):
    """设置当前请求的 tool 上下文，返回重置 token 列表"""
    tokens = []
    if model_config_id is not None:
        tokens.append(_current_model_config_id.set(model_config_id))
    if user_id is not None:
        tokens.append(_current_user_id.set(user_id))
    return tokens


def reset_tool_context(tokens: list):
    """重置 tool 上下文（请求结束时调用）"""
    for token in tokens:
        token.var.reset(token)


def get_model_config_id() -> int | None:
    """获取当前请求的模型配置 ID"""
    return _current_model_config_id.get()


def get_user_id() -> int | None:
    """获取当前请求的用户 ID"""
    return _current_user_id.get()
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/agents/tool_context.py
git commit -m "feat(backend): add contextvars-based tool context for safe async request scoping"
```

---

## Task 3: Services 层 — 共享能力

**Files:**
- Create: `backend/app/agents/services/__init__.py`
- Create: `backend/app/agents/services/outline_service.py`
- Create: `backend/app/agents/services/character_service.py`
- Create: `backend/app/agents/services/relation_service.py`
- Create: `backend/app/agents/services/chapter_service.py`

关键设计：
- 全部 **async**（因为 LLMService.chat/chat_stream 是 async）
- 每个函数接收 `db: Session` 参数，调用方管理 Session 生命周期
- chapter_service 的 `generate_chapter` / `rewrite_chapter` 在生成完成后将全文写入 DB，返回摘要
- `review_chapter` 返回结构化审核结果

- [ ] **Step 1: 创建 services 包**

```python
# backend/app/agents/services/__init__.py
```

- [ ] **Step 2: 创建 outline_service.py**

```python
# backend/app/agents/services/outline_service.py
"""大纲读写服务"""

from sqlalchemy.orm import Session
from app.models.outline import Outline, ChapterOutline
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def read_outline(db: Session, project_id: int) -> dict:
    """读取项目大纲"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在"}
    return {
        "title": outline.title,
        "summary": outline.summary,
        "plot_points": outline.plot_points,
        "chapter_count_suggested": outline.chapter_count_suggested,
        "confirmed": outline.confirmed,
    }


async def update_outline(db: Session, project_id: int, title: str = None, summary: str = None, plot_points: list = None) -> dict:
    """修改项目大纲"""
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if not outline:
        return {"error": "大纲不存在"}
    changes = []
    if title is not None:
        changes.append(f"标题: {outline.title} → {title}")
        outline.title = title
    if summary is not None:
        outline.summary = summary
        changes.append("概述已更新")
    if plot_points is not None:
        outline.plot_points = plot_points
        changes.append("情节节点已更新")
    db.commit()
    return {"success": True, "message": "大纲已更新", "changes": changes}


async def read_chapter_outlines(db: Session, project_id: int) -> list:
    """读取所有章节大纲"""
    outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).order_by(ChapterOutline.chapter_number).all()
    return [
        {
            "id": co.id,
            "chapter_number": co.chapter_number,
            "title": co.title,
            "plot": co.plot,
            "confirmed": co.confirmed,
        }
        for co in outlines
    ]


async def update_chapter_outline(db: Session, project_id: int, chapter_outline_id: int, title: str = None, plot: str = None) -> dict:
    """修改章节大纲"""
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.id == chapter_outline_id,
        ChapterOutline.project_id == project_id
    ).first()
    if not outline:
        return {"error": "章节大纲不存在"}
    changes = []
    if title is not None:
        changes.append(f"标题: {outline.title} → {title}")
        outline.title = title
    if plot is not None:
        outline.plot = plot
        changes.append("情节已更新")
    db.commit()
    return {"success": True, "message": f"第{outline.chapter_number}章大纲已更新", "changes": changes}
```

- [ ] **Step 3: 创建 character_service.py**

```python
# backend/app/agents/services/character_service.py
"""角色 CRUD 服务"""

from sqlalchemy.orm import Session
from app.models.character import Character
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def read_characters(db: Session, project_id: int) -> list:
    """读取所有角色"""
    characters = db.query(Character).filter(Character.project_id == project_id).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "personality": c.personality,
            "core_motivation": c.core_motivation,
            "growth_arc": c.growth_arc,
        }
        for c in characters
    ]


async def create_character(db: Session, project_id: int, name: str, role: str, personality: str = "", core_motivation: str = "") -> dict:
    """新增角色"""
    character = Character(
        project_id=project_id,
        name=name,
        role=role,
        personality=personality,
        core_motivation=core_motivation,
    )
    db.add(character)
    db.commit()
    return {"success": True, "message": f"角色「{name}」已创建", "id": character.id}


async def update_character(db: Session, project_id: int, character_id: int, name: str = None, role: str = None, personality: str = None, core_motivation: str = None, growth_arc: str = None) -> dict:
    """修改角色"""
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()
    if not character:
        return {"error": "角色不存在"}
    changes = []
    if name is not None:
        changes.append(f"姓名: {character.name} → {name}")
        character.name = name
    if role is not None:
        changes.append(f"定位: {character.role} → {role}")
        character.role = role
    if personality is not None:
        character.personality = personality
        changes.append("性格已更新")
    if core_motivation is not None:
        character.core_motivation = core_motivation
        changes.append("核心动机已更新")
    if growth_arc is not None:
        character.growth_arc = growth_arc
        changes.append("成长弧线已更新")
    db.commit()
    return {"success": True, "message": f"角色「{character.name}」已更新", "changes": changes}
```

- [ ] **Step 4: 创建 relation_service.py**

```python
# backend/app/agents/services/relation_service.py
"""人物关系读写服务"""

from sqlalchemy.orm import Session
from app.models.character import Relation, Character
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def read_relations(db: Session, project_id: int) -> list:
    """读取项目人物关系"""
    relations = db.query(Relation).filter(Relation.project_id == project_id).all()
    result = []
    for r in relations:
        char_a = db.query(Character).filter(Character.id == r.character_a_id).first()
        char_b = db.query(Character).filter(Character.id == r.character_b_id).first()
        result.append({
            "id": r.id,
            "character_a": char_a.name if char_a else f"ID:{r.character_a_id}",
            "character_b": char_b.name if char_b else f"ID:{r.character_b_id}",
            "relation_type": r.relation_type,
            "direction": r.direction,
            "current_status": r.current_status,
            "trust_level": r.trust_level,
        })
    return result


async def update_relation(db: Session, project_id: int, relation_id: int, relation_type: str = None, direction: str = None, current_status: str = None, trust_level: int = None) -> dict:
    """修改人物关系"""
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()
    if not relation:
        return {"error": "关系不存在"}
    changes = []
    if relation_type is not None:
        changes.append(f"类型: {relation.relation_type} → {relation_type}")
        relation.relation_type = relation_type
    if direction is not None:
        changes.append(f"方向: {relation.direction} → {direction}")
        relation.direction = direction
    if current_status is not None:
        relation.current_status = current_status
        changes.append("状态已更新")
    if trust_level is not None:
        changes.append(f"信任度: {relation.trust_level} → {trust_level}")
        relation.trust_level = trust_level
    db.commit()

    char_a = db.query(Character).filter(Character.id == relation.character_a_id).first()
    char_b = db.query(Character).filter(Character.id == relation.character_b_id).first()
    desc = f"{char_a.name if char_a else '?'} ↔ {char_b.name if char_b else '?'}"
    return {"success": True, "message": f"关系「{desc}」已更新", "changes": changes}
```

- [ ] **Step 5: 创建 chapter_service.py**

```python
# backend/app/agents/services/chapter_service.py
"""章节生成/审核/重写核心服务

生成类 tool 的 MVP 方案：
- generate_chapter / rewrite_chapter 调用 LLMService.chat_stream（async）生成全文
- 生成完成后将全文写入 DB（Chapter 表）
- 返回摘要信息（字数、预览前200字），前端在聊天中渲染为预览卡片
- 用户在 WritingPanel 查看完整章节
- 流式输出在后续迭代通过 side channel SSE 实现
"""

import json
from sqlalchemy.orm import Session
from app.models.outline import ChapterOutline
from app.models.chapter import Chapter
from app.services.llm import get_llm_service_from_config, get_llm_service
from app.models.model_config import ModelConfig
from app.models.settings import UserSettings
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_llm_service() -> "LLMService":
    """从 tool context 获取 LLM 服务实例"""
    model_config_id = get_model_config_id()
    user_id = get_user_id()

    if model_config_id and user_id:
        db = Session()
        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == model_config_id).first()
            if config:
                return get_llm_service_from_config(config, user_id)
        except Exception as e:
            logger.warning(f"Failed to get LLM from model config: {e}")
        finally:
            db.close()

    if user_id:
        db = Session()
        try:
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                return get_llm_service(settings)
        except Exception as e:
            logger.warning(f"Failed to get LLM from user settings: {e}")
        finally:
            db.close()

    raise ValueError("无法获取 LLM 配置，请先在设置中配置 API Key")


def _calc_max_tokens(target_words: int) -> int:
    """根据目标字数动态计算 max_tokens"""
    return max(int(target_words * 2.5) + 512, 8192)


async def generate_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """生成章节正文，完成后写入 DB，返回摘要"""
    # 获取章节大纲
    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()
    if not outline:
        return {"error": f"第{chapter_number}章大纲不存在"}

    prompt = f"""请根据以下信息撰写第{chapter_number}章「{outline.title}」的正文：

章节大纲：
- 场景：{outline.scene or ''}
- 出场人物：{outline.characters or ''}
- 情节要点：{outline.plot or ''}
- 冲突：{outline.conflict or ''}
- 结尾：{outline.ending or ''}

目标字数：{outline.target_words or 3000}字

请直接输出章节正文，不要输出标题或其他说明。"""

    llm_service = _get_llm_service()
    max_tokens = _calc_max_tokens(outline.target_words or 3000)

    full_content = ""
    try:
        async for chunk in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Chapter generation failed: {e}")
        return {"error": f"生成失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "生成结果为空，请重试"}

    # 写入 DB
    try:
        chapter = db.query(Chapter).filter(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        ).first()
        if chapter:
            chapter.content = full_content
        else:
            chapter = Chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=outline.title,
                content=full_content,
                target_words=outline.target_words or 3000,
            )
            db.add(chapter)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save chapter: {e}")
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章「{outline.title}」已生成（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title,
        "word_count": word_count,
        "preview": preview,
    }


async def review_chapter(db: Session, project_id: int, chapter_number: int) -> dict:
    """审核章节，返回结构化审核结果"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在，请先生成"}

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    prompt = f"""请审核以下章节内容，按 JSON 格式返回审核结果。

章节大纲：
- 标题：{outline.title if outline else ''}
- 情节要点：{outline.plot if outline else ''}

章节正文（前2000字）：
{chapter.content[:2000]}

请严格按以下 JSON 格式返回，不要包含其他内容：
{{
  "passed": true/false,
  "scores": {{"情节": 1-10, "人物": 1-10, "文笔": 1-10, "逻辑": 1-10, "节奏": 1-10}},
  "issues": [{{"type": "逻辑/情节/人物/文笔", "location": "位置描述", "description": "问题描述"}}],
  "suggestions": "整体改进建议"
}}"""

    llm_service = _get_llm_service()
    try:
        result_text = await llm_service.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        review_result = json.loads(result_text)
        return {"success": True, "review": review_result}
    except json.JSONDecodeError:
        return {"success": True, "review": {"passed": True, "raw": result_text}, "warning": "审核结果解析不完整"}
    except Exception as e:
        logger.error(f"Review failed: {e}")
        return {"error": f"审核失败: {str(e)}"}


async def rewrite_chapter(db: Session, project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写章节，完成后写入 DB，返回摘要"""
    chapter = db.query(Chapter).filter(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    ).first()
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章内容不存在"}

    outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    ).first()

    prompt = f"""请根据审核意见重写第{chapter_number}章「{outline.title if outline else ''}」。

原章节正文：
{chapter.content}

审核意见：
{review_feedback}

章节大纲：
- 情节要点：{outline.plot if outline else ''}
- 冲突：{outline.conflict if outline else ''}
- 结尾：{outline.ending if outline else ''}

目标字数：{outline.target_words or 3000}字

请直接输出重写后的章节正文。"""

    llm_service = _get_llm_service()
    max_tokens = _calc_max_tokens(outline.target_words if outline else 3000)

    full_content = ""
    try:
        async for chunk in llm_service.chat_stream(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        ):
            if chunk:
                full_content += chunk
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        return {"error": f"重写失败: {str(e)}"}

    if not full_content.strip():
        return {"error": "重写结果为空，请重试"}

    try:
        chapter.content = full_content
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"保存失败: {str(e)}"}

    word_count = len(full_content)
    preview = full_content[:200] + ("..." if word_count > 200 else "")
    return {
        "success": True,
        "message": f"第{chapter_number}章已重写（{word_count}字）",
        "chapter_number": chapter_number,
        "title": outline.title if outline else f"第{chapter_number}章",
        "word_count": word_count,
        "preview": preview,
    }
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/agents/services/
git commit -m "feat(backend): add async shared services layer for agent tools"
```

---

## Task 4: 重构 agent_tools — async tools + 调 services + 新增 5 tools

**Files:**
- Modify: `backend/app/agents/agent_tools.py`

关键设计：
- 全部 **async** tool（`create_react_agent` 原生支持 async tool）
- 通过 `tool_context.get_model_config_id()` / `get_user_id()` 获取上下文
- 每个工具内部管理 `SessionLocal()` 的生命周期

- [ ] **Step 1: 重写 agent_tools.py**

```python
# backend/app/agents/agent_tools.py
"""AI 搭档 Agent 的工具集

全部 async tool，调 services/ 共享能力层。
运行时上下文通过 tool_context（contextvars）传递。
"""

from langchain_core.tools import tool
from app.database import SessionLocal

from app.agents.services.outline_service import (
    read_outline as svc_read_outline,
    update_outline as svc_update_outline,
    read_chapter_outlines as svc_read_chapter_outlines,
    update_chapter_outline as svc_update_chapter_outline,
)
from app.agents.services.character_service import (
    read_characters as svc_read_characters,
    create_character as svc_create_character,
    update_character as svc_update_character,
)
from app.agents.services.relation_service import (
    read_relations as svc_read_relations,
    update_relation as svc_update_relation,
)
from app.agents.services.chapter_service import (
    generate_chapter,
    review_chapter,
    rewrite_chapter,
)


# --- 读取类 tools ---

@tool
async def read_outline(project_id: int) -> dict:
    """读取项目的大纲信息，包括标题、概述、情节节点、确认状态"""
    db = SessionLocal()
    try:
        return await svc_read_outline(db, project_id)
    finally:
        db.close()


@tool
async def read_characters(project_id: int) -> list:
    """读取项目的所有角色信息"""
    db = SessionLocal()
    try:
        return await svc_read_characters(db, project_id)
    finally:
        db.close()


@tool
async def read_chapter_outlines(project_id: int) -> list:
    """读取项目的所有章节大纲"""
    db = SessionLocal()
    try:
        return await svc_read_chapter_outlines(db, project_id)
    finally:
        db.close()


@tool
async def read_relations(project_id: int) -> list:
    """读取项目的人物关系，返回关系列表（包含角色名、关系类型、信任度等）"""
    db = SessionLocal()
    try:
        return await svc_read_relations(db, project_id)
    finally:
        db.close()


# --- 写入类 tools ---

@tool
async def update_outline(project_id: int, title: str = None, summary: str = None, plot_points: list = None) -> dict:
    """修改项目的大纲。可以修改标题、概述或情节节点，只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_outline(db, project_id, title, summary, plot_points)
    finally:
        db.close()


@tool
async def update_character(project_id: int, character_id: int, name: str = None, role: str = None, personality: str = None, core_motivation: str = None, growth_arc: str = None) -> dict:
    """修改指定角色的信息。只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_character(db, project_id, character_id, name, role, personality, core_motivation, growth_arc)
    finally:
        db.close()


@tool
async def create_character(project_id: int, name: str, role: str, personality: str = "", core_motivation: str = "") -> dict:
    """为项目新增一个角色"""
    db = SessionLocal()
    try:
        return await svc_create_character(db, project_id, name, role, personality, core_motivation)
    finally:
        db.close()


@tool
async def update_chapter_outline(project_id: int, chapter_outline_id: int, title: str = None, plot: str = None) -> dict:
    """修改指定章节的大纲。只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_chapter_outline(db, project_id, chapter_outline_id, title, plot)
    finally:
        db.close()


@tool
async def update_relations(project_id: int, relation_id: int, relation_type: str = None, direction: str = None, current_status: str = None, trust_level: int = None) -> dict:
    """修改人物关系。可修改关系类型、方向、状态描述、信任度，只传需要修改的字段"""
    db = SessionLocal()
    try:
        return await svc_update_relation(db, project_id, relation_id, relation_type, direction, current_status, trust_level)
    finally:
        db.close()


# --- 生成类 tools ---

@tool
async def generate_chapter_content(project_id: int, chapter_number: int) -> dict:
    """生成指定章节的正文内容。生成完成后自动保存，可在写作面板查看完整内容。返回生成摘要和预览。"""
    db = SessionLocal()
    try:
        return await generate_chapter(db, project_id, chapter_number)
    finally:
        db.close()


@tool
async def review_chapter(project_id: int, chapter_number: int) -> dict:
    """审核指定章节的内容，返回结构化审核结果（分数、问题列表、改进建议）。"""
    db = SessionLocal()
    try:
        return await review_chapter(db, project_id, chapter_number)
    finally:
        db.close()


@tool
async def rewrite_chapter(project_id: int, chapter_number: int, review_feedback: str) -> dict:
    """根据审核意见重写指定章节。重写完成后自动保存，可在写作面板查看。review_feedback 填写审核意见摘要。"""
    db = SessionLocal()
    try:
        return await rewrite_chapter(db, project_id, chapter_number, review_feedback)
    finally:
        db.close()


# 所有 tools 列表
AGENT_TOOLS = [
    read_outline,
    read_characters,
    read_chapter_outlines,
    read_relations,
    update_outline,
    update_character,
    create_character,
    update_chapter_outline,
    update_relations,
    generate_chapter_content,
    review_chapter,
    rewrite_chapter,
]
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(backend): refactor all tools to async, use services layer, add 5 new tools"
```

---

## Task 5: 后端 SSE — 并发控制 + tool_context + 生成结果事件

**Files:**
- Modify: `backend/app/api/agent.py`
- Modify: `backend/app/agents/sse_events.py`

关键设计：
- 并发控制：请求前获取 is_busy 锁，流结束后释放（使用独立 Session 避免请求级 Session 失效）
- tool_context：请求开始时 set，结束后 reset
- 生成类 tool 完成后通过 `on_tool_end` 事件的 result 传递预览信息
- 审核结果通过 `on_tool_end` 事件的 result 传递结构化审核数据

- [ ] **Step 1: sse_events.py 新增审核结果事件**

在 Agent SSE 事件区域末尾添加：

```python
def format_agent_review(review: dict) -> str:
    """格式化 Agent 审核结果事件（结构化数据，前端渲染为卡片）"""
    return f"event: agent_review\ndata: {json.dumps(review, ensure_ascii=False)}\n\n"

def format_agent_chapter_preview(preview: dict) -> str:
    """格式化 Agent 章节生成/重写预览事件"""
    return f"event: agent_chapter_preview\ndata: {json.dumps(preview, ensure_ascii=False)}\n\n"
```

- [ ] **Step 2: 重写 agent.py**

```python
# backend/app/api/agent.py
"""AI 搭档 Agent API 路由"""

import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.models.user import User
from app.models.project import Project
from app.agents.agent_graph import create_agent_graph, build_project_context
from app.agents.tool_context import set_tool_context, reset_tool_context
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_ai_update,
    format_agent_review,
    format_agent_chapter_preview,
    format_error_message,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

BUSY_TIMEOUT_SECONDS = 300  # 5 分钟超时自动释放


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    history: Optional[list[dict]] = None


def _acquire_busy_lock(db: Session, project_id: int, owner: str = "agent") -> bool:
    """尝试获取项目忙锁，返回是否成功"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    now = datetime.utcnow()
    if project.is_busy:
        if project.busy_since and (now - project.busy_since).total_seconds() > BUSY_TIMEOUT_SECONDS:
            logger.warning(f"Project {project_id} busy lock expired, preempting (was held by {project.busy_by})")
        else:
            return False
    project.is_busy = True
    project.busy_since = now
    project.busy_by = owner
    db.commit()
    return True


def _release_busy_lock(project_id: int):
    """释放项目忙锁（使用独立 Session）"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.busy_by == "agent":
            project.is_busy = False
            project.busy_since = None
            project.busy_by = None
            db.commit()
    except Exception as e:
        logger.error(f"Failed to release busy lock: {e}")
        db.rollback()
    finally:
        db.close()


async def stream_agent_events(graph, messages: list, project_id: int):
    """流式输出 Agent 事件"""
    write_tools = {
        "update_outline", "update_character", "create_character",
        "update_chapter_outline", "update_relations",
        "generate_chapter_content", "rewrite_chapter",
    }
    module_map = {
        "update_outline": "outline",
        "update_character": "characters",
        "create_character": "characters",
        "update_chapter_outline": "chapter_outlines",
        "update_relations": "relations",
        "generate_chapter_content": "writing",
        "rewrite_chapter": "writing",
    }

    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            # LLM 文本输出
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    yield format_agent_text(chunk.content)

            # Tool 调用开始
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                yield format_agent_tool_start(tool_name, tool_input)

            # Tool 调用结束
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})

                # 写操作发送 ai_update 通知
                if tool_name in write_tools:
                    module = module_map.get(tool_name, "unknown")
                    yield format_ai_update(module, f"{tool_name} 执行完成")

                # 序列化 tool output
                output_data = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                yield format_agent_tool_result(tool_name, {"output": output_data[:500]})

                # 生成类 tool：发送章节预览事件
                if tool_name in ("generate_chapter_content", "rewrite_chapter") and isinstance(tool_output, dict):
                    if tool_output.get("success"):
                        yield format_agent_chapter_preview({
                            "chapter_number": tool_output.get("chapter_number"),
                            "title": tool_output.get("title", ""),
                            "word_count": tool_output.get("word_count", 0),
                            "preview": tool_output.get("preview", ""),
                            "action": "generated" if tool_name == "generate_chapter_content" else "rewritten",
                        })

                # 审核 tool：发送审核结果事件
                if tool_name == "review_chapter" and isinstance(tool_output, dict):
                    if tool_output.get("success") and tool_output.get("review"):
                        yield format_agent_review(tool_output["review"])

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


@router.post("/{project_id}/agent/chat")
async def agent_chat(
    project_id: int,
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """与 AI 搭档对话（SSE 流式）"""
    project = get_project_for_user(project_id, current_user.id, db)

    # 并发控制：获取忙锁
    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    # 构建项目上下文
    context = build_project_context(project_id)

    # 构建 system message
    system_content = f"""你是一位专业的小说创作搭档。你可以帮助用户修改大纲、角色设定、章节大纲，也可以生成章节正文、审核章节、重写章节。

当前项目上下文：
- 大纲：{json.dumps(context.get('outline', {}), ensure_ascii=False)}
- 角色：{json.dumps(context.get('characters', []), ensure_ascii=False)}
- 章节大纲：{json.dumps(context.get('chapter_outlines', {}), ensure_ascii=False)}
- 用户当前查看：{req.active_tab or '未知'}{f' / {req.active_menu_item}' if req.active_menu_item else ''}

请根据用户的需求，调用相应的工具来修改项目内容或生成内容。修改后简要说明你做了什么。"""

    messages = [{"role": "system", "content": system_content}]
    if req.history:
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    # 创建 Agent 图
    try:
        graph = create_agent_graph(
            model_config_id=req.model_config_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        _release_busy_lock(project_id)
        raise HTTPException(status_code=400, detail=str(e))

    # 设置 tool 运行时上下文（contextvars）
    context_tokens = set_tool_context(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
    )

    async def _stream_with_cleanup():
        try:
            async for event in stream_agent_events(graph, messages, project_id):
                yield event
        finally:
            # 释放忙锁
            _release_busy_lock(project_id)
            # 重置 tool 上下文
            reset_tool_context(context_tokens)

    return StreamingResponse(
        _stream_with_cleanup(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/agent.py backend/app/agents/sse_events.py
git commit -m "feat(backend): add concurrency control, tool context, review/chapter-preview events"
```

---

## Task 6: 前端 — AiMessage segments + 新 SSE 事件处理

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`
- Modify: `frontend/src/lib/agentApi.ts`

- [ ] **Step 1: 更新 workbenchStore.ts**

替换 `AiMessage` 和 `AiAction` 接口，添加 `isAgentBusy`：

```typescript
/** AI 消息内容段 */
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview'
  content: string
  data?: Record<string, unknown>  // 结构化数据（审核结果、章节预览等）
}

/** AI 侧栏消息 */
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string  // 纯文本摘要
  segments: AiMessageSegment[]
  actions?: AiAction[]
  timestamp: number
}

/** AI 工具调用动作 */
export interface AiAction {
  tool: string
  status: 'running' | 'done' | 'error'
  description: string
  args?: Record<string, unknown>
  result?: Record<string, unknown>
}
```

在 `WorkbenchState` interface 中添加：

```typescript
  // Agent 并发控制
  isAgentBusy: boolean
  setIsAgentBusy: (busy: boolean) => void
```

在 `initialState` 中添加：

```typescript
  isAgentBusy: false as boolean,
```

在 store 实现中添加：

```typescript
  setIsAgentBusy: (busy) => set({ isAgentBusy: busy }),
```

更新 `addAiMessage`：

```typescript
  addAiMessage: (message) => set((state) => ({
    aiMessages: [...state.aiMessages, {
      ...message,
      segments: message.segments || [],
    }]
  })),
```

- [ ] **Step 2: 更新 agentApi.ts — 处理新事件**

```typescript
// frontend/src/lib/agentApi.ts

import { createSSEStream } from './sseParser'
import type { SSEData } from './sseParser'

/** Agent 聊天 SSE 回调 */
export interface AgentChatCallbacks {
  onAgentText?: (content: string) => void
  onToolStart?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, result: Record<string, unknown>) => void
  onAiUpdate?: (module: string, summary: string) => void
  onChapterPreview?: (data: Record<string, unknown>) => void
  onReview?: (data: Record<string, unknown>) => void
  onAgentDone?: () => void
  onError?: (error: string) => void
}

/** Agent 聊天请求选项 */
export interface AgentChatOptions {
  modelConfigId?: number
  activeTab?: string
  activeMenuItem?: string
  history?: Array<{ role: string; content: string }>
  signal?: AbortSignal
}

/**
 * 发送 Agent 聊天消息（SSE 流式）
 */
export async function sendAgentMessage(
  projectId: number,
  message: string,
  callbacks: AgentChatCallbacks,
  options?: AgentChatOptions
): Promise<void> {
  await createSSEStream(
    {
      url: `/api/projects/${projectId}/agent/chat`,
      method: 'POST',
      body: {
        message,
        model_config_id: options?.modelConfigId,
        active_tab: options?.activeTab,
        active_menu_item: options?.activeMenuItem,
        history: options?.history,
      },
      signal: options?.signal,
    },
    (type: string, data: SSEData) => {
      const payload = (typeof data === 'object' && data !== null) ? data as Record<string, unknown> : {}

      switch (type) {
        case 'agent_text':
          callbacks.onAgentText?.(String(payload.content || ''))
          break
        case 'agent_tool_start':
          callbacks.onToolStart?.(String(payload.tool || ''), (payload.args as Record<string, unknown>) || {})
          break
        case 'agent_tool_result':
          callbacks.onToolResult?.(String(payload.tool || ''), (payload.result as Record<string, unknown>) || {})
          break
        case 'ai_update':
          callbacks.onAiUpdate?.(String(payload.module || ''), String(payload.summary || ''))
          break
        case 'agent_chapter_preview':
          callbacks.onChapterPreview?.(payload)
          break
        case 'agent_review':
          callbacks.onReview?.(payload)
          break
        case 'agent_done':
          callbacks.onAgentDone?.()
          break
        case 'error':
          callbacks.onError?.(String(payload.error || payload.message || '请求失败'))
          break
      }
    },
    (error: string) => {
      callbacks.onError?.(error)
    }
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/stores/workbenchStore.ts frontend/src/lib/agentApi.ts
git commit -m "feat(frontend): add AiMessage segments, review/chapter-preview events, isAgentBusy"
```

---

## Task 7: 前端 — AICompanionSidebar 模型选择器 + segments 处理 + 并发

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionSidebar.tsx`

- [ ] **Step 1: 重写 AICompanionSidebar.tsx**

关键改动：
- 模型选择器下拉菜单（header 区域）
- segments 处理：agent_text 追加文本，chapter_preview / review 追加结构化 segment
- tool action 记录 args 和 result
- 传递 modelConfigId
- 并发控制：isAgentBusy + workflow 运行时禁用

```tsx
// frontend/src/components/workbench/AICompanionSidebar.tsx

import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { PanelRightClose, PanelRightOpen, ChevronDown } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'
import { sendAgentMessage } from '@/lib/agentApi'
import { modelConfigsApi } from '@/lib/api'
import type { ModelConfig } from '@/types'

export function AICompanionSidebar()
{
  const { id } = useParams()
  const projectId = parseInt(id || '0')
  const {
    aiSidebarOpen, toggleAiSidebar, addAiMessage,
    isAgentBusy, setIsAgentBusy,
  } = useWorkbenchStore()
  const workflowRunning = useWorkflowStore((s) => s.isRunning)
  const [sending, setSending] = useState(false)
  const [models, setModels] = useState<ModelConfig[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // 加载模型配置列表
  useEffect(() =>
  {
    modelConfigsApi.list().then((res) =>
    {
      const healthy = (res.configs || []).filter((c: ModelConfig) => c.is_healthy)
      setModels(healthy)
      if (healthy.length > 0 && !selectedModelId)
      {
        setSelectedModelId(healthy[0].id)
      }
    }).catch(() => {})
  }, [])

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-slate-950 border-l border-slate-800 flex flex-col items-center pt-3 gap-2">
        <button onClick={toggleAiSidebar} className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors" title="展开 AI 搭档">
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-slate-600 text-[10px]" style={{ writingMode: 'vertical-lr' }}>AI 搭档</span>
      </div>
    )
  }

  const disabled = sending || workflowRunning
  const disabledReason = workflowRunning
    ? '工作流运行中，Agent 暂不可用'
    : sending ? 'Agent 思考中...' : undefined

  const selectedModel = models.find((m) => m.id === selectedModelId)

  const handleSend = async (message: string) =>
  {
    // 添加用户消息
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      segments: [],
      timestamp: Date.now(),
    })

    // 创建 AI 消息占位
    const assistantId = crypto.randomUUID()
    addAiMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      segments: [],
      actions: [],
      timestamp: Date.now(),
    })

    setSending(true)
    setIsAgentBusy(true)
    const controller = new AbortController()
    abortRef.current = controller

    const { activeTab, activeMenuItem, aiMessages } = useWorkbenchStore.getState()

    // 构建历史消息
    const history = aiMessages
      .filter((m) => m.id !== assistantId)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }))

    try
    {
      await sendAgentMessage(projectId, message, {
        onAgentText: (content) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: m.content + content,
                    segments: [...m.segments, { type: 'agent_text' as const, content }],
                  }
                : m
            ),
          }))
        },
        onToolStart: (tool, args) =>
        {
          const desc = _toolDescription(tool, args)
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    actions: [...(m.actions || []), {
                      tool,
                      status: 'running' as const,
                      description: desc,
                      args,
                    }],
                  }
                : m
            ),
          }))
        },
        onToolResult: (tool, result) =>
        {
          useWorkbenchStore.setState((state) =>
          {
            const msg = state.aiMessages.find((m) => m.id === assistantId)
            if (!msg?.actions) return state
            const actionIdx = [...msg.actions].reverse().findIndex(
              (a) => a.tool === tool && a.status === 'running'
            )
            if (actionIdx === -1) return state
            const realIdx = msg.actions.length - 1 - actionIdx
            return {
              aiMessages: state.aiMessages.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      actions: m.actions?.map((a, i) =>
                        i === realIdx
                          ? { ...a, status: 'done' as const, result }
                          : a
                      ),
                    }
                  : m
              ),
            }
          })
        },
        onChapterPreview: (data) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    segments: [...m.segments, {
                      type: 'chapter_preview' as const,
                      content: String(data.preview || ''),
                      data,
                    }],
                  }
                : m
            ),
          }))
        },
        onReview: (data) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    segments: [...m.segments, {
                      type: 'review' as const,
                      content: JSON.stringify(data),
                      data,
                    }],
                  }
                : m
            ),
          }))
        },
        onAiUpdate: (module) =>
        {
          useWorkbenchStore.getState().addAiUpdateMarker(module)
          setTimeout(() =>
          {
            useWorkbenchStore.getState().clearAiUpdateMarker(module)
          }, 5 * 60 * 1000)
        },
        onAgentDone: () =>
        {
          setSending(false)
          setIsAgentBusy(false)
        },
        onError: (error) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content || `出错：${error}` } : m
            ),
          }))
          setSending(false)
          setIsAgentBusy(false)
        },
      }, {
        activeTab,
        activeMenuItem,
        history,
        modelConfigId: selectedModelId || undefined,
        signal: controller.signal,
      })
    }
    catch
    {
      setSending(false)
      setIsAgentBusy(false)
    }
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>

          {/* 模型选择器 */}
          <div className="relative">
            <button
              onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 px-1.5 py-0.5 rounded hover:bg-slate-800 transition-colors"
              title="选择模型"
            >
              <span className="max-w-[80px] truncate">{selectedModel?.name || '默认'}</span>
              <ChevronDown className="h-3 w-3" />
            </button>
            {modelDropdownOpen && models.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-slate-800 border border-slate-700 rounded-md shadow-lg z-50 py-1 max-h-48 overflow-auto">
                {models.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { setSelectedModelId(m.id); setModelDropdownOpen(false) }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-700 transition-colors ${
                      m.id === selectedModelId ? 'text-emerald-400' : 'text-slate-300'
                    }`}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <button onClick={toggleAiSidebar} className="p-1 text-slate-500 hover:text-slate-300 transition-colors" title="折叠 AI 搭档">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* 聊天区 */}
      <AICompanionChat />

      {/* 输入区 */}
      <AICompanionInput onSend={handleSend} disabled={disabled} disabledReason={disabledReason} />
    </div>
  )
}

/** 生成 tool 操作的可读描述 */
function _toolDescription(tool: string, args: Record<string, unknown>): string
{
  const map: Record<string, (args: Record<string, unknown>) => string> = {
    read_outline: () => '读取大纲',
    update_outline: () => '修改大纲',
    read_characters: () => '读取角色',
    update_character: (a) => `修改角色「${a.name || ''}」`,
    create_character: (a) => `新增角色「${a.name || ''}」`,
    read_chapter_outlines: () => '读取章节大纲',
    update_chapter_outline: () => '修改章节大纲',
    read_relations: () => '读取人物关系',
    update_relations: () => '修改人物关系',
    generate_chapter_content: (a) => `生成第${a.chapter_number || '?'}章正文`,
    review_chapter: (a) => `审核第${a.chapter_number || '?'}章`,
    rewrite_chapter: (a) => `重写第${a.chapter_number || '?'}章`,
  }
  return (map[tool] || (() => tool))(args)
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/workbench/AICompanionSidebar.tsx
git commit -m "feat(frontend): add model selector, concurrency control, segments handling"
```

---

## Task 8: 前端 — AICompanionChat segments 混合内容渲染 + AIActionCard 可展开

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionChat.tsx`
- Modify: `frontend/src/components/workbench/AIActionCard.tsx`

- [ ] **Step 1: 重写 AICompanionChat.tsx**

```tsx
// frontend/src/components/workbench/AICompanionChat.tsx

import { useEffect, useRef, useState } from 'react'
import { useWorkbenchStore, type AiMessage } from '@/stores/workbenchStore'
import { AIActionCard } from './AIActionCard'

/** 渲染 segments 混合内容 */
function MessageContent({ message }: { message: AiMessage })
{
  // 兼容无 segments 的旧消息
  if (!message.segments || message.segments.length === 0)
  {
    return <span className="whitespace-pre-wrap">{message.content}</span>
  }

  // 合并相邻的 agent_text segments
  const merged: Array<{ type: string; content: string; data?: Record<string, unknown> }> = []
  for (const seg of message.segments)
  {
    const last = merged[merged.length - 1]
    if (last && last.type === 'agent_text' && seg.type === 'agent_text')
    {
      last.content += seg.content
    }
    else
    {
      merged.push({ type: seg.type, content: seg.content, data: seg.data })
    }
  }

  return (
    <>
      {merged.map((seg, i) =>
      {
        if (seg.type === 'agent_text')
        {
          return <span key={i} className="whitespace-pre-wrap">{seg.content}</span>
        }

        if (seg.type === 'chapter_preview')
        {
          return <ChapterPreviewCard key={i} data={seg.data || {}} />
        }

        if (seg.type === 'review')
        {
          return <ReviewResultCard key={i} data={seg.data || {}} />
        }

        // fallback
        return <span key={i} className="whitespace-pre-wrap">{seg.content}</span>
      })}
    </>
  )
}

/** 章节生成/重写预览卡片 */
function ChapterPreviewCard({ data }: { data: Record<string, unknown> })
{
  const [expanded, setExpanded] = useState(false)
  const preview = String(data.preview || '')
  const title = String(data.title || '')
  const wordCount = Number(data.word_count || 0)
  const action = String(data.action || 'generated')
  const actionLabel = action === 'rewritten' ? '已重写' : '已生成'

  return (
    <div className="my-1.5 rounded bg-slate-800/60 border border-emerald-700/30 px-2.5 py-2">
      <div className="text-[10px] text-emerald-400/80 mb-1">
        📝 {title} · {actionLabel} · {wordCount}字
      </div>
      {preview && (
        <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
          {expanded ? preview : preview.slice(0, 150)}
          {preview.length > 150 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-1 text-slate-500 hover:text-slate-300"
            >
              {expanded ? '收起' : '...展开'}
            </button>
          )}
        </div>
      )}
      <div className="text-[10px] text-slate-500 mt-1">
        完整内容可在「写作」标签页查看
      </div>
    </div>
  )
}

/** 审核结果卡片 */
function ReviewResultCard({ data }: { data: Record<string, unknown> })
{
  const review = data as {
    passed?: boolean
    scores?: Record<string, number>
    issues?: Array<{ type: string; location: string; description: string }>
    suggestions?: string
  }

  const passed = review.passed !== false
  const scores = review.scores || {}
  const issues = review.issues || []

  return (
    <div className={`my-1.5 rounded border px-2.5 py-2 ${
      passed
        ? 'bg-green-900/20 border-green-700/30'
        : 'bg-red-900/20 border-red-700/30'
    }`}>
      <div className={`text-[10px] font-medium mb-1 ${
        passed ? 'text-green-400' : 'text-red-400'
      }`}>
        {passed ? '✓ 审核通过' : '✗ 审核未通过'}
      </div>

      {Object.keys(scores).length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mb-1">
          {Object.entries(scores).map(([key, val]) => (
            <span key={key} className="text-[10px] text-slate-400">
              {key}: <span className={val >= 7 ? 'text-green-400' : val >= 5 ? 'text-amber-400' : 'text-red-400'}>{val}</span>
            </span>
          ))}
        </div>
      )}

      {issues.length > 0 && (
        <div className="space-y-0.5 mb-1">
          {issues.map((issue, i) => (
            <div key={i} className="text-[10px] text-slate-400">
              <span className="text-amber-400">[{issue.type}]</span> {issue.location}: {issue.description}
            </div>
          ))}
        </div>
      )}

      {review.suggestions && (
        <div className="text-[10px] text-slate-400 italic">{review.suggestions}</div>
      )}
    </div>
  )
}

export function AICompanionChat()
{
  const messages = useWorkbenchStore((s) => s.aiMessages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() =>
  {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-auto p-3 space-y-3">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
          <div className="text-2xl">🤖</div>
          <p className="text-xs text-slate-500 leading-relaxed">
            我是你的 AI 编剧搭档<br />
            跟我说说你对小说的想法<br />
            我会帮你修改大纲、角色、章节...
          </p>
        </div>
      )}
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
              msg.role === 'user'
                ? 'bg-blue-900/50 text-blue-200'
                : 'bg-emerald-900/40 text-emerald-200'
            }`}
          >
            <MessageContent message={msg} />
            {msg.actions && msg.actions.length > 0 && <AIActionCard actions={msg.actions} />}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
```

- [ ] **Step 2: 重写 AIActionCard.tsx**

```tsx
// frontend/src/components/workbench/AIActionCard.tsx

import { useState } from 'react'
import { Check, Loader2, X, ChevronDown, ChevronRight } from 'lucide-react'
import type { AiAction } from '@/stores/workbenchStore'

interface AIActionCardProps
{
  actions: AiAction[]
}

export function AIActionCard({ actions }: AIActionCardProps)
{
  if (actions.length === 0) return null

  return (
    <div className="space-y-1.5 my-2">
      {actions.map((action, i) => (
        <ActionItem key={i} action={action} />
      ))}
    </div>
  )
}

function ActionItem({ action }: { action: AiAction })
{
  const [expanded, setExpanded] = useState(false)
  const hasDetails = action.args || action.result

  return (
    <div className="rounded bg-slate-800/40 border border-slate-700/30">
      <button
        onClick={() => hasDetails && setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs w-full text-left px-2 py-1.5 hover:bg-slate-700/30 transition-colors"
      >
        {action.status === 'done' && <Check className="h-3 w-3 text-green-400 shrink-0" />}
        {action.status === 'running' && <Loader2 className="h-3 w-3 text-blue-400 animate-spin shrink-0" />}
        {action.status === 'error' && <X className="h-3 w-3 text-red-400 shrink-0" />}
        <span className={action.status === 'running' ? 'text-blue-300' : 'text-slate-400'}>
          {action.description}
        </span>
        {hasDetails && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-slate-500 ml-auto shrink-0" />
            : <ChevronRight className="h-3 w-3 text-slate-500 ml-auto shrink-0" />
        )}
      </button>
      {expanded && hasDetails && (
        <div className="px-2 pb-2 space-y-1.5 border-t border-slate-700/30">
          {action.args && (
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">输入参数</div>
              <pre className="text-[10px] text-slate-400 bg-slate-900/50 rounded px-2 py-1 overflow-auto max-h-32">
                {JSON.stringify(action.args, null, 2)}
              </pre>
            </div>
          )}
          {action.result && (
            <div>
              <div className="text-[10px] text-slate-500 mb-0.5">执行结果</div>
              <pre className="text-[10px] text-slate-400 bg-slate-900/50 rounded px-2 py-1 overflow-auto max-h-32">
                {JSON.stringify(action.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/AICompanionChat.tsx frontend/src/components/workbench/AIActionCard.tsx
git commit -m "feat(frontend): mixed content rendering with chapter preview and review cards, expandable tool actions"
```

---

## Task 9: 前端 — AICompanionInput 支持 disabledReason

**Files:**
- Modify: `frontend/src/components/workbench/AICompanionInput.tsx`

- [ ] **Step 1: 更新 AICompanionInput**

读取现有文件，添加 `disabledReason` prop。在输入框上方显示禁用原因提示。

```tsx
// 修改 props 接口
interface AICompanionInputProps
{
  onSend: (message: string) => void
  disabled: boolean
  disabledReason?: string
}

// 在输入区域上方添加提示
{disabled && disabledReason && (
  <div className="text-[10px] text-amber-400/80 mb-1.5 text-center">{disabledReason}</div>
)}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/workbench/AICompanionInput.tsx
git commit -m "feat(frontend): add disabledReason display to AICompanionInput"
```

---

## Task 10: 集成验证

- [ ] **Step 1: 重启服务**

```bash
docker compose build --no-cache backend && docker compose up -d backend
docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 2: 运行后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 3: 手动验证功能清单**

1. AI 侧栏模型选择器：下拉框选模型 → 发消息 → 后端用选定模型
2. `read_relations` / `update_relations`：读取/修改人物关系
3. `generate_chapter_content`：发"帮我写第1章" → tool 运行中显示 spinner → 完成后显示预览卡片
4. `review_chapter`：发"审核第1章" → 显示审核结果卡片（分数+问题+建议）
5. `rewrite_chapter`：发"根据审核意见重写第1章" → 显示重写预览卡片
6. Tool 可展开详情：点击 tool 操作行 → 展开显示参数和结果 JSON
7. 并发控制：Agent 运行中再发消息 → 409 错误
8. Context 自动刷新：左侧修改大纲 → 发"读取大纲" → Agent 返回最新数据
9. Workflow 运行时 → Agent 输入框禁用，显示提示

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: complete agent evolution and workbench integration v2

- Add 5 new async agent tools with contextvars-based request scoping
- Add async shared services layer (outline, chapter, character, relation)
- Add concurrency control (is_busy lock with 5min timeout)
- Add model selector dropdown in AI sidebar
- Add chapter preview and review result cards in chat
- Add expandable tool action cards with args/result details
- Add workflow/agent mutual exclusion in UI"
```
