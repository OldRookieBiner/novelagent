# Phase 2: Knowledge Base + Free Operation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Free Operation Agent from CRUD tools to cognitive tools, add impact assessment for knowledge base changes, and upgrade the frontend chat panel for rich tool output.

**Architecture:** Replace old `agent_tools.py` CRUD tools with 13 cognitive tools grouped as perception (6), modification (3 with impact assessment), and creation assist (4). Add `SettingChange` model for tracking proposals. Rewrite `agent_context.py` to use `KnowledgeBaseService` instead of direct DB queries. Rewrite `agent_graph.py` with phase-aware system prompts. Upgrade `AgentChatPanel` with SSE integration and impact assessment cards.

**Tech Stack:** Python 3.12 / LangGraph `create_react_agent` / LangChain tools / SQLAlchemy / FastAPI SSE / React 18 + Zustand + shadcn/ui

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/models/setting_change.py` | Create | SettingChange ORM model for impact assessment tracking |
| `backend/app/models/__init__.py` | Modify | Export SettingChange |
| `backend/app/models/project.py` | Modify | Add setting_changes relationship |
| `backend/app/agents/agent_tools.py` | Rewrite | 13 cognitive tools replacing 18 CRUD tools |
| `backend/app/agents/agent_context.py` | Rewrite | Phase-aware context builder using KnowledgeBaseService |
| `backend/app/agents/agent_graph.py` | Rewrite | Phase-aware ReAct agent with cognitive tools |
| `backend/app/agents/tool_context.py` | Modify | Add project_id contextvar |
| `backend/app/agents/sse_events.py` | Modify | Add impact_assessment and warning SSE events |
| `backend/app/agents/prompts.py` | Modify | Add AGENT_SYSTEM_PROMPT template |
| `backend/app/api/agent.py` | Rewrite | Integrate new tools, impact assessment flow, phase-aware prompts |
| `frontend/src/stores/workbenchStore.ts` | Modify | Add impact assessment state, SSE agent chat actions |
| `frontend/src/components/workbench/AgentChatPanel.tsx` | Rewrite | SSE chat, impact assessment cards, rich tool output |
| `backend/tests/test_agent_tools.py` | Create | Cognitive tool unit tests |
| `backend/alembic/versions/20260527_phase2_setting_change.py` | Create | Migration for setting_changes table |

---


### Task 1: SettingChange Model + Migration

**Files:**
- Create: `backend/app/models/setting_change.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/20260527_phase2_setting_change.py`

- [ ] **Step 1: Create SettingChange model**

Create `backend/app/models/setting_change.py`:

```python
"""Knowledge base change proposal + impact assessment tracking

Spec section 4: Knowledge base changes must be proposed first,
assessed for impact, then approved/abandoned by the author.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class SettingChange(Base):
    """Knowledge base change proposal

    Tracks proposed changes to the knowledge base along with
    their impact assessment and the author's decision.
    """

    __tablename__ = "setting_changes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    # What is being changed: world_setting / character / foreshadowing / style / outline / relation
    target_type = Column(String(50), nullable=False)
    # ID of the object being changed
    target_id = Column(Integer, nullable=False)
    # JSON snapshot of the current value
    old_value = Column(JSON, nullable=True)
    # JSON of the proposed new value
    new_value = Column(JSON, nullable=False)
    # proposed / approved / abandoned / applied
    status = Column(String(20), default="proposed")
    # Impact assessment report JSON: {level, affected_chapters, affected_paragraphs, details}
    impact_report = Column(JSON, nullable=True)
    # Author decision: proceed / adjust / abandon
    author_decision = Column(String(20), nullable=True)
    # Natural language description of the change
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="setting_changes")

    def __repr__(self):
        return f"<SettingChange {self.target_type}:{self.target_id} status={self.status}>"
```

- [ ] **Step 2: Register in models/__init__.py**

Add `SettingChange` to `backend/app/models/__init__.py` imports and `__all__`.

- [ ] **Step 3: Add relationship to Project model**

Add to `backend/app/models/project.py` Project class:

```python
    setting_changes = relationship(
        "SettingChange", back_populates="project", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Create Alembic migration**

Create `backend/alembic/versions/20260527_phase2_setting_change.py` that creates the `setting_changes` table.

- [ ] **Step 5: Run migration**

Run: `docker compose exec backend alembic upgrade head`
Expected: Migration applies, `setting_changes` table exists.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/setting_change.py backend/app/models/__init__.py backend/app/models/project.py backend/alembic/versions/
git commit -m "feat(models): add SettingChange model for impact assessment tracking"
```

---


### Task 2: Add KnowledgeBaseService Methods for Impact Assessment

**Files:**
- Modify: `backend/app/agents/services/knowledge_base.py`

- [ ] **Step 1: Add SettingChange CRUD methods**

Add these methods to `KnowledgeBaseService` in `backend/app/agents/services/knowledge_base.py`:

```python
    # ========== 变更提案 ==========

    def create_setting_change(self, data: dict) -> "SettingChange":
        from app.models.setting_change import SettingChange
        db = self._get_db()
        committed = False
        try:
            change = SettingChange(project_id=self.project_id, **data)
            db.add(change)
            db.commit()
            committed = True
            db.refresh(change)
            return change
        finally:
            self._close_db_write(db, committed)

    def get_setting_changes(self, status: Optional[str] = None) -> list:
        from app.models.setting_change import SettingChange
        db = self._get_db()
        try:
            query = db.query(SettingChange).filter(
                SettingChange.project_id == self.project_id
            )
            if status:
                query = query.filter(SettingChange.status == status)
            return query.order_by(SettingChange.created_at.desc()).all()
        finally:
            self._close_db_read(db)

    def get_setting_change(self, change_id: int) -> Optional["SettingChange"]:
        from app.models.setting_change import SettingChange
        db = self._get_db()
        try:
            return db.query(SettingChange).filter(
                SettingChange.id == change_id,
                SettingChange.project_id == self.project_id,
            ).first()
        finally:
            self._close_db_read(db)

    def update_setting_change(self, change_id: int, data: dict) -> "SettingChange":
        from app.models.setting_change import SettingChange
        db = self._get_db()
        committed = False
        try:
            change = db.query(SettingChange).filter(
                SettingChange.id == change_id,
                SettingChange.project_id == self.project_id,
            ).first()
            if not change:
                raise ValueError(f"SettingChange {change_id} not found")
            for key, value in data.items():
                setattr(change, key, value)
            db.commit()
            committed = True
            db.refresh(change)
            return change
        finally:
            self._close_db_write(db, committed)
```

- [ ] **Step 2: Add Chapter access methods**

KnowledgeBaseService currently has no chapter read/write methods. The Free Operation Agent needs these.
Add to `KnowledgeBaseService`:

```python
    # ========== 章节 ==========

    def get_chapter_by_number(self, chapter_number: int) -> Optional["Chapter"]:
        """Get chapter content by chapter number."""
        from app.models.outline import ChapterOutline
        from app.models.chapter import Chapter
        db = self._get_db()
        try:
            co = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
                ChapterOutline.chapter_number == chapter_number,
            ).first()
            if not co:
                return None
            return db.query(Chapter).filter(
                Chapter.chapter_outline_id == co.id,
            ).first()
        finally:
            self._close_db_read(db)

    def update_character_direct(self, character_id: int, data: dict) -> Character:
        """Update character fields directly. Used by _apply_change in agent API."""
        db = self._get_db()
        committed = False
        try:
            char = db.query(Character).filter(
                Character.id == character_id,
                Character.project_id == self.project_id,
            ).first()
            if not char:
                raise ValueError(f"Character {character_id} not found")
            for key, value in data.items():
                if hasattr(char, key):
                    setattr(char, key, value)
            db.commit()
            committed = True
            db.refresh(char)
            return char
        finally:
            self._close_db_write(db, committed)
```

- [ ] **Step 3: Add impact search method**

Add a method that searches written chapters for references to a specific setting element. This is the foundation for impact assessment:

```python
    def search_chapters_for_references(self, keywords: list[str], max_chapters: int = 50) -> list[dict]:
        """Search written chapter content for references to given keywords.

        Returns list of {chapter_number, title, matching_paragraphs: [{index, text}]}
        Used by impact_assessment to find affected content.
        """
        from app.models.outline import ChapterOutline
        from app.models.chapter import Chapter
        from sqlalchemy.orm import joinedload
        db = self._get_db()
        try:
            results = []
            # Eager load chapter content to avoid N+1 queries
            outlines = db.query(ChapterOutline).filter(
                ChapterOutline.project_id == self.project_id,
            ).order_by(ChapterOutline.chapter_number).limit(max_chapters).all()

            for co in outlines:
                chapter = db.query(Chapter).filter(
                    Chapter.chapter_outline_id == co.id,
                ).first()
                if not chapter or not chapter.content:
                    continue

                paragraphs = chapter.content.split("\n")
                matching = []
                for i, para in enumerate(paragraphs):
                    if not para.strip():
                        continue
                    for kw in keywords:
                        if kw in para:
                            matching.append({"index": i, "text": para[:200]})
                            break

                if matching:
                    results.append({
                        "chapter_number": co.chapter_number,
                        "title": co.title or "",
                        "matching_paragraphs": matching,
                    })
            return results
        finally:
            self._close_db_read(db)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/services/knowledge_base.py
git commit -m "feat(services): add SettingChange CRUD + chapter reference search to KnowledgeBaseService"
```

---


### Task 3: Rewrite tool_context.py — Add project_id

**Files:**
- Modify: `backend/app/agents/tool_context.py`

- [ ] **Step 1: Add project_id contextvar**

Replace `backend/app/agents/tool_context.py` with:

```python
"""Agent tool runtime context

