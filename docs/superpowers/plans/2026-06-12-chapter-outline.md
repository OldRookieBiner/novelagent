# 章节大纲功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 ChapterOutline 在写作流程中活起来——先规划、再审查、再动笔，提升章节写作质量。

**Architecture:** 新增 `generate_chapter_outline` 工具实现规划环节，修改 `generate_chapter_content` 在写正文前检查大纲确认状态，通过 `agent_context.py` 将大纲注入 Agent system prompt 让 LLM 参考大纲写作，前端在 WritingPanel 正文上方增加可折叠大纲面板实现审查环节，通过 `knowledgeVersion` 机制实现前端自动刷新。

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic（后端），React/shadcn/ui/Zustand（前端），LangChain tools（Agent 工具）

---

## File Structure

| 操作 | 文件 | 职责 |
|------|------|------|
| Create | `backend/app/agents/tools/creation/generate_chapter_outline.py` | 新工具：生成/更新章节大纲 |
| Modify | `backend/app/models/outline.py` | ChapterOutline 加 4 列 |
| Modify | `backend/app/schemas/chapter.py` | schema 加 4 字段 |
| Modify | `backend/app/agents/tools/creation/__init__.py` | 导出新工具 |
| Modify | `backend/app/agents/tools/registry.py` | 注册到 STRUCTURE/WRITING_TOOLS |
| Modify | `backend/app/agents/tools/creation/generate_chapter_content.py` | 写正文前检查 confirmed 状态 |
| Modify | `backend/app/agents/agent_context.py` | writing phase 加载 current_chapter_outline |
| Modify | `backend/app/agents/services/outline_service.py` | read/update_chapter_outline 加新字段 |
| Modify | `backend/app/api/chapters.py` | update/confirm 端点支持新字段 |
| Modify | `backend/app/agents/tools/creation/review_chapter.py` | chapter_outline_dict 加 4 字段 |
| Modify | `backend/app/agents/tools/creation/rewrite_chapter.py` | chapter_outline_dict 加 4 字段 |
| Modify | `backend/app/agents/review_utils.py` | _format_chapter_outline_str 加新字段 |
| Modify | `backend/app/agents/rewrite_utils.py` | _format_chapter_outline_str 加新字段 |
| Modify | `backend/app/agents/tools/utils.py` | _build_state_for_review 加新字段 |
| Modify | `frontend/src/types/index.ts` | ChapterOutline 类型加 4 字段 |
| Modify | `frontend/src/components/workbench/creation/WritingPanel.tsx` | 加大纲面板 + 编辑 + 状态标识 + 前置检查 + knowledgeVersion |
| Delete | `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 死代码 |
| Delete | `frontend/src/components/workbench/creation/ChapterOutlineEditor.tsx` | 死代码 |
| Delete | `frontend/src/components/workbench/creation/ChapterOutlineCard.tsx` | 死代码 |
| Delete | `frontend/src/components/workbench/creation/ChapterOutlineFlatList.tsx` | 死代码 |
| Delete | `frontend/src/components/workbench/creation/ChapterOutlineTreeView.tsx` | 死代码 |

---

### Task 1: 数据模型 — ChapterOutline 新增 4 列

**Files:**
- Modify: `backend/app/models/outline.py`
- Modify: `backend/app/schemas/chapter.py`
- Modify: `backend/app/agents/services/outline_service.py`
- Modify: `backend/app/api/chapters.py`

- [ ] **Step 1: ChapterOutline 模型加 4 列**

在 `backend/app/models/outline.py` 的 `ChapterOutline` 类中，`ending` 字段之后、`target_words` 之前，添加：

```python
    opening_state = Column(Text, nullable=True)  # 开场状态
    emotional_arc = Column(Text, nullable=True)  # 情绪弧线
    key_scenes = Column(JSON, nullable=True)  # 核心场景列表
    pacing_note = Column(Text, nullable=True)  # 节奏标注
```

注意：`key_scenes` 用 `nullable=True` 而非 `default=list`，避免 SQLAlchemy 可变默认值陷阱。写入时由应用层设置空列表 `[]`，数据库层 NULL 表示未设置。

- [ ] **Step 2: Schema 加 4 字段**

在 `backend/app/schemas/chapter.py` 中：

`ChapterOutlineBase` 添加：
```python
    opening_state: Optional[str] = None
    emotional_arc: Optional[str] = None
    key_scenes: Optional[list[dict]] = None
    pacing_note: Optional[str] = None