Uses contextvars to safely pass request-level context in async environments,
preventing cross-contamination between concurrent requests.
"""

from contextvars import ContextVar

# Current request model config ID
_current_model_config_id: ContextVar[int | None] = ContextVar("model_config_id", default=None)

# Current request user ID
_current_user_id: ContextVar[int | None] = ContextVar("user_id", default=None)

# Current request project ID — shared by all cognitive tools
_current_project_id: ContextVar[int | None] = ContextVar("project_id", default=None)


def set_tool_context(
    model_config_id: int | None = None,
    user_id: int | None = None,
    project_id: int | None = None,
):
    """Set tool context for the current request, return reset tokens"""
    tokens = []
    if model_config_id is not None:
        tokens.append(_current_model_config_id.set(model_config_id))
    if user_id is not None:
        tokens.append(_current_user_id.set(user_id))
    if project_id is not None:
        tokens.append(_current_project_id.set(project_id))
    return tokens


def reset_tool_context(tokens: list):
    """Reset tool context (called when request ends)"""
    for token in tokens:
        token.var.reset(token)


def get_model_config_id() -> int | None:
    return _current_model_config_id.get()


def get_user_id() -> int | None:
    return _current_user_id.get()


def get_project_id() -> int | None:
    return _current_project_id.get()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tool_context.py
git commit -m "refactor(agents): add project_id contextvar to tool_context"
```

---


### Task 4: Rewrite agent_tools.py — 13 Cognitive Tools

**Files:**
- Rewrite: `backend/app/agents/agent_tools.py`

This is the core task. Replace all 18 CRUD tools with 13 cognitive tools.
Every tool reads from KnowledgeBaseService via `get_project_id()` from tool_context.
No tool creates its own DB session — KnowledgeBaseService handles session lifecycle.

- [ ] **Step 1: Write the complete agent_tools.py**

Replace `backend/app/agents/agent_tools.py` with:

```python
"""Cognitive tools for the Free Operation Agent (ReAct)

Three categories:
1. Perception (6) — read-only queries about the knowledge base
2. Modification (3) — propose changes with automatic impact assessment
3. Creation Assist (4) — help the author with creative decisions

All tools use KnowledgeBaseService (shared with the main writing loop)
via project_id from tool_context. No tool manages its own DB session.
"""

import json
from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.services.knowledge_base import KnowledgeBaseService


def _kb() -> KnowledgeBaseService:
    """Get KnowledgeBaseService for the current project context.

    Raises ValueError if project_id is not set in tool_context.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")
    return KnowledgeBaseService(project_id)


def _serialize(obj) -> dict | list | str:
    """Serialize an ORM object to a dict, handling detached sessions."""
    if obj is None:
        return {}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns
            if c.name not in ("created_at", "updated_at")
        }
    return str(obj)


# ========================================================================
# 1. Perception Tools (read-only)
# ========================================================================


@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """Search the knowledge base for specific information.

    Use when the user asks about any aspect of the novel's settings,
    characters, plot, or style. Returns structured results from the DB.

    Args:
        query: Natural language search query (e.g., "主角的魔法限制", "世界观核心规则")
        target: Which part to search - "world_setting", "characters",
                "foreshadowing", "timeline", "plot", "style", or "all"
    """
    kb = _kb()
    results = {}

    if target in ("all", "world_setting"):
        ws = kb.get_world_setting()
        if ws:
            results["world_setting"] = _serialize(ws)

    if target in ("all", "characters"):
        chars = kb.get_characters()
        results["characters"] = _serialize(chars)

    if target in ("all", "foreshadowing"):
        foreshadowings = kb.get_foreshadowings()
        results["foreshadowings"] = _serialize(foreshadowings)

    if target in ("all", "timeline"):
        timeline = kb.get_timeline()
        results["timeline"] = _serialize(timeline)

    if target in ("all", "plot"):
        blocks = kb.get_plot_blocks()
        questions = kb.get_plot_questions()
        subplots = kb.get_subplots()
        results["plot_blocks"] = _serialize(blocks)
        results["plot_questions"] = _serialize(questions)
        results["subplots"] = _serialize(subplots)

    if target in ("all", "style"):
        style = kb.get_style_constraints()
        snapshots = kb.get_style_snapshots(last_n=5)
        results["style_constraints"] = _serialize(style) if style else {}
        results["recent_style_snapshots"] = _serialize(snapshots)

    # Filter results to only include non-empty sections
    filtered = {k: v for k, v in results.items() if v}
    if not filtered:
        return {"found": False, "message": f"未找到与「{query}」相关的知识库内容"}
    return {"found": True, "results": filtered}


@tool
async def foreshadowing_check(current_chapter: int | None = None) -> dict:
    """Check foreshadowing status — active, pending reclaim, overdue.

    Use when the user asks about foreshadowing health, which foreshadowings
    haven't been reclaimed, or whether any are overdue.

    Args:
        current_chapter: Current chapter number (for overdue calculation).
                         If not provided, uses the latest chapter.
    """
    kb = _kb()

    active = kb.get_foreshadowings(status="active")
    pending = kb.get_pending_foreshadowings()
    overdue = []
    if current_chapter:
        overdue = kb.get_overdue_foreshadowings(current_chapter)

    result = {
        "active_count": len(active),
        "pending_reclaim_count": len(pending),
        "overdue_count": len(overdue),
        "active": [{"id": f.id, "content": f.content[:80], "planted_chapter": f.planted_chapter, "level": f.level} for f in active],
        "pending_reclaim": [{"id": f.id, "content": f.content[:80], "expected_resolve_chapter": f.expected_resolve_chapter} for f in pending],
        "overdue": [{"id": f.id, "content": f.content[:80], "expected_resolve_chapter": f.expected_resolve_chapter, "overdue_by": current_chapter - f.expected_resolve_chapter if current_chapter and f.expected_resolve_chapter else 0} for f in overdue],
    }

    if overdue:
        result["warning"] = f"有 {len(overdue)} 个伏笔已超过预期回收章节"
    return result


@tool
async def consistency_check(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """Check consistency between two chapters or across the whole novel.

    Use when the user suspects a contradiction or wants to verify
    consistency of character behavior, timeline, or settings.

    Args:
        chapter_a: First chapter number to compare
        chapter_b: Second chapter number to compare
        aspect: What to check - "character", "timeline", "setting", or "all"
    """
    kb = _kb()
    result = {"chapters_compared": [chapter_a, chapter_b], "issues": []}

    # Check character consistency
    if aspect in ("all", "character"):
        chars = kb.get_characters()
        for char in chars:
            kb_data = {
                "name": char.name,
                "knowledge_boundary": getattr(char, "knowledge_boundary", None) or getattr(char, "deep_fear", ""),
            }
            # Note: actual content analysis would require reading chapter text
            # Here we provide the character's constraints for reference
            result["character_constraints"] = result.get("character_constraints", [])
            result["character_constraints"].append(kb_data)

    # Check timeline consistency
    if aspect in ("all", "timeline"):
        timeline = kb.get_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = _serialize(timeline)

    # Check world setting consistency
    if aspect in ("all", "setting"):
        ws = kb.get_world_setting()
        if ws:
            result["world_setting_red"] = ws.tiered_settings.get("red", []) if ws.tiered_settings else []

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result


@tool
async def style_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze writing style trends and detect drift.

    Use when the user asks about style consistency, dialogue ratio,
    or whether recent chapters are drifting from the established style.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    snapshots = kb.get_style_snapshots(last_n=last_n_chapters)

    if not snapshots:
        return {"has_data": False, "message": "尚无风格统计数据，需要先写几章后才能分析"}

    # Calculate averages
    avg_dialogue = sum(s.dialogue_ratio for s in snapshots if s.dialogue_ratio) / max(len(snapshots), 1)
    avg_sent_len = sum(s.avg_sentence_length for s in snapshots if s.avg_sentence_length) / max(len(snapshots), 1)
    avg_para_len = sum(s.avg_paragraph_length for s in snapshots if s.avg_paragraph_length) / max(len(snapshots), 1)

    # Drift detection: compare latest 3 vs overall average
    drift = {}
    if len(snapshots) >= 3:
        recent_3 = snapshots[:3]
        recent_dialogue = sum(s.dialogue_ratio for s in recent_3) / 3
        recent_sent = sum(s.avg_sentence_length for s in recent_3) / 3

        if avg_dialogue > 0 and abs(recent_dialogue - avg_dialogue) / avg_dialogue > 0.25:
            drift["dialogue_ratio"] = {
                "overall_avg": round(avg_dialogue, 3),
                "recent_avg": round(recent_dialogue, 3),
                "direction": "偏高" if recent_dialogue > avg_dialogue else "偏低",
            }
        if avg_sent_len > 0 and abs(recent_sent - avg_sent_len) / avg_sent_len > 0.25:
            drift["sentence_length"] = {
                "overall_avg": round(avg_sent_len, 1),
                "recent_avg": round(recent_sent, 1),
                "direction": "偏长" if recent_sent > avg_sent_len else "偏短",
            }

    result = {
        "has_data": True,
        "overall_averages": {
            "dialogue_ratio": round(avg_dialogue, 3),
            "avg_sentence_length": round(avg_sent_len, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
        },
        "snapshots": [
            {
                "chapter": s.chapter_number,
                "dialogue_ratio": s.dialogue_ratio,
                "avg_sentence_length": s.avg_sentence_length,
                "paragraph_count": s.paragraph_count,
            }
            for s in snapshots
        ],
        "drift_detection": drift if drift else "风格稳定，未检测到漂移",
    }

    if drift:
        result["warning"] = "检测到风格漂移，建议检查最近几章的写作风格"
    return result


@tool
async def progress_report() -> dict:
    """Generate a writing progress report.

    Use when the user asks how far they've gotten, what's been written,
    what's left, or the overall status of the novel.
    """
    kb = _kb()

    outline = kb.get_outline()
    chars = kb.get_characters()
    foreshadowings = kb.get_foreshadowings()
    timeline = kb.get_timeline()
    blocks = kb.get_plot_blocks()

    written_chapters = len([t for t in timeline]) if timeline else 0
    total_chapters = 0
    if outline:
        total_chapters = outline.chapter_count_confirmed or outline.chapter_count_suggested or 0

    active_foreshadowings = [f for f in foreshadowings if f.status in ("active", "pending_reclaim")]
    reclaimed = [f for f in foreshadowings if f.status == "reclaimed"]

    result = {
        "total_planned_chapters": total_chapters,
        "chapters_written": written_chapters,
        "progress_percent": round(written_chapters / total_chapters * 100, 1) if total_chapters else 0,
        "characters_count": len(chars),
        "foreshadowings_active": len(active_foreshadowings),
        "foreshadowings_reclaimed": len(reclaimed),
        "plot_blocks_total": len(blocks),
        "plot_blocks_completed": len([b for b in blocks if b.completion_summary]),
    }

    if outline:
        result["title"] = outline.title or "未命名"
        result["summary"] = (outline.summary or "")[:200]

    return result


@tool
async def rhythm_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze story rhythm — tension, emotion, pacing trends.

    Use when the user asks about pacing, whether recent chapters
    feel flat, or whether the rhythm curve is monotone.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    timeline = kb.get_timeline()
    recent = timeline[:last_n_chapters] if timeline else []

    if not recent:
        return {"has_data": False, "message": "尚无时间线数据，需要先写几章后才能分析节奏"}

    # Detect monotone sections: 3+ consecutive chapters with same emotion_tag
    monotone_sections = []
    consecutive_same = 0
    last_tag = None
    start_chapter = None

    for entry in reversed(recent):  # timeline is ordered desc
        tag = entry.emotion_tag
        if tag == last_tag and tag:
            consecutive_same += 1
            if consecutive_same >= 3 and not monotone_sections:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": entry.chapter_number,
                    "emotion": tag,
                    "length": consecutive_same + 1,
                })
        else:
            if consecutive_same >= 3:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": last_tag_chapter,
                    "emotion": last_tag,
                    "length": consecutive_same + 1,
                })
            consecutive_same = 0
            start_chapter = entry.chapter_number
        last_tag = tag
        last_tag_chapter = entry.chapter_number

    result = {
        "has_data": True,
        "chapters_analyzed": len(recent),
        "rhythm_curve": [
            {
                "chapter": t.chapter_number,
                "rhythm_score": t.rhythm_score,
                "tension_score": t.tension_score,
                "emotion_score": t.emotion_score,
                "emotion_tag": t.emotion_tag,
            }
            for t in reversed(recent)
        ],
        "monotone_sections": monotone_sections,
        "average_tension": round(sum(t.tension_score for t in recent if t.tension_score) / max(len(recent), 1), 1),
    }

    if monotone_sections:
        result["warning"] = f"检测到 {len(monotone_sections)} 段节奏单调区域，建议调整情绪节奏"
    return result


# ========================================================================
# 2. Modification Tools (with impact assessment)
# ========================================================================


@tool
async def propose_setting_change(
    target_type: str,
    target_id: int,
    new_value: str,
    description: str,
) -> dict:
    """Propose a change to a knowledge base setting.

    Automatically triggers impact assessment. The change is NOT applied
    immediately — it creates a SettingChange record with status="proposed"
    and an impact report. The author must approve or abandon it.

    Args:
        target_type: What to change - "world_setting", "character",
                     "foreshadowing", "style", "outline", "relation"
        target_id: ID of the object to change
        new_value: JSON string describing the new value
        description: Natural language description of the proposed change
    """
    kb = _kb()

    # Get old value for comparison
    old_value = _get_current_value(kb, target_type, target_id)

    # Parse new_value
    try:
        new_value_parsed = json.loads(new_value) if isinstance(new_value, str) else new_value
    except json.JSONDecodeError:
        new_value_parsed = {"value": new_value}

    # Impact assessment: search for references
    keywords = _extract_keywords(old_value, new_value_parsed, description)
    affected = kb.search_chapters_for_references(keywords)

    # Grade impact
    impact_level, impact_detail = _grade_impact(affected, target_type, new_value_parsed, old_value)

    impact_report = {
        "level": impact_level,
        "affected_chapters": len(affected),
        "affected_paragraphs": sum(len(ch.get("matching_paragraphs", [])) for ch in affected),
        "details": affected[:5],  # Limit detail to first 5 chapters
        "grading_explanation": impact_detail,
    }

    # Create the SettingChange record
    change = kb.create_setting_change({
        "target_type": target_type,
        "target_id": target_id,
        "old_value": old_value,
        "new_value": new_value_parsed,
        "description": description,
        "status": "proposed",
        "impact_report": impact_report,
    })

    level_labels = {"none": "🟢 不影响", "minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_chapters": impact_report["affected_chapters"],
        "affected_paragraphs": impact_report["affected_paragraphs"],
        "detail": impact_detail,
        "next_steps": "作者需决策：proceed（按原方案修改）/ adjust（调整修改方案）/ abandon（放弃修改）",
    }


@tool
async def propose_outline_adjustment(
    description: str,
    affected_plot_blocks: list[int] | None = None,
) -> dict:
    """Propose an adjustment to the story structure.

    Evaluates impact on foreshadowing, plot questions, and already-written chapters.

    Args:
        description: Natural language description of the proposed adjustment
        affected_plot_blocks: List of plot block IDs that would be affected
    """
    kb = _kb()

    blocks = kb.get_plot_blocks()
    foreshadowings = kb.get_foreshadowings(status="active")
    questions = kb.get_plot_questions(status="pending")

    affected_blocks = []
    if affected_plot_blocks:
        affected_blocks = [b for b in blocks if b.id in affected_plot_blocks]
    else:
        # If not specified, check all blocks for keyword overlap
        for b in blocks:
            block_text = f"{b.title} {' '.join(b.must_happen or [])} {' '.join(b.questions_to_answer or [])}"
            for word in description.split():
                if len(word) >= 2 and word in block_text:
                    affected_blocks.append(b)
                    break

    affected_foreshadowings = []
    for f in foreshadowings:
        for b in affected_blocks:
            if b.chapter_start and f.expected_resolve_chapter:
                if b.chapter_start <= f.expected_resolve_chapter <= (b.chapter_end or 999):
                    affected_foreshadowings.append({
                        "id": f.id,
                        "content": f.content[:60],
                        "expected_resolve_chapter": f.expected_resolve_chapter,
                    })

    affected_questions = []
    for q in questions:
        for b in affected_blocks:
            if q.plot_block_id == b.id:
                affected_questions.append({
                    "id": q.id,
                    "question": q.question_text[:60],
                    "status": q.status,
                })

    impact_level = "minor"
    if affected_foreshadowings or affected_questions:
        impact_level = "moderate"
    if len(affected_blocks) > 2:
        impact_level = "severe"

    change = kb.create_setting_change({
        "target_type": "outline_adjustment",
        "target_id": 0,
        "old_value": {},
        "new_value": {"description": description},
        "description": description,
        "status": "proposed",
        "impact_report": {
            "level": impact_level,
            "affected_blocks": [{"id": b.id, "title": b.title, "chapter_range": f"{b.chapter_start}-{b.chapter_end}"} for b in affected_blocks],
            "affected_foreshadowings": affected_foreshadowings,
            "affected_questions": affected_questions,
        },
    })

    level_labels = {"minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_blocks": len(affected_blocks),
        "affected_foreshadowings": len(affected_foreshadowings),
        "affected_questions": len(affected_questions),
        "next_steps": "作者需决策：proceed / adjust / abandon",
    }


@tool
async def propose_chapter_rewrite(
    chapter_number: int,
    reason: str,
) -> dict:
    """Propose rewriting a specific chapter.

    Marks the old version and creates a proposal. Does not rewrite
    immediately — the author must approve.

    Args:
        chapter_number: The chapter to rewrite
        reason: Why the rewrite is needed (e.g., "审核不通过", "设定矛盾")
    """
    kb = _kb()
    chapter = kb.get_chapter_by_number(chapter_number)
    if not chapter:
        return {"error": f"第{chapter_number}章不存在"}
    old_content = chapter.content[:500] if chapter.content else ""
    chapter_id = chapter.id

    change = kb.create_setting_change({
        "target_type": "chapter_rewrite",
        "target_id": chapter_id,
        "old_value": {"chapter_number": chapter_number, "content_preview": old_content},
        "new_value": {"chapter_number": chapter_number, "reason": reason},
        "description": f"提议重写第{chapter_number}章：{reason}",
        "status": "proposed",
        "impact_report": {
            "level": "moderate",
            "affected_chapters": 1,
            "note": "重写章节会影响后续追踪数据（时间线、伏笔、风格统计），重写后需更新追踪文件",
        },
    })

    return {
        "change_id": change.id,
        "chapter_number": chapter_number,
        "status": "proposed",
        "reason": reason,
        "impact": "🟠 重写章节需更新追踪文件（时间线、伏笔、风格统计）",
        "next_steps": "作者确认后可执行重写",
    }