```

`ChapterOutlineUpdate` 添加：
```python
    opening_state: Optional[str] = None
    emotional_arc: Optional[str] = None
    key_scenes: Optional[list[dict]] = None
    pacing_note: Optional[str] = None
```

注意：`ChapterOutlineResponse` 继承自 `ChapterOutlineBase`，会自动继承这 4 个字段，无需额外修改。但 `chapters.py` 三个端点手动构造 kwargs 时必须包含这 4 个字段。

- [ ] **Step 3: outline_service 加新字段**

在 `backend/app/agents/services/outline_service.py` 的 `read_chapter_outlines` 返回字典中添加：
```python
            "opening_state": o.opening_state,
            "emotional_arc": o.emotional_arc,
            "key_scenes": o.key_scenes,
            "pacing_note": o.pacing_note,
```

在 `update_chapter_outline` 的 `field_labels` 字典中添加：
```python
        "opening_state": "开场状态",
        "emotional_arc": "情绪弧线",
        "key_scenes": "核心场景",
        "pacing_note": "节奏标注",
```

- [ ] **Step 4: chapters API 支持新字段**

在 `backend/app/api/chapters.py` 的 `update_chapter_outline` 函数中，在 `if request.target_words is not None:` 之后添加：
```python
    if request.opening_state is not None:
        chapter_outline.opening_state = request.opening_state
    if request.emotional_arc is not None:
        chapter_outline.emotional_arc = request.emotional_arc
    if request.key_scenes is not None:
        chapter_outline.key_scenes = request.key_scenes
    if request.pacing_note is not None:
        chapter_outline.pacing_note = request.pacing_note
```

**关键**：`list_chapter_outlines`、`update_chapter_outline`、`confirm_chapter_outline` 三个函数的响应构造字典（kwargs）中都必须添加这 4 个字段。因为三个端点都是手动构造 `ChapterOutlineResponse` 的 kwargs，不使用 `from_orm`，遗漏字段会导致前端拿到的值为 None。

```python
        "opening_state": co.opening_state,
        "emotional_arc": co.emotional_arc,
        "key_scenes": co.key_scenes,
        "pacing_note": co.pacing_note,
```

注意 `confirm_chapter_outline` 中变量名是 `chapter_outline` 而非 `co`：
```python
        "opening_state": chapter_outline.opening_state,
        "emotional_arc": chapter_outline.emotional_arc,
        "key_scenes": chapter_outline.key_scenes,
        "pacing_note": chapter_outline.pacing_note,