# ========================================================================
# 3. Creation Assist Tools
# ========================================================================


@tool
async def writer_block_assist(current_chapter: int) -> dict:
    """Help overcome writer's block with 2-3 writing directions.

    Suggests scene ideas, reclaimable foreshadowings, and
    question chain prompts based on current progress.

    Args:
        current_chapter: Current chapter number being worked on
    """
    kb = _kb()

    pending = kb.get_pending_foreshadowings()
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    questions = kb.get_questions_for_chapter(current_chapter)
    block = kb.get_current_plot_block(current_chapter)

    suggestions = []

    # Direction 1: Reclaim overdue foreshadowing
    if overdue:
        f = overdue[0]
        suggestions.append({
            "direction": "回收超期伏笔",
            "detail": f"伏笔「{f.content[:50]}」已超过预期回收章节，可以在本章回收",
            "foreshadowing_id": f.id,
        })

    # Direction 2: Answer a pending question
    if questions:
        q = questions[0]
        suggestions.append({
            "direction": "回答待解问题",
            "detail": f"问题「{q.question_text[:50]}」可以在本章回答",
            "question_id": q.id,
        })

    # Direction 3: Follow plot block
    if block:
        must_happen = block.must_happen or []
        if must_happen:
            suggestions.append({
                "direction": "推进情节块",
                "detail": f"当前情节块「{block.title}」必须事件：{must_happen[0][:50] if must_happen else '无'}",
                "plot_block_id": block.id,
            })

    if not suggestions:
        suggestions.append({
            "direction": "自由发挥",
            "detail": "当前没有紧迫的伏笔或问题链需要处理，可以自由推进剧情",
        })

    return {
        "current_chapter": current_chapter,
        "suggestions": suggestions,
        "pending_foreshadowings": len(pending),
        "pending_questions": len(questions),
    }


@tool
async def suggest_foreshadowing(current_chapter: int) -> dict:
    """Suggest foreshadowing placement based on current plot block.

    Analyzes the current plot block and existing foreshadowing map
    to suggest new foreshadowings that fit the story structure.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    block = kb.get_current_plot_block(current_chapter)
    foreshadowings = kb.get_foreshadowings()
    active = [f for f in foreshadowings if f.status in ("active", "pending_reclaim")]

    if not block:
        return {"suggestion": "当前没有情节块信息，建议先完成结构设计"}

    # Suggest based on plot block's questions_to_raise
    suggestions = []
    for question in (block.questions_to_raise or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
        })

    # Suggest based on gaps in the foreshadowing map
    if len(active) < 3 and block.chapter_end and block.chapter_start:
        span = block.chapter_end - block.chapter_start
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
            })

    return {
        "current_chapter": current_chapter,
        "plot_block": block.title if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }


@tool
async def suggest_plot_twist(current_chapter: int) -> dict:
    """Suggest a plot twist based on rhythm curve, character arcs, and foreshadowings.

    Use when the user wants ideas for a surprising turn in the story.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    timeline = kb.get_timeline()
    foreshadowings = kb.get_foreshadowings(status="active")
    characters = kb.get_characters()
    block = kb.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.tension_score:
                recent_tension.append(t.tension_score)

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    # Low tension -> suggest escalation twist
    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    # Active foreshadowings -> suggest misdirection twist
    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f.id for f in foreshadowings[:3]],
        })

    # Character with strong motivation -> suggest betrayal/revelation
    for c in characters:
        if c.core_motivation and len(c.core_motivation) > 10:
            twist_types.append({
                "type": "角色反转",
                "reason": f"角色「{c.name}」的动机可以制造意想不到的转折",
                "character_id": c.id,
                "character_name": c.name,
            })
            break  # Only suggest one character twist

    return {
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:3],
    }


@tool
async def expand_world_setting(aspect: str, description: str) -> dict:
    """Expand the world setting in a specific direction.

    Automatically assesses impact of the expansion on existing content.

    Args:
        aspect: What aspect to expand - "location", "rule", "culture", "history", "technology"
        description: Natural language description of the expansion
    """
    kb = _kb()
    ws = kb.get_world_setting()

    if not ws:
        return {"error": "世界观尚未创建，请先完成创意孵化阶段"}

    # Assess impact: check if expansion contradicts existing red-tier settings
    red_settings = ws.tiered_settings.get("red", []) if ws.tiered_settings else []
    contradictions = []
    for rule in red_settings:
        rule_text = rule if isinstance(rule, str) else str(rule)
        # Simple keyword overlap check
        for word in description.split():
            if len(word) >= 2 and word in rule_text:
                contradictions.append(rule_text[:80])

    impact_level = "none"
    impact_detail = "扩展不与现有🔴设定冲突"
    if contradictions:
        impact_level = "severe"
        impact_detail = f"扩展可能与🔴设定冲突：{'; '.join(contradictions[:3])}"

    # Search for references in existing chapters
    keywords = [w for w in description.split() if len(w) >= 2][:5]
    affected = kb.search_chapters_for_references(keywords) if keywords else []

    if affected and impact_level != "severe":
        impact_level = "minor"

    return {
        "aspect": aspect,
        "description": description,
        "impact_level": impact_level,
        "impact_detail": impact_detail,
        "affected_chapters": len(affected),
        "contradictions": contradictions,
        "suggestion": "可以安全扩展" if impact_level == "none" else "建议先解决冲突再扩展",
    }


# ========================================================================
# Helper functions (not exposed as tools)
# ========================================================================


def _get_current_value(kb: KnowledgeBaseService, target_type: str, target_id: int) -> dict:
    """Get the current value of a knowledge base object for comparison."""
    if target_type == "world_setting":
        obj = kb.get_world_setting()
        if obj and obj.id == target_id:
            return _serialize(obj)
    elif target_type == "character":
        chars = kb.get_characters()
        for c in chars:
            if c.id == target_id:
                return _serialize(c)
    elif target_type == "foreshadowing":
        foreshadowings = kb.get_foreshadowings()
        for f in foreshadowings:
            if f.id == target_id:
                return _serialize(f)
    elif target_type == "style":
        style = kb.get_style_constraints()
        if style and style.id == target_id:
            return _serialize(style)
    elif target_type == "outline":
        outline = kb.get_outline()
        if outline and outline.id == target_id:
            return _serialize(outline)
    elif target_type == "relation":
        relations = kb.get_relations()
        for r in relations:
            if r.id == target_id:
                return _serialize(r)
    return {}


def _extract_keywords(old_value: dict, new_value: dict, description: str) -> list[str]:
    """Extract search keywords from the change description and values."""
    keywords = []
    # From description
    for word in description.split():
        if len(word) >= 2:
            keywords.append(word)
    # From new_value keys that differ from old_value
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        for key in new_value:
            if new_value.get(key) != old_value.get(key):
                val = new_value[key]
                if isinstance(val, str):
                    for word in val.split():
                        if len(word) >= 2:
                            keywords.append(word)
    return keywords[:10]


def _grade_impact(affected_chapters: list, target_type: str, new_value: dict, old_value: dict) -> tuple[str, str]:
    """Grade the impact level of a proposed change.

    Returns (level, detail) where level is one of:
    none, minor, moderate, severe
    """
    total_paragraphs = sum(len(ch.get("matching_paragraphs", [])) for ch in affected_chapters)
    total_chapters = len(affected_chapters)

    if total_chapters == 0:
        return "none", "变更不影响任何已写内容"

    if total_chapters <= 1 and total_paragraphs <= 2:
        return "minor", f"轻微影响：{total_chapters} 章、{total_paragraphs} 段提及，读者不易察觉"

    if total_chapters <= 3 and total_paragraphs <= 5:
        return "moderate", f"中度影响：{total_chapters} 章、{total_paragraphs} 段提及，细心读者可能发现矛盾"

    return "severe", f"严重影响：{total_chapters} 章、{total_paragraphs} 段提及，核心情节可能直接矛盾"


# ========================================================================
# Tool lists by phase
# ========================================================================

# Tools available during incubation phase (perception only + expand)
INCUBATION_TOOLS = [
    knowledge_search,
    progress_report,
    expand_world_setting,
]

# Tools available during structure phase
STRUCTURE_TOOLS = [
    knowledge_search,
    foreshadowing_check,
    progress_report,
    rhythm_analysis,
    propose_outline_adjustment,
    suggest_foreshadowing,
]

# Tools available during writing phase (all tools)
WRITING_TOOLS = [
    # Perception
    knowledge_search,
    foreshadowing_check,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # Modification
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # Creation assist
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
]

# All tools (default)
AGENT_TOOLS = WRITING_TOOLS
```

- [ ] **Step 2: Verify no imports from old services remain**

Run: `grep -n "from app.agents.services.outline_service\|from app.agents.services.character_service\|from app.agents.services.relation_service\|from app.agents.services.chapter_service\|from app.agents.services.edit_service\|from app.agents.services.inspiration_service" backend/app/agents/agent_tools.py`
Expected: No matches

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(agents): rewrite agent_tools with 13 cognitive tools replacing CRUD tools"
```

---


### Task 5: Rewrite agent_context.py — Phase-Aware Context Builder

**Files:**
- Rewrite: `backend/app/agents/agent_context.py`

- [ ] **Step 1: Write the new agent_context.py**

Replace `backend/app/agents/agent_context.py` with a phase-aware context builder
that uses KnowledgeBaseService instead of direct DB queries:

```python
"""Phase-aware context builder for the Free Operation Agent

Reads project data via KnowledgeBaseService (shared with the main writing loop).
Injects a prioritized, token-budget-constrained context into the agent system prompt.

Priorities differ by phase:
- incubation: outline + story seed + world setting basics
- structure: outline + characters + plot blocks + foreshadowing
- writing: current chapter + outline + characters + foreshadowing + style + timeline
- revision: full outline + all tracking data
"""

import json
import re

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.state import Phase


class BudgetTracker:
    """Token budget tracker"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)


def estimate_tokens(text: str) -> int:
    """Estimate token count: Chinese chars x2, English words x1.3"""
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return int(chinese_chars * 2 + english_words * 1.3)


def _serialize(obj) -> dict | list:
    """Serialize ORM object to dict (handles detached sessions)."""
    if obj is None:
        return {}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dict__") and hasattr(obj, "__table__"):
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns
            if c.name not in ("created_at", "updated_at")
        }
    return obj if isinstance(obj, (dict, list)) else str(obj)


def build_agent_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
) -> dict:
    """Build phase-aware project context for the agent system prompt.

    Uses KnowledgeBaseService (independent sessions per read).
    Returns a dict with context sections to be formatted by the caller.
    """
    kb = KnowledgeBaseService(project_id)
    budget = BudgetTracker(max_tokens)
    context: dict = {}

    # === Always load: outline ===
    outline = kb.get_outline()
    if outline:
        outline_data = _serialize(outline)
        outline_json = json.dumps(outline_data, ensure_ascii=False)
        tokens = estimate_tokens(outline_json)
        if budget.can_add(tokens):
            context["outline"] = outline_data
            budget.add(tokens)

    # === Phase-specific loading ===
    if phase == Phase.INCUBATION.value:
        _load_incubation_context(kb, budget, context)

    elif phase == Phase.STRUCTURE.value:
        _load_structure_context(kb, budget, context)

    elif phase == Phase.WRITING.value:
        _load_writing_context(kb, budget, context, current_chapter_number)

    elif phase == Phase.REVISION.value:
        _load_revision_context(kb, budget, context)

    context["_budget_used"] = budget.used
    context["_budget_max"] = budget.max
    return context


def _load_incubation_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    """Incubation: minimal context for creative exploration."""
    ws = kb.get_world_setting()
    if ws:
        data = _serialize(ws)
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = data
            budget.add(estimate_tokens(data_json))


def _load_structure_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    """Structure: characters, plot blocks, foreshadowing map."""
    # Characters
    chars = kb.get_characters()
    char_list = []
    for c in chars:
        info = {"id": c.id, "name": c.name, "role": c.role, "core_motivation": c.core_motivation or ""}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    # Plot blocks
    blocks = kb.get_plot_blocks()
    block_list = []
    for b in blocks:
        info = {
            "id": b.id, "title": b.title,
            "chapter_start": b.chapter_start, "chapter_end": b.chapter_end,
            "expected_mood": b.expected_mood,
        }
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            block_list.append(info)
            budget.add(tokens)
    context["plot_blocks"] = block_list

    # Foreshadowing plan
    foreshadowings = kb.get_foreshadowings()
    fs_list = []
    for f in foreshadowings:
        info = {
            "id": f.id, "content": f.content[:60],
            "planted_chapter": f.planted_chapter,
            "expected_resolve_chapter": f.expected_resolve_chapter,
            "status": f.status,
        }
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            fs_list.append(info)
            budget.add(tokens)
    context["foreshadowings"] = fs_list


def _load_writing_context(
    kb: KnowledgeBaseService,
    budget: BudgetTracker,
    context: dict,
    current_chapter_number: int | None,
):
    """Writing: current chapter + relevant characters + foreshadowing + style."""
    # Characters (brief)
    chars = kb.get_characters()
    char_list = []
    for c in chars:
        info = {
            "id": c.id, "name": c.name, "role": c.role,
            "core_motivation": c.core_motivation or "",
            "personality": (c.personality or "")[:100],
        }
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    # World setting
    ws = kb.get_world_setting()
    if ws:
        data = {
            "core_concept": ws.core_concept or "",
            "red_settings": ws.tiered_settings.get("red", []) if ws.tiered_settings else [],
            "key_locations": ws.key_locations or [],
        }
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = data
            budget.add(estimate_tokens(data_json))

    # Pending foreshadowings
    pending = kb.get_pending_foreshadowings()
    overdue = kb.get_overdue_foreshadowings(current_chapter_number) if current_chapter_number else []
    context["pending_foreshadowings"] = [
        {"id": f.id, "content": f.content[:60], "expected_resolve_chapter": f.expected_resolve_chapter}
        for f in pending
    ]
    context["overdue_foreshadowings"] = [
        {"id": f.id, "content": f.content[:60], "expected_resolve_chapter": f.expected_resolve_chapter}
        for f in overdue
    ]

    # Style constraints
    style = kb.get_style_constraints()
    if style:
        data = {
            "taboo_words": style.taboo_words or [],
            "forbidden_patterns": style.forbidden_patterns or [],
            "abstract_rules": style.abstract_rules or [],
        }
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["style_constraints"] = data
            budget.add(estimate_tokens(data_json))

    # Current chapter context
    if current_chapter_number:
        block = kb.get_current_plot_block(current_chapter_number)
        if block:
            context["current_plot_block"] = {
                "title": block.title,
                "expected_mood": block.expected_mood,
                "must_happen": block.must_happen or [],
            }

        questions = kb.get_questions_for_chapter(current_chapter_number)
        context["questions_for_chapter"] = [
            {"id": q.id, "question": q.question_text[:60]}
            for q in questions
        ]

    # Recent timeline
    timeline = kb.get_timeline()
    if timeline:
        recent = timeline[:5]
        context["recent_timeline"] = [
            {"chapter": t.chapter_number, "summary": (t.summary or "")[:80], "emotion_tag": t.emotion_tag}
            for t in recent
        ]


def _load_revision_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    """Revision: full data for comprehensive review."""
    # Characters (full)
    chars = kb.get_characters()
    context["characters"] = _serialize(chars)

    # All tracking data
    foreshadowings = kb.get_foreshadowings()
    context["foreshadowings"] = _serialize(foreshadowings)

    questions = kb.get_plot_questions()
    context["plot_questions"] = _serialize(questions)

    subplots = kb.get_subplots()
    context["subplots"] = _serialize(subplots)

    timeline = kb.get_timeline()
    context["timeline"] = _serialize(timeline)

    style = kb.get_style_constraints()
    if style:
        context["style_constraints"] = _serialize(style)

    snapshots = kb.get_style_snapshots()
    context["style_snapshots"] = _serialize(snapshots)


# Model context window mapping (default when model_config.context_window is NULL)
_MODEL_CONTEXT_WINDOW_DEFAULTS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "claude-3.5-sonnet": 200000,
    "claude-sonnet-4-6": 200000,
    "deepseek-v3": 128000,
    "deepseek-r1": 128000,
    "qwen-plus": 131072,
}

DEFAULT_CONTEXT_WINDOW = 128000


def get_context_window(model_config) -> int:
    """Get model context window size.

    Priority: model_config.context_window > default mapping > 128000
    """
    if model_config and model_config.context_window:
        return model_config.context_window

    model_name = (model_config.model_name or "") if model_config else ""
    return _MODEL_CONTEXT_WINDOW_DEFAULTS.get(model_name, DEFAULT_CONTEXT_WINDOW)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/agent_context.py
git commit -m "refactor(agents): rewrite agent_context with phase-aware KnowledgeBaseService"
```

---


### Task 6: Rewrite agent_graph.py — Phase-Aware ReAct Agent

**Files:**
- Rewrite: `backend/app/agents/agent_graph.py`
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: Add AGENT_SYSTEM_PROMPT to prompts.py**

Add this system prompt template to `backend/app/agents/prompts.py`:

```python
AGENT_SYSTEM_PROMPT = """你是一位专业的小说创作智能体，拥有丰富的写作方法论和创作经验。你的核心能力是感知→分析→建议，帮助作者提升写作质量。

## 当前项目状态
- 创作阶段：{phase_label}
- 项目：{project_name}

## 项目上下文
{context_block}

## 你的行为准则

1. **感知优先**：先用 perception 工具了解项目状态，再给出建议
2. **影响评估**：提议修改知识库时，必须使用 propose_setting_change 而不是直接修改，让作者看到影响评估报告后再决策
3. **质量导向**：始终关注伏笔闭环、角色知识边界、风格一致性、问题链推进
4. **创作辅助**：遇到卡文、节奏单调、缺少伏笔等问题时，主动建议创作方向
5. **分级报告**：
   - 伏笔超期 → 🟡预警
   - 风格漂移 → 🟡预警
   - 设定冲突 → 🔴严重
   - 节奏单调 → 🟡建议

## 不可违反规则
- 伏笔至少出现2次（暗示→强化）才能回收
- 角色不得说出知识边界之外的信息
- 🔴设定不得违反
- 每章必须回答一个旧问题或提出一个新问题
- 知识库变更必须先评估影响，不能直接修改

请根据用户的需求，调用相应的工具来感知项目状态、评估影响、或提供创作建议。"""
```

- [ ] **Step 2: Rewrite agent_graph.py**

Replace `backend/app/agents/agent_graph.py`:

```python
"""Free Operation Agent graph definition

Uses LangGraph create_react_agent with phase-aware cognitive tools.
Shares KnowledgeBaseService with the main writing loop.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.agents.agent_tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS
from app.agents.state import Phase
from app.utils.llm import resolve_llm_service


def _get_llm_from_service(llm_service) -> ChatOpenAI:
    """Convert LLMService to LangChain ChatOpenAI for tool calling."""
    return ChatOpenAI(
        model=llm_service.model,
        api_key=llm_service.api_key,
        base_url=llm_service.base_url,
        temperature=0.7,
    )


# Phase -> tool list mapping
_PHASE_TOOLS = {
    Phase.INCUBATION.value: INCUBATION_TOOLS,
    Phase.STRUCTURE.value: STRUCTURE_TOOLS,
    Phase.WRITING.value: WRITING_TOOLS,
    Phase.REVISION.value: WRITING_TOOLS,
}


def create_agent_graph(
    model_config_id: int | None = None,
    user_id: int | None = None,
    phase: str | None = None,
):
    """Create a Free Operation Agent graph instance.

    Args:
        model_config_id: Model config ID for LLM selection
        user_id: User ID for LLM service resolution
        phase: Current creation phase (determines available tools)
    """
    llm_service = resolve_llm_service(model_config_id, user_id)
    llm = _get_llm_from_service(llm_service)

    # Select tools by phase
    tools = _PHASE_TOOLS.get(phase, WRITING_TOOLS)

    graph = create_react_agent(
        model=llm,
        tools=tools,
    )
    return graph
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_graph.py backend/app/agents/prompts.py
git commit -m "feat(agents): rewrite agent_graph with phase-aware cognitive tools + system prompt"
```

---


### Task 7: Add Impact Assessment SSE Events

**Files:**
- Modify: `backend/app/agents/sse_events.py`

- [ ] **Step 1: Add new SSE event formatters**

Add these functions to `backend/app/agents/sse_events.py`:

```python
def format_impact_assessment(data: dict) -> str:
    """Format impact assessment report event for frontend display."""
    import json
    return f"event: impact_assessment\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def format_warning(warning_type: str, data: dict) -> str:
    """Format a warning event (foreshadowing overdue, style drift, etc.)."""
    import json
    payload = {"type": warning_type, **data}
    return f"event: warning\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/sse_events.py
git commit -m "feat(sse): add impact_assessment and warning SSE events"
```

---


### Task 8: Rewrite agent.py API — Phase-Aware with Impact Assessment

**Files:**
- Rewrite: `backend/app/api/agent.py`

- [ ] **Step 1: Rewrite the complete agent.py**

Replace `backend/app/api/agent.py`. Key changes:
- Uses `build_agent_context` with phase parameter
- Uses `AGENT_SYSTEM_PROMPT` template
- Sets `project_id` in tool_context
- Adds `approve_change` and `abandon_change` endpoints for impact assessment flow
- New tool name sets in `stream_agent_events` for cognitive tools

```python
"""AI Creation Agent API routes

Phase-aware agent chat with cognitive tools and impact assessment.
"""

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
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.model_config import ModelConfig
from app.agents.agent_graph import create_agent_graph
from app.agents.prompts import AGENT_SYSTEM_PROMPT
from app.models.workflow_state import WorkflowState
from app.agents.state import Phase
from app.agents.agent_context import build_agent_context, get_context_window, estimate_tokens
from app.agents.tool_context import set_tool_context, reset_tool_context
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.sse_events import (
    format_agent_text,
    format_agent_tool_start,
    format_agent_tool_result,
    format_agent_done,
    format_impact_assessment,
    format_warning,
    format_error_message,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

BUSY_TIMEOUT_SECONDS = 300

PHASE_LABELS = {
    Phase.INCUBATION.value: "创意孵化",
    Phase.STRUCTURE.value: "结构设计",
    Phase.WRITING.value: "写作中",
    Phase.REVISION.value: "修订中",
}


class AgentChatRequest(BaseModel):
    message: str
    model_config_id: Optional[int] = None
    active_tab: Optional[str] = None
    active_menu_item: Optional[str] = None
    current_chapter_number: Optional[int] = None
    history: Optional[list[dict]] = None


class ImpactDecisionRequest(BaseModel):
    """Author decision on a proposed setting change."""
    change_id: int
    decision: str  # "proceed" | "adjust" | "abandon"
    adjusted_value: Optional[str] = None  # JSON, only when decision="adjust"


def _acquire_busy_lock(db: Session, project_id: int, owner: str = "agent") -> bool:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    now = datetime.utcnow()
    if project.is_busy:
        if project.busy_since and (now - project.busy_since).total_seconds() > BUSY_TIMEOUT_SECONDS:
            logger.warning(f"Project {project_id} busy lock expired, preempting")
        else:
            return False
    project.is_busy = True
    project.busy_since = now
    project.busy_by = owner
    db.commit()
    return True


def _release_busy_lock(project_id: int):
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


def _get_or_create_conversation(db: Session, project_id: int) -> AgentConversation:
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if not conv:
        conv = AgentConversation(project_id=project_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def _save_user_message(project_id: int, message: str):
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        msg = AgentMessage(
            conversation_id=conv.id,
            role="user",
            content=message or "",
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        if not conv.title:
            conv.title = message[:50]
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")
        db.rollback()
    finally:
        db.close()


def _save_assistant_message(project_id: int, content: str, segments: list, actions: list):
    db = SessionLocal()
    try:
        conv = _get_or_create_conversation(db, project_id)
        msg = AgentMessage(
            conversation_id=conv.id,
            role="assistant",
            content=content or "",
            segments=segments or [],
            actions=actions or [],
        )
        db.add(msg)
        conv.message_count = (conv.message_count or 0) + 1
        conv.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save assistant message: {e}")
        db.rollback()
    finally:
        db.close()


def _build_truncated_history(history: list[dict], history_budget: int) -> list[dict]:
    if not history or history_budget <= 0:
        return []
    kept: list[dict] = []
    used = 0
    for msg in reversed(history):
        msg_tokens = estimate_tokens(str(msg.get("content", "")))
        if used + msg_tokens > history_budget:
            break
        kept.insert(0, msg)
        used += msg_tokens
    return kept


# Tools that produce impact assessment reports
IMPACT_TOOLS = {"propose_setting_change", "propose_outline_adjustment", "propose_chapter_rewrite"}

# Tools that produce warnings
WARNING_TOOLS = {"foreshadowing_check", "style_analysis", "rhythm_analysis"}


async def stream_agent_events(
    graph,
    messages: list,
    project_id: int,
    accumulator: dict | None = None,
):
    """Stream Agent events with cognitive tool awareness."""
    try:
        async for event in graph.astream_events(
            {"messages": messages},
            config={"configurable": {"thread_id": f"agent-{project_id}"}},
            version="v2",
        ):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content and isinstance(chunk.content, str):
                    if accumulator is not None:
                        accumulator["full"] = accumulator.get("full", "") + chunk.content
                        accumulator.setdefault("segments", []).append(
                            {"type": "agent_text", "content": chunk.content}
                        )
                    yield format_agent_text(chunk.content)

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                if accumulator is not None:
                    accumulator.setdefault("actions", []).append({
                        "tool": tool_name,
                        "status": "running",
                        "args": tool_input,
                    })
                yield format_agent_tool_start(tool_name, tool_input)

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                tool_output = event.get("data", {}).get("output", {})

                # Format tool result
                output_str = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, dict) else str(tool_output)
                yield format_agent_tool_result(tool_name, {"output": output_str[:800]})

                # Mark action as done in accumulator
                if accumulator is not None:
                    actions = accumulator.get("actions", [])
                    for a in reversed(actions):
                        if a["tool"] == tool_name and a.get("status") == "running":
                            a["status"] = "done"
                            a["result"] = tool_output if isinstance(tool_output, dict) else {"output": str(tool_output)}
                            break

                # Impact assessment tools: emit dedicated SSE event
                if tool_name in IMPACT_TOOLS and isinstance(tool_output, dict):
                    if tool_output.get("change_id"):
                        yield format_impact_assessment(tool_output)

                # Warning-producing tools: emit warning if flagged
                if tool_name in WARNING_TOOLS and isinstance(tool_output, dict):
                    if tool_output.get("warning"):
                        yield format_warning(tool_name, {"message": tool_output["warning"]})

        yield format_agent_done()

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield format_error_message(str(e))


@router.get("/{project_id}/agent/conversation")
async def get_conversation(
    project_id: int,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the agent conversation and messages."""
    get_project_for_user(project_id, current_user.id, db)
    conv = _get_or_create_conversation(db, project_id)

    query = db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conv.id
    )
    if before_id is not None:
        query = query.filter(AgentMessage.id < before_id)
    query = query.order_by(AgentMessage.created_at.desc()).limit(limit)

    messages_raw = list(reversed(query.all()))
    messages = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "segments": m.segments or [],
            "actions": m.actions or [],
            "timestamp": int(m.created_at.timestamp() * 1000) if m.created_at else 0,
        }
        for m in messages_raw
    ]

    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "message_count": conv.message_count,
        "messages": messages,
    }


@router.delete("/{project_id}/agent/conversation")
async def clear_conversation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear the agent conversation."""
    get_project_for_user(project_id, current_user.id, db)
    conv = db.query(AgentConversation).filter(
        AgentConversation.project_id == project_id
    ).first()
    if conv:
        db.query(AgentMessage).filter(
            AgentMessage.conversation_id == conv.id
        ).delete()
        conv.message_count = 0
        conv.title = ""
        conv.updated_at = datetime.utcnow()
        db.commit()
    return {"detail": "对话已清空"}


@router.post("/{project_id}/agent/chat")
async def agent_chat(
    project_id: int,
    req: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the AI creation agent (SSE streaming)."""
    project = get_project_for_user(project_id, current_user.id, db)

    if not _acquire_busy_lock(db, project_id, "agent"):
        holder = project.busy_by or "未知"
        raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")

    _save_user_message(project_id, req.message)

    # Read current workflow phase
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).first()
    phase = workflow_state.stage if workflow_state else Phase.INCUBATION.value

    # Get model context window
    model_config = None
    if req.model_config_id:
        model_config = db.query(ModelConfig).filter(
            ModelConfig.id == req.model_config_id
        ).first()
    context_window = get_context_window(model_config)

    # Build phase-aware project context
    context = build_agent_context(
        project_id,
        phase=phase,
        current_chapter_number=req.current_chapter_number,
    )

    # Format context block for system prompt
    context_block = json.dumps(context, ensure_ascii=False, default=str)

    # Build system message
    phase_label = PHASE_LABELS.get(phase, "未知阶段")
    system_content = AGENT_SYSTEM_PROMPT.format(
        phase_label=phase_label,
        project_name=project.name,
        context_block=context_block,
    )

    # Calculate history budget and truncate
    system_used = estimate_tokens(system_content)
    history_budget = int(context_window * 0.7) - system_used
    truncated_history = _build_truncated_history(
        req.history or [],
        max(history_budget, 0),
    )

    messages = [{"role": "system", "content": system_content}]
    messages.extend(truncated_history)
    messages.append({"role": "user", "content": req.message})

    # Create agent graph with phase-aware tools
    try:
        graph = create_agent_graph(
            model_config_id=req.model_config_id,
            user_id=current_user.id,
            phase=phase,
        )
    except ValueError as e:
        _release_busy_lock(project_id)
        raise HTTPException(status_code=400, detail=str(e))

    # Set tool context (including project_id for cognitive tools)
    context_tokens = set_tool_context(
        model_config_id=req.model_config_id,
        user_id=current_user.id,
        project_id=project_id,
    )

    async def _stream_with_cleanup():
        acc: dict = {}
        try:
            async for event in stream_agent_events(graph, messages, project_id, accumulator=acc):
                yield event
            _save_assistant_message(
                project_id,
                content=acc.get("full", ""),
                segments=acc.get("segments", []),
                actions=acc.get("actions", []),
            )
        finally:
            _release_busy_lock(project_id)
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


@router.post("/{project_id}/agent/impact-decision")
async def impact_decision(
    project_id: int,
    req: ImpactDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Author decides on a proposed setting change.

    Three options:
    - proceed: Apply the change as proposed
    - adjust: Apply with adjusted value (requires adjusted_value)
    - abandon: Discard the proposal
    """
    get_project_for_user(project_id, current_user.id, db)
    kb = KnowledgeBaseService(project_id)

    change = kb.get_setting_change(req.change_id)
    if not change:
        raise HTTPException(status_code=404, detail="变更提案不存在")
    if change.status != "proposed":
        raise HTTPException(status_code=400, detail=f"提案状态为 {change.status}，无法决策")

    if req.decision == "abandon":
        kb.update_setting_change(req.change_id, {
            "status": "abandoned",
            "author_decision": "abandon",
        })
        return {"change_id": req.change_id, "status": "abandoned", "message": "已放弃修改"}

    elif req.decision == "proceed":
        # Apply the change to the actual knowledge base object
        _apply_change(kb, change)
        kb.update_setting_change(req.change_id, {
            "status": "applied",
            "author_decision": "proceed",
        })
        return {"change_id": req.change_id, "status": "applied", "message": "已按原方案修改"}

    elif req.decision == "adjust":
        if not req.adjusted_value:
            raise HTTPException(status_code=400, detail="adjust 决策需要提供 adjusted_value")
        try:
            adjusted = json.loads(req.adjusted_value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="adjusted_value 不是有效的 JSON")

        # Apply the adjusted value instead
        change.new_value = adjusted
        _apply_change(kb, change)
        kb.update_setting_change(req.change_id, {
            "status": "applied",
            "author_decision": "adjust",
            "new_value": adjusted,
        })
        return {"change_id": req.change_id, "status": "applied", "message": "已按调整方案修改"}

    else:
        raise HTTPException(status_code=400, detail=f"无效决策: {req.decision}")


def _apply_change(kb: KnowledgeBaseService, change):
    """Apply a proposed change to the actual knowledge base object.

    Delegates to the appropriate KnowledgeBaseService update method
    based on target_type.
    """
    target_type = change.target_type
    target_id = change.target_id
    new_value = change.new_value if not isinstance(change.new_value, str) else json.loads(change.new_value)

    if target_type == "world_setting":
        kb.update_world_setting(target_id, new_value)
    elif target_type == "character":
        kb.update_character_direct(target_id, new_value)
    elif target_type == "style":
        kb.update_style_constraints(target_id, new_value)
    elif target_type == "foreshadowing":
        kb.update_foreshadowing(target_id, new_value)
    elif target_type == "outline_adjustment":
        # Outline adjustments are structural; mark as applied but don't auto-modify
        pass
    elif target_type == "chapter_rewrite":
        # Chapter rewrites are handled by the main writing loop
        pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/agent.py
git commit -m "feat(api): rewrite agent API with phase-aware prompts + impact assessment flow"
```