```

- [ ] **Step 5: 创建 Alembic 迁移**

```bash
docker exec novelagent-backend-1 alembic revision -m "add_chapter_outline_writing_guidance_fields"
```

编辑生成的迁移文件，upgrade 添加：
```python
    op.add_column('chapter_outlines', sa.Column('opening_state', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('emotional_arc', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('key_scenes', sa.JSON(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('pacing_note', sa.Text(), nullable=True))
```

downgrade 添加：
```python
    op.drop_column('chapter_outlines', 'pacing_note')
    op.drop_column('chapter_outlines', 'key_scenes')
    op.drop_column('chapter_outlines', 'emotional_arc')
    op.drop_column('chapter_outlines', 'opening_state')
```

- [ ] **Step 6: 执行迁移并重启后端**

```bash
docker exec novelagent-backend-1 alembic upgrade head
docker compose restart backend
```

- [ ] **Step 7: 验证 API**

```bash
curl -s http://localhost:8000/api/projects/1/chapter-outlines | python3 -m json.tool | head -20
```

预期：返回的章节大纲数据包含 `opening_state`、`emotional_arc`、`key_scenes`、`pacing_note` 字段。

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/outline.py backend/app/schemas/chapter.py backend/app/agents/services/outline_service.py backend/app/api/chapters.py backend/alembic/versions/
git commit -m "feat(db): ChapterOutline 新增开场状态/情绪弧线/核心场景/节奏标注字段"
```

---

### Task 2: Agent 工具 — generate_chapter_outline

**Files:**
- Create: `backend/app/agents/tools/creation/generate_chapter_outline.py`
- Modify: `backend/app/agents/tools/creation/__init__.py`
- Modify: `backend/app/agents/tools/registry.py`

- [ ] **Step 1: 创建 generate_chapter_outline 工具**

创建 `backend/app/agents/tools/creation/generate_chapter_outline.py`：

```python
"""生成章节大纲工具"""

import json as _json
import logging

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id

logger = logging.getLogger(__name__)


@tool
async def generate_chapter_outline(
    chapter_number: int,
    title: str,
    scene: str = "",
    characters: str = "",
    plot: str = "",
    conflict: str = "",
    turning_point: str = "",
    hook: str = "",
    transition: str = "",
    ending: str = "",
    target_words: int = 3000,
    opening_state: str = "",
    emotional_arc: str = "",
    key_scenes: str = "[]",
    pacing_note: str = "",
) -> dict:
    """Generate or update the outline for a specific chapter.

    Use this when the user asks to plan or outline a specific chapter BEFORE writing it.
    This creates a detailed writing blueprint that will be referenced during chapter writing.

    Args:
        chapter_number: Chapter number (e.g., 1)
        title: Chapter title (e.g., "暗潮涌动")
        scene: Scene setting (e.g., "皇宫大殿·深夜")
        characters: Characters appearing in this chapter (e.g., "李承泽, 苏婉清")
        plot: Key plot points of this chapter
        conflict: Main conflict in this chapter
        turning_point: Turning point in this chapter
        hook: Suspense hook at chapter end
        transition: Transition/bridge to next chapter
        ending: Chapter ending description
        target_words: Target word count (default 3000)
        opening_state: State at chapter opening — character/situation status, links to previous chapter
        emotional_arc: Emotional trajectory (e.g., "压抑→紧张→爆发→余波")
        key_scenes: JSON string list of key scenes, each: {"seq": 1, "desc": "场景描述", "mood": "情绪"}
        pacing_note: Pacing instruction (e.g., "前慢后快，2/3处转折")
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline

    try:
        scenes = _json.loads(key_scenes) if isinstance(key_scenes, str) else key_scenes
    except _json.JSONDecodeError:
        logger.warning("key_scenes JSON 解析失败，使用空列表: %s", key_scenes[:100])
        scenes = []

    project_id = get_project_id()
    db = SessionLocal()
    committed = False

    try:
        chapter_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()

        if chapter_outline:
            # 更新现有大纲（即使已确认也允许更新，但重置确认状态）
            chapter_outline.title = title
            if scene:
                chapter_outline.scene = scene
            if characters:
                chapter_outline.characters = characters
            if plot:
                chapter_outline.plot = plot
            if conflict:
                chapter_outline.conflict = conflict
            if turning_point:
                chapter_outline.turning_point = turning_point
            if hook:
                chapter_outline.hook = hook
            if transition:
                chapter_outline.transition = transition
            if ending:
                chapter_outline.ending = ending
            chapter_outline.target_words = target_words
            if opening_state:
                chapter_outline.opening_state = opening_state
            if emotional_arc:
                chapter_outline.emotional_arc = emotional_arc
            if scenes:
                chapter_outline.key_scenes = scenes
            if pacing_note:
                chapter_outline.pacing_note = pacing_note
            # 重置确认状态，要求用户重新审查
            chapter_outline.confirmed = False
            action = "updated"
        else:
            # 创建新大纲
            chapter_outline = ChapterOutline(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                scene=scene or None,
                characters=characters or None,
                plot=plot or None,
                conflict=conflict or None,
                turning_point=turning_point or None,
                hook=hook or None,
                transition=transition or None,
                ending=ending or None,
                target_words=target_words,
                opening_state=opening_state or None,
                emotional_arc=emotional_arc or None,
                key_scenes=scenes if scenes else None,
                pacing_note=pacing_note or None,
                confirmed=False,
            )
            db.add(chapter_outline)
            action = "created"

        db.commit()
        committed = True

        return {
            "action": action,
            "chapter_number": chapter_number,
            "title": title,
            "confirmed": False,
            "message": f"第{chapter_number}章「{title}」大纲已{action}，请审查后确认",
        }

    except Exception as e:
        logger.error("generate_chapter_outline 失败: %s", e, exc_info=True)
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass
```

字段更新策略说明：更新时使用 `if value:` 判断非空才写入，空字符串参数表示"未提供"而非"清空"。这是有意设计——Agent 生成大纲时不会主动清空已有字段。创建时空字符串转为 `None` 存入数据库。

- [ ] **Step 2: 在 __init__.py 中导出**

在 `backend/app/agents/tools/creation/__init__.py` 添加：
```python
from .generate_chapter_outline import generate_chapter_outline
```

- [ ] **Step 3: 在 registry.py 中注册**

在 `backend/app/agents/tools/registry.py` 的导入区添加：
```python
from app.agents.tools.creation import (
    # ...existing imports...
    generate_chapter_outline,
)
```

在 `STRUCTURE_TOOLS` 列表中 `generate_outline` 之后添加：
```python
    generate_chapter_outline,
```

在 `WRITING_TOOLS` 列表中 `generate_chapter_content` 之前添加：
```python
    generate_chapter_outline,
```

验证递进关系：INCUBATION_TOOLS 不含此工具（正确——孵化阶段不需要规划单章），STRUCTURE_TOOLS ⊂ WRITING_TOOLS 成立。

- [ ] **Step 4: 重启后端验证工具注册**

```bash
docker compose restart backend
```

检查日志确认无导入错误：
```bash
docker compose logs backend --tail 20
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/tools/creation/generate_chapter_outline.py backend/app/agents/tools/creation/__init__.py backend/app/agents/tools/registry.py
git commit -m "feat(agent): 新增 generate_chapter_outline 工具"
```

---

### Task 3: Agent 上下文 — writing phase 加载当前章节大纲

**Files:**
- Modify: `backend/app/agents/agent_context.py`

这是大纲信息注入 Agent system prompt 的关键路径。`generate_chapter_content` 是 LangChain tool，它不构建 LLM messages——LLM 在决定调用工具时参考的是 Agent 的 system prompt。大纲信息必须通过 `agent_context.py` 注入 context dict，才能出现在 system prompt 中。

- [ ] **Step 1: 在 _load_writing_context 中加载 current_chapter_outline**

在 `backend/app/agents/agent_context.py` 的 `_load_writing_context` 函数中，在 `# 上一章结尾 500 字` 注释之前添加：

```python
    # 当前章节大纲（让 Agent 写正文时参考规划）
    if current_chapter_number:
        from app.database import SessionLocal as _SL
        from app.models.outline import ChapterOutline as _CO
        _db = _SL()
        try:
            _co = _db.query(_CO).filter(
                _CO.project_id == kb.project_id,
                _CO.chapter_number == current_chapter_number,
            ).first()
            if _co:
                co_data = {
                    "chapter_number": _co.chapter_number,
                    "title": _co.title or "",
                    "scene": _co.scene or "",
                    "characters": _co.characters or "",
                    "plot": _co.plot or "",
                    "conflict": _co.conflict or "",
                    "turning_point": _co.turning_point or "",
                    "hook": _co.hook or "",
                    "transition": _co.transition or "",
                    "ending": _co.ending or "",
                    "target_words": _co.target_words,
                    "opening_state": getattr(_co, "opening_state", None) or "",
                    "emotional_arc": getattr(_co, "emotional_arc", None) or "",
                    "key_scenes": getattr(_co, "key_scenes", None) or [],
                    "pacing_note": getattr(_co, "pacing_note", None) or "",
                    "confirmed": _co.confirmed,
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                co_tokens = estimate_tokens(co_json)
                if budget.can_add(co_tokens):
                    context["current_chapter_outline"] = co_data
                    budget.add(co_tokens)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("加载当前章节大纲失败: %s", e)
        finally:
            try:
                _db.close()
            except Exception:
                pass
```

注意：新字段使用 `getattr(_co, "field", None)` 读取，防御迁移未执行时新列不存在的情况。异常时记录 warning 日志而非静默吞没。

- [ ] **Step 2: 重启后端**

```bash
docker compose restart backend
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/agent_context.py
git commit -m "feat(agent): writing phase 加载当前章节大纲到上下文"
```

---

### Task 4: generate_chapter_content — 写正文前检查 confirmed 状态

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_chapter_content.py`

注意：大纲信息通过 `agent_context.py` 注入 Agent system prompt，`generate_chapter_content` 本身不需要注入大纲到 messages。此工具只需做 confirmed 状态检查。

- [ ] **Step 1: 修改 generate_chapter_content，写正文前检查 confirmed 状态**

在 `backend/app/agents/tools/creation/generate_chapter_content.py` 中，在 `project_id = get_project_id()` 之后、`kb = _kb()` 之前插入：

```python
    # 检查当前章是否有已确认的大纲
    _check_db = SessionLocal()
    try:
        _existing_co = _check_db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if _existing_co and not _existing_co.confirmed:
            return {
                "error": f"第{chapter_number}章大纲尚未确认，请先审查并确认章节大纲后再写作",
                "hint": "使用 generate_chapter_outline 工具生成大纲，或提醒用户确认大纲",
            }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("大纲确认状态检查失败: %s", e)
    finally:
        try:
            _check_db.close()
        except Exception:
            pass
```

关键行为：
- `_existing_co` 存在且 confirmed=False → 返回错误，要求先确认
- `_existing_co` 存在且 confirmed=True → 通过检查，继续后续流程（大纲已通过 system prompt 注入）
- `_existing_co` 不存在 → 不拦截，保留向后兼容（工具会自动创建空壳 ChapterOutline）

注意：`_check_db` 使用独立 session，先关闭后再进入主流程的 `db = SessionLocal()`。检查异常时记录 warning 日志而非静默吞没，但检查失败不阻断后续流程。

- [ ] **Step 2: 重启后端**

```bash
docker compose restart backend
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/tools/creation/generate_chapter_content.py
git commit -m "feat(agent): generate_chapter_content 写正文前检查已确认大纲"
```

---

### Task 5: 审核和重写上下文 — chapter_outline_dict 加新字段

**Files:**
- Modify: `backend/app/agents/tools/creation/review_chapter.py`
- Modify: `backend/app/agents/tools/creation/rewrite_chapter.py`
- Modify: `backend/app/agents/review_utils.py`
- Modify: `backend/app/agents/rewrite_utils.py`
- Modify: `backend/app/agents/tools/utils.py`

- [ ] **Step 1: review_chapter.py 的 chapter_outline_dict 加 4 字段**

在 `backend/app/agents/tools/creation/review_chapter.py` 中，`chapter_outline_dict` 字典的 `"target_words": co.target_words,` 之后添加：

```python
            "opening_state": getattr(co, "opening_state", None),
            "emotional_arc": getattr(co, "emotional_arc", None),
            "key_scenes": getattr(co, "key_scenes", None),
            "pacing_note": getattr(co, "pacing_note", None),
```

使用 `getattr` 带默认值，防御迁移未执行时新列不存在的情况。

- [ ] **Step 2: rewrite_chapter.py 的 chapter_outline_dict 加 4 字段**

在 `backend/app/agents/tools/creation/rewrite_chapter.py` 中，找到 `chapter_outline_dict` 字典，在 `"target_words": co.target_words,` 之后添加同样的 4 个字段（同样用 `getattr`）。

- [ ] **Step 3: review_utils.py 的 _format_chapter_outline_str 加新字段**

在 `backend/app/agents/review_utils.py` 的 `_format_chapter_outline_str` 函数中，在 `for field, label in [...]` 循环的字段列表末尾添加：

```python
                         ("opening_state", "开场状态"), ("emotional_arc", "情绪弧线"), ("pacing_note", "节奏标注"),
```

并在循环之后、`return` 之前添加 key_scenes 的格式化：

```python
    scenes = chapter_outline.get("key_scenes")
    if scenes and isinstance(scenes, list):
        for s in scenes:
            seq = s.get("seq", "")
            desc = s.get("desc", "")
            mood = s.get("mood", "")
            parts.append(f"  场景{seq}：{desc}（{mood}）")
```

- [ ] **Step 4: rewrite_utils.py 的 _format_chapter_outline_str 加新字段**

在 `backend/app/agents/rewrite_utils.py` 的 `_format_chapter_outline_str` 函数中，做与 Step 3 完全相同的修改。

- [ ] **Step 5: _build_state_for_review 的 chapter_outlines 加新字段**

在 `backend/app/agents/tools/utils.py` 的 `_build_state_for_review` 函数中，`chapter_outlines` 列表里每项字典的 `"target_words": co.target_words,` 之后添加：

```python
                "opening_state": getattr(co, "opening_state", None),
                "emotional_arc": getattr(co, "emotional_arc", None),
                "key_scenes": getattr(co, "key_scenes", None),
                "pacing_note": getattr(co, "pacing_note", None),
```

- [ ] **Step 6: 重启后端**

```bash
docker compose restart backend
```

- [ ] **Step 7: 提交**

```bash
git add backend/app/agents/tools/creation/review_chapter.py backend/app/agents/tools/creation/rewrite_chapter.py backend/app/agents/review_utils.py backend/app/agents/rewrite_utils.py backend/app/agents/tools/utils.py
git commit -m "feat(agent): 审核/重写上下文同步包含章节大纲新字段"
```

---

### Task 6: 前端类型 — 新增 4 字段

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: ChapterOutline 类型加 4 字段**

在 `frontend/src/types/index.ts` 的 `ChapterOutline` 接口中，`target_words` 之后、`confirmed` 之前添加：
```typescript
  opening_state?: string;
  emotional_arc?: string;
  key_scenes?: { seq: number; desc: string; mood: string }[];
  pacing_note?: string;
```

在 `ChapterOutlineUpdate` 接口中添加：
```typescript
  opening_state?: string;
  emotional_arc?: string;
  key_scenes?: { seq: number; desc: string; mood: string }[];
  pacing_note?: string;
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): ChapterOutline 类型新增写作指导字段"
```

---

### Task 7: 前端 — WritingPanel 大纲面板

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: WritingPanel 订阅 knowledgeVersion 自动刷新**

在 `frontend/src/components/workbench/creation/WritingPanel.tsx` 中，使用选择器方式订阅 `knowledgeVersion`（与 KnowledgeTab/StructureTab/TrackingTab 一致，避免解构导致不必要的重渲染）：

```typescript
  const knowledgeVersion = useWorkbenchStore((s) => s.knowledgeVersion)
  const { toggleAiSidebar } = useWorkbenchStore()
```

在章节大纲列表的 `useEffect` 依赖数组中加入 `knowledgeVersion`：

```typescript
  }, [projectId, knowledgeVersion])
```

这样当 Agent 对话完成（`onAgentDone` → `incrementKnowledgeVersion()`）后，章节列表自动刷新。

- [ ] **Step 2: WritingPanel 增加可折叠大纲面板**

在组件顶部新增状态：
```typescript
  const [outlineCollapsed, setOutlineCollapsed] = useState(false)
```

在正文编辑区域（`<div className="max-w-3xl mx-auto">` 内，标题栏之后、TipTapEditor/预览区之前）插入大纲面板。

大纲面板结构：
1. **头部**：可点击折叠/展开 + 状态标签（"待确认"/"已确认"）+ 当前章标题
2. **基础规划区域**（8 字段）：scene、characters、plot、conflict、turning_point、hook、transition、ending — 每个字段一行，点击变输入框，失焦调用 `chapterOutlinesApi.update`
3. **写作指导区域**（4 字段）：opening_state、emotional_arc、key_scenes（列表形式）、pacing_note — 同样 inline 可编辑
4. **底部按钮**：确认大纲（调用 `chapterOutlinesApi.confirm`，成功后刷新章节列表）、重新规划（调用 `handleReplan`）

样式规则：
- 未确认大纲：默认展开，虚线边框 `border-dashed`，amber 色"待确认"标签
- 已确认大纲：默认折叠，实线边框 `border-solid`，蓝色"已确认"标签
- 无大纲：显示空状态提示

key_scenes 编辑说明：使用简化的列表编辑——每个场景一行，显示"场景N: 描述（情绪）"，点击弹出简单编辑表单。避免复杂的嵌套 JSON 编辑器。

- [ ] **Step 3: "重新规划"按钮实现**

添加 `handleReplan` 函数：

```typescript
  const handleReplan = useCallback(() =>
  {
    if (!selectedChapter) return
    const message = `重新规划第${selectedChapter.chapter_number}章大纲`
    // 调用 AgentChatPanel 的发送逻辑
    // 方式：通过 workbenchStore 的 aiSidebarOpen + 预填消息触发
    toggleAiSidebar()
    // 注意：实际发送需要调用 AgentChatPanel 暴露的 sendMessage 方法
    // 或者通过 store 设置一个 "pendingMessage" 状态
    // 最简实现：打开侧边栏 + toast 提示用户在对话框输入
    toast.info('请在右侧 Agent 对话中输入重新规划请求', { description: message })
  }, [selectedChapter, toggleAiSidebar])
```

注意：当前 `AgentChatPanel` 没有暴露外部的 `sendMessage` 方法。最简实现是打开侧边栏 + toast 提示。后续迭代可以通过 store 添加 `pendingMessage` 状态来实现自动发送。

- [ ] **Step 4: 章节列表增加大纲状态标识**

将原有的 `has_content` ✅ 标识替换为四级状态：

```tsx
{chapter.has_content ? (
  <span className="text-[10px] text-green-500 flex-shrink-0">✓</span>
) : chapter.confirmed ? (
  <span className="text-[10px] text-blue-500 flex-shrink-0">●</span>
) : chapter.plot ? (
  <span className="text-[10px] text-amber-500 flex-shrink-0">●</span>
) : (
  <span className="text-[10px] text-gray-300 flex-shrink-0">○</span>
)}
```

折叠状态的侧边栏中，章节按钮的显示也需要同步修改：
- 有正文 → 绿色 ✓
- 已确认 → 蓝色数字
- 已规划 → 琥珀色数字
- 未规划 → 灰色数字

- [ ] **Step 5: AI 生成按钮增加前置检查**

将"AI 生成"按钮的 onClick 从直接 `toggleAiSidebar()` 改为：

```tsx
onClick={() => {
  if (!selectedChapter) return
  // 无大纲 → 提示规划
  if (!selectedChapter.plot) {
    toast.info('请先规划本章大纲', { description: '将自动发送规划请求' })
    toggleAiSidebar()
    return
  }
  // 有大纲但未确认 → 提示确认
  if (!selectedChapter.confirmed) {
    toast.info('请先确认章节大纲后再写作')
    return
  }
  // 已确认 → 正常写作
  toggleAiSidebar()
}}
```

- [ ] **Step 6: 重启前端验证**

```bash
docker compose restart frontend
```

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(frontend): WritingPanel 增加大纲面板、状态标识、前置检查和自动刷新"
```

---

### Task 8: 清理死代码

**Files:**
- Delete: 5 个未使用的组件文件
- Modify: `frontend/src/components/workbench/creation/index.ts`

- [ ] **Step 1: 删除未使用的组件文件**

```bash
rm frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
rm frontend/src/components/workbench/creation/ChapterOutlineEditor.tsx
rm frontend/src/components/workbench/creation/ChapterOutlineCard.tsx
rm frontend/src/components/workbench/creation/ChapterOutlineFlatList.tsx
rm frontend/src/components/workbench/creation/ChapterOutlineTreeView.tsx
```

- [ ] **Step 2: 更新 index.ts 导出**

从 `frontend/src/components/workbench/creation/index.ts` 中移除：
```typescript
export { ChapterOutlinePanel } from './ChapterOutlinePanel'
```

其余 4 个组件没有被 index.ts 导出，无需移除。

- [ ] **Step 3: 重启前端验证无编译错误**

```bash
docker compose restart frontend
docker compose logs frontend --tail 10
```

- [ ] **Step 4: 提交**

```bash
git add -A frontend/src/components/workbench/creation/
git commit -m "chore(frontend): 清理未使用的章节大纲组件死代码"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 验证数据库迁移**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

- [ ] **Step 2: 验证后端 API 新字段**

```bash
curl -s http://localhost:8000/api/projects/1/chapter-outlines | python3 -m json.tool | grep -E "opening_state|emotional_arc|key_scenes|pacing_note"
```

- [ ] **Step 3: 验证前端页面**

打开工作台写作标签页，确认：
- 左侧章节列表显示四级状态标识（○ ● ● ✓）
- 正文上方显示可折叠大纲面板
- Agent 完成对话后大纲面板自动刷新

- [ ] **Step 4: 验证 Agent 工具**

在 Agent 对话中输入"规划第1章"，观察 Agent 调用 `generate_chapter_outline`，大纲面板刷新，状态变为"已规划"。

- [ ] **Step 5: 验证写作前置检查**

大纲未确认时点击"AI 生成"，确认 toast 提示出现。

- [ ] **Step 6: 验证审核/重写包含新字段**

在 Agent 对话中审核已写章节，确认审核消息中包含开场状态、情绪弧线等指导信息。

- [ ] **Step 7: 最终提交**

```bash
git add -A
git commit -m "fix: 章节大纲功能端到端验证修复"
```