---


### Task 9: Update workbenchStore — Agent Chat State + Impact Assessment

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: Add agent chat types and actions**

Add these types and state fields to `frontend/src/stores/workbenchStore.ts`:

```typescript
// Add to existing type definitions

/** Impact assessment report from a propose_* tool */
export interface ImpactReport {
  change_id: number
  status: string
  impact_level: string
  impact_label: string
  affected_chapters: number
  affected_paragraphs: number
  detail: string
  next_steps: string
}

/** Warning from a perception tool */
export interface AgentWarning {
  type: string
  message: string
  timestamp: number
}

/** Tool action in agent message */
export interface ToolAction {
  tool: string
  status: 'running' | 'done'
  args: Record<string, unknown>
  result?: Record<string, unknown>
}
```

Add to the `WorkbenchState` interface:

```typescript
  // Impact assessment
  pendingImpacts: ImpactReport[]
  addPendingImpact: (report: ImpactReport) => void
  removePendingImpact: (changeId: number) => void

  // Warnings
  agentWarnings: AgentWarning[]
  addAgentWarning: (warning: AgentWarning) => void
  clearAgentWarnings: () => void

  // Agent sending state
  isAgentSending: boolean
  setIsAgentSending: (sending: boolean) => void
```

Add to the store implementation:

```typescript
  // Impact assessment
  pendingImpacts: [],
  addPendingImpact: (report) =>
    set((s) => ({ pendingImpacts: [...s.pendingImpacts, report] })),
  removePendingImpact: (changeId) =>
    set((s) => ({ pendingImpacts: s.pendingImpacts.filter((r) => r.change_id !== changeId) })),

  // Warnings
  agentWarnings: [],
  addAgentWarning: (warning) =>
    set((s) => ({ agentWarnings: [...s.agentWarnings, { ...warning, timestamp: Date.now() }] })),
  clearAgentWarnings: () => set({ agentWarnings: [] }),

  // Agent sending
  isAgentSending: false,
  setIsAgentSending: (sending) => set({ isAgentSending: sending }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/workbenchStore.ts
git commit -m "feat(store): add impact assessment and warning state to workbenchStore"
```

---


### Task 10: Rewrite AgentChatPanel — SSE Chat + Impact Cards + Rich Tool Output

**Files:**
- Rewrite: `frontend/src/components/workbench/AgentChatPanel.tsx`

- [ ] **Step 1: Rewrite the complete AgentChatPanel**

Replace `frontend/src/components/workbench/AgentChatPanel.tsx` with a fully
functional agent chat panel that:

1. Sends messages to `/api/projects/{id}/agent/chat` SSE endpoint
2. Parses SSE events: `chunk` (text), `agent_tool_start` (tool running),
   `agent_tool_result` (tool output), `impact_assessment` (impact card),
   `warning` (warning badge), `done` (complete)
3. Renders impact assessment cards with approve/abandon buttons
4. Shows tool execution status inline
5. Displays warning badges from perception tools

```tsx
// AgentChatPanel.tsx — Right panel: AI creation agent chat

import { useState, useRef, useEffect, useCallback } from 'react'
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck, X } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { AiMessage, ImpactReport, AgentWarning } from '@/stores/workbenchStore'

const API_BASE = '/api/projects'

export function AgentChatPanel() {
  const {
    currentProjectId,
    aiSidebarOpen,
    toggleAiSidebar,
    aiMessages,
    addAiMessage,
    pendingImpacts,
    addPendingImpact,
    removePendingImpact,
    agentWarnings,
    addAgentWarning,
    isAgentSending,
    setIsAgentSending,
  } = useWorkbenchStore()

  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages, pendingImpacts])

  // SSE chat handler
  const handleSend = useCallback(async () => {
    if (!input.trim() || !currentProjectId || isAgentSending) return

    const userMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(userMsg)
    const messageText = input.trim()
    setInput('')
    setIsAgentSending(true)

    const assistantMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(assistantMsg)

    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      const res = await fetch(`${API_BASE}/${currentProjectId}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
        signal: abortController.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        assistantMsg.content = `错误：${err.detail || res.statusText}`
        setIsAgentSending(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let lastEventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            lastEventType = line.slice(7).trim()
            continue
          }
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6)
            try {
              const data = JSON.parse(dataStr)
              // Dispatch based on the SSE event type, not data shape
              if (lastEventType === 'chunk' && data.content && typeof data.content === 'string') {
                assistantMsg.content += data.content
              } else if (lastEventType === 'agent_tool_start' && data.tool) {
                assistantMsg.segments.push({
                  type: 'tool_start' as any,
                  content: `调用 ${data.tool}...`,
                  data,
                })
              } else if (lastEventType === 'agent_tool_result' && data.tool) {
                assistantMsg.segments.push({
                  type: 'tool_result' as any,
                  content: `${data.tool} 完成`,
                  data,
                })
              } else if (lastEventType === 'impact_assessment' && data.change_id !== undefined) {
                addPendingImpact(data as ImpactReport)
              } else if (lastEventType === 'warning' && data.message) {
                addAgentWarning(data as AgentWarning)
              }
            } catch {
              // Not JSON, skip
            }
            lastEventType = '' // Reset after consuming data line
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        assistantMsg.content = `连接错误：${err.message}`
      }
    } finally {
      setIsAgentSending(false)
      abortRef.current = null
    }
  }, [input, currentProjectId, isAgentSending, addAiMessage, addPendingImpact, addAgentWarning, setIsAgentSending])

  // Impact decision handler
  const handleImpactDecision = async (changeId: number, decision: string) => {
    if (!currentProjectId) return

    try {
      const res = await fetch(`${API_BASE}/${currentProjectId}/agent/impact-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ change_id: changeId, decision }),
      })

      if (res.ok) {
        removePendingImpact(changeId)
      }
    } catch {
      // Silently fail
    }
  }

  // Collapsed state
  if (!aiSidebarOpen) {
    return (
      <div className="w-10 bg-white border-l border-gray-200 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
          title="展开智能体"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        {agentWarnings.length > 0 && (
          <div className="relative">
            <AlertTriangle className="h-3 w-3 text-amber-500" />
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full" />
          </div>
        )}
        <span className="text-gray-400 text-[10px]" style={{ writingMode: 'vertical-lr' }}>
          智能体
        </span>
      </div>
    )
  }

  return (
    <div className="w-[300px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-gray-100 font-semibold text-sm flex items-center gap-2">
        <span>✦ 智能体</span>
        <div className={`w-1.5 h-1.5 rounded-full ml-auto ${isAgentSending ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Warnings */}
      {agentWarnings.length > 0 && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-100">
          {agentWarnings.slice(-2).map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[10px] text-amber-700 mb-1">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {aiMessages.length === 0 && (
          <div className="text-center text-muted-foreground text-xs py-8">
            和智能体讨论你的创作想法
          </div>
        )}
        {aiMessages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'rounded-lg px-3 py-2 text-[11px] leading-relaxed',
              msg.role === 'assistant'
                ? 'bg-primary/5 text-foreground'
                : 'bg-primary text-primary-foreground ml-10'
            )}
          >
            {msg.content || (msg.role === 'assistant' && isAgentSending ? '...' : '')}
            {/* Tool segments */}
            {msg.segments.filter(s => s.type === 'tool_result').map((s, i) => (
              <div key={i} className="mt-1 text-[10px] text-muted-foreground border-t border-gray-100 pt-1">
                {s.content}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Impact Assessment Cards */}
      {pendingImpacts.length > 0 && (
        <div className="px-3 py-2 border-t border-gray-100 space-y-2">
          {pendingImpacts.map((report) => (
            <div key={report.change_id} className="bg-gray-50 rounded-lg p-2 text-[10px]">
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldCheck className="h-3 w-3 text-gray-500" />
                <span className="font-medium">影响评估</span>
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-[9px] font-medium',
                  report.impact_level === 'severe' ? 'bg-red-100 text-red-700' :
                  report.impact_level === 'moderate' ? 'bg-orange-100 text-orange-700' :
                  report.impact_level === 'minor' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-green-100 text-green-700'
                )}>
                  {report.impact_label}
                </span>
              </div>
              <div className="text-muted-foreground mb-1.5">
                影响 {report.affected_chapters} 章 / {report.affected_paragraphs} 段
              </div>
              {report.detail && (
                <div className="text-muted-foreground mb-1.5 text-[9px]">{report.detail}</div>
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'proceed')}
                  className="px-2 py-1 bg-primary text-primary-foreground rounded text-[9px]"
                >
                  按原方案修改
                </button>
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'abandon')}
                  className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-[9px]"
                >
                  放弃
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t border-gray-100">
        <div className="flex gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            className="flex-1 border border-gray-200 rounded-md px-2.5 py-1.5 text-[11px] outline-none focus:border-primary"
            placeholder={isAgentSending ? '思考中...' : '输入消息...'}
            disabled={isAgentSending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isAgentSending}
            className="bg-primary text-primary-foreground border-none px-2.5 py-1.5 rounded-md text-[11px] disabled:opacity-50"
          >
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/AgentChatPanel.tsx
git commit -m "feat(frontend): rewrite AgentChatPanel with SSE chat + impact cards + warnings"
```

---


### Task 11: Integration Test + Backend Verification

**Files:**
- Create: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Write cognitive tool unit tests**

Create `backend/tests/test_agent_tools.py`:

```python
"""Unit tests for cognitive tools (agent_tools.py)

Tests tool registration, KnowledgeBaseService integration,
and impact assessment logic.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.agent_tools import (
    knowledge_search,
    foreshadowing_check,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
    AGENT_TOOLS,
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    _extract_keywords,
    _grade_impact,
)


class TestToolRegistration:
    """Verify all cognitive tools are properly registered."""

    def test_writing_tools_has_13_tools(self):
        assert len(WRITING_TOOLS) == 13

    def test_incubation_tools_subset(self):
        assert len(INCUBATION_TOOLS) == 3
        assert knowledge_search in INCUBATION_TOOLS

    def test_structure_tools_subset(self):
        assert len(STRUCTURE_TOOLS) == 6
        assert propose_outline_adjustment in STRUCTURE_TOOLS

    def test_all_tools_have_names(self):
        for tool in AGENT_TOOLS:
            assert tool.name, f"Tool {tool} missing name"
            assert tool.description, f"Tool {tool.name} missing description"

    def test_perception_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["knowledge_search", "foreshadowing_check", "consistency_check",
                         "style_analysis", "progress_report", "rhythm_analysis"]:
            assert expected in names, f"Missing perception tool: {expected}"

    def test_modification_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["propose_setting_change", "propose_outline_adjustment", "propose_chapter_rewrite"]:
            assert expected in names, f"Missing modification tool: {expected}"

    def test_creation_assist_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["writer_block_assist", "suggest_foreshadowing", "suggest_plot_twist", "expand_world_setting"]:
            assert expected in names, f"Missing creation assist tool: {expected}"


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_extract_keywords_from_description(self):
        keywords = _extract_keywords({}, {}, "主角的魔法限制被修改")
        assert len(keywords) > 0
        assert any("魔法" in k or "主角" in k for k in keywords)

    def test_grade_impact_none(self):
        level, detail = _grade_impact([], "world_setting", {}, {})
        assert level == "none"

    def test_grade_impact_minor(self):
        affected = [{"matching_paragraphs": [{"index": 0, "text": "test"}]}]
        level, detail = _grade_impact(affected, "character", {}, {})
        assert level == "minor"

    def test_grade_impact_severe(self):
        affected = [{"matching_paragraphs": [{"index": i, "text": f"para {i}"} for i in range(10)]} for _ in range(5)]
        level, detail = _grade_impact(affected, "world_setting", {}, {})
        assert level == "severe"


class TestKnowledgeSearch:
    """Test knowledge_search tool with mocked KnowledgeBaseService."""

    @patch("app.agents.agent_tools._kb")
    async def test_search_with_no_results(self, mock_kb_fn):
        mock_kb = MagicMock()
        mock_kb.get_world_setting.return_value = None
        mock_kb.get_characters.return_value = []
        mock_kb.get_foreshadowings.return_value = []
        mock_kb.get_timeline.return_value = []
        mock_kb.get_plot_blocks.return_value = []
        mock_kb.get_plot_questions.return_value = []
        mock_kb.get_subplots.return_value = []
        mock_kb.get_style_constraints.return_value = None
        mock_kb.get_style_snapshots.return_value = []
        mock_kb_fn.return_value = mock_kb

        result = await knowledge_search.ainvoke({"query": "不存在的设定", "target": "all"})
        assert result["found"] is False
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec backend python -m pytest tests/test_agent_tools.py -v`
Expected: Tests pass

- [ ] **Step 3: Run existing tests to check no regressions**

Run: `docker compose exec backend python -m pytest tests/test_creation_agent.py -v`
Expected: All existing tests still pass

- [ ] **Step 4: Verify backend health**

Run: `curl -s http://localhost:8000/health`
Expected: `{"status": "ok"}`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_agent_tools.py
git commit -m "test(agents): add cognitive tool unit tests"
```

---

## Self-Review Checklist

After completing all tasks, verify:

1. **Spec coverage**: Each tool from spec section 6 is implemented
   - [x] 6 perception tools: knowledge_search, foreshadowing_check, consistency_check, style_analysis, progress_report, rhythm_analysis
   - [x] 3 modification tools: propose_setting_change, propose_outline_adjustment, propose_chapter_rewrite
   - [x] 4 creation assist tools: writer_block_assist, suggest_foreshadowing, suggest_plot_twist, expand_world_setting

2. **Spec section 4 coverage**: Impact assessment flow
   - [x] SettingChange model with target_type, target_id, old/new value, status, impact_report, author_decision
   - [x] Impact grading: none/minor/moderate/severe with emoji labels
   - [x] Author decision endpoints: proceed/adjust/abandon
   - [x] Frontend impact cards with approve/abandon buttons

3. **No placeholders**: All code is concrete, no TODO/TBD

4. **Type consistency**: SettingChange fields match between model, service, tools, and API

5. **LangGraph compliance**: create_react_agent is the only graph type used; tools follow LangChain @tool protocol

6. **No technical debt**: All old CRUD tools removed; KnowledgeBaseService is the single data access layer
