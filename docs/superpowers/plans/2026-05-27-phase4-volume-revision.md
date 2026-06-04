# Phase 4: Volume Management + Full-Book Revision

> **Goal:** Support 3M+ word long-form creation with volume management, cross-volume tracking, dual-tier retrieval, and complete full-book revision flow.

**Spec sections:** 9 (Volume Management), 10 (Revision), 5.6 (Cross-Volume Models), 6.4 (Cross-Volume Warnings), 8.3-8.4 (Dual-Tier Retrieval).

---

## Architecture Overview

Phase 4 extends the existing LangGraph StateGraph with:
- A new `volume_transition_node` that orchestrates cross-volume data handoff (snapshot, tracking writes, index rebuild, new volume creation)
- A new routing path: after volume_transition → per-volume revision chain (structural_review → character_arc_review → final_polish) → resume writing context_assembly
- Three new cross-volume tracking models (`CrossVolumeForeshadowing`, `CrossVolumeSubplot`, `CharacterChangeLog`)
- Dual-tier retrieval in `RetrievalService` (volume index + global index)
- Enhanced revision nodes with cross-volume capability
- Three new warning checks in `WarningService`
- Frontend volume management panel + revision report panel

### LangGraph Flow After Phase 4

```
post_write_summary_node
  → (每5章) deep_review_node → route_after_deep_review
  → (卷过渡) volume_transition_node → structural_review_node → character_arc_review_node → final_polish_node → context_assembly_node (new volume)
  → (全部完成) structural_review_node → character_arc_review_node → final_polish_node → END
  → (继续) context_assembly_node
```

Key: volume_transition_node does NOT internally run the revision nodes. Instead, the graph routes from volume_transition → structural_review (per-volume revision) → character_arc_review → final_polish → context_assembly (resume writing in new volume). This conforms to LangGraph's single-node-single-responsibility principle.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/models/volume.py` | Modify | Add `chapter_offset`, `character_snapshot`, `last_block_summary` columns |
| `backend/app/models/cross_volume.py` | Create | `CrossVolumeForeshadowing`, `CrossVolumeSubplot`, `CharacterChangeLog` models |
| `backend/app/models/__init__.py` | Modify | Register new models |
| `backend/app/models/project.py` | Modify | Add cross-volume relationships |
| `backend/alembic/versions/20260527_phase4_volume_revision.py` | Create | Alembic migration for all schema changes |
| `backend/app/agents/state.py` | Modify | Add `VOLUME_TRANSITION` confirmation type, `current_volume` field, `revision_context` field |
| `backend/app/agents/nodes/volume_transition.py` | Create | Volume transition data handoff node |
| `backend/app/agents/services/retrieval.py` | Modify | Add dual-tier retrieval (volume + global indices) |
| `backend/app/agents/nodes/structural_review.py` | Rewrite | Cross-volume: foreshadowing closure, question chain closure, timeline consistency, subplot closure |
| `backend/app/agents/nodes/character_arc_review.py` | Rewrite | Cross-volume: character arc verification, style consistency |
| `backend/app/agents/nodes/final_polish.py` | Rewrite | Full implementation: apply review suggestions, consistency pass, optional encyclopedia |
| `backend/app/agents/services/warning.py` | Modify | Add 3 cross-volume warning checks |
| `backend/app/agents/services/knowledge_base.py` | Modify | Add volume + cross-volume CRUD methods |
| `backend/app/agents/graph.py` | Modify | Add `volume_transition_node`, modify `route_after_post_write`, add `route_after_volume_transition` |
| `backend/app/agents/prompts.py` | Modify | Add volume transition + cross-volume revision prompts |
| `backend/app/agents/sse_events.py` | Modify | Add volume transition event types |
| `backend/tests/test_phase4.py` | Create | Phase 4 integration tests |
| `frontend/src/components/workbench/VolumePanel.tsx` | Create | Volume management panel |
| `frontend/src/components/workbench/RevisionReport.tsx` | Create | Revision report panel |

---

## Task 1: Volume Model Enhancement + Cross-Volume Models + Alembic Migration

### Step 1: Extend Volume model

Add to `backend/app/models/volume.py`:
- `chapter_offset = Column(Integer, default=0, nullable=False)` — global chapter number offset
- `character_snapshot = Column(JSON, nullable=True)` — character state snapshot at volume boundary
- `last_block_summary = Column(Text, nullable=True)` — last plot block summary

### Step 2: Create cross-volume models

Create `backend/app/models/cross_volume.py` with three models:

**CrossVolumeForeshadowing:**
- `project_id` (FK projects.id, CASCADE)
- `source_foreshadowing_id` (FK foreshadowings.id, CASCADE)
- `appearance_count` (Integer, default=1)
- `expected_volume` (Integer, nullable=True)
- `status` (String(20), default="active") — active / resolved
- `project` relationship, `source_foreshadowing` relationship

**CrossVolumeSubplot:**
- `project_id` (FK projects.id, CASCADE)
- `source_subplot_id` (FK subplots.id, CASCADE)
- `status` (String(50), default="active") — active / resolved
- `expected_intersection_volume` (Integer, nullable=True)
- `project` relationship, `source_subplot` relationship

**CharacterChangeLog:**
- `project_id` (FK projects.id, CASCADE)
- `volume_number` (Integer, nullable=False)
- `character_id` (FK characters.id, CASCADE)
- `changes` (JSON, nullable=False) — {field: {old, new}}
- `chapter_number` (Integer, nullable=True)
- `project` relationship, `character` relationship

### Step 3: Register models in `__init__.py`

Add `CrossVolumeForeshadowing`, `CrossVolumeSubplot`, `CharacterChangeLog` to `backend/app/models/__init__.py`.

### Step 4: Add relationships to Project model

Add to `backend/app/models/project.py`:
```python
cross_volume_foreshadowings = relationship("CrossVolumeForeshadowing", back_populates="project", cascade="all, delete-orphan")
cross_volume_subplots = relationship("CrossVolumeSubplot", back_populates="project", cascade="all, delete-orphan")
character_change_logs = relationship("CharacterChangeLog", back_populates="project", cascade="all, delete-orphan")
```

### Step 5: Alembic migration

Create `backend/alembic/versions/20260527_phase4_volume_revision.py`:
- Add `chapter_offset`, `character_snapshot`, `last_block_summary` to `volumes` table
- Create `cross_volume_foreshadowings` table
- Create `cross_volume_subplots` table
- Create `character_change_logs` table

### Step 6: Commit

---

## Task 2: NovelState Extension

### Step 1: Add fields to NovelState

In `backend/app/agents/state.py`:

```python
# Add to ConfirmationType enum:
VOLUME_TRANSITION = "volume_transition"

# Add to NovelState TypedDict:
current_volume: int  # current volume number (1-based)
revision_context: Optional[str]  # "full_book" or "per_volume" — controls revision node behavior
```

`revision_context` is needed because the same `structural_review_node` / `character_arc_review_node` / `final_polish_node` are used for both per-volume revision (after volume transition) and full-book revision (after all chapters done). The revision nodes read this field to adjust their scope:
- `revision_context = "per_volume"`: review current volume only
- `revision_context = "full_book"` (or None): review all volumes (full-book scope)

### Step 2: Commit

---

## Task 3: KnowledgeBaseService — Volume + Cross-Volume CRUD

### Step 1: Add volume-related methods

In `backend/app/agents/services/knowledge_base.py`, add:

**Volume methods:**
- `get_volumes() -> list[Volume]`
- `get_volume(volume_number: int) -> Optional[Volume]`
- `create_volume(data: dict) -> Volume`
- `update_volume(volume_id: int, data: dict) -> Volume`
- `get_current_volume() -> Volume`

**Cross-volume foreshadowing methods:**
- `get_cross_volume_foreshadowings(status: Optional[str] = None) -> list[CrossVolumeForeshadowing]`
- `create_cross_volume_foreshadowing(data: dict) -> CrossVolumeForeshadowing`
- `update_cross_volume_foreshadowing(cvf_id: int, data: dict) -> CrossVolumeForeshadowing`

**Cross-volume subplot methods:**
- `get_cross_volume_subplots(status: Optional[str] = None) -> list[CrossVolumeSubplot]`
- `create_cross_volume_subplot(data: dict) -> CrossVolumeSubplot`
- `update_cross_volume_subplot(cvs_id: int, data: dict) -> CrossVolumeSubplot`

**Character change log methods:**
- `get_character_change_logs(volume_number: Optional[int] = None) -> list[CharacterChangeLog]`
- `create_character_change_log(data: dict) -> CharacterChangeLog`

**Volume-aware queries:**
- `get_chapters_for_volume(volume_number: int) -> list` — chapters whose chapter_number falls in [volume.chapter_offset+1, volume.chapter_offset+volume_chapter_count]

All methods follow existing pattern: independent session per call, try/commit/finally/close.

### Step 2: Commit

---

## Task 4: Dual-Tier RetrievalService

### Step 1: Add volume-aware indexing functions

In `backend/app/agents/services/retrieval.py`, add module-level functions:

```python
def build_volume_index(project_id: int, volume_number: int) -> bool:
    """Build FAISS+BM25 index for a specific volume's data.
    
    Indexes: volume-scoped timeline, foreshadowings, scene entries, chapters.
    Stored at /tmp/novelagent_index/{project_id}/volume_{volume_number}/
    """

def build_global_index(project_id: int) -> bool:
    """Build global index (world setting, characters, relations, style, plot blocks, cross-volume tracking).
    
    Replaces the existing build_index() for multi-volume projects.
    Stored at /tmp/novelagent_index/{project_id}/global/
    """
```

### Step 2: Refactor existing build_index

The existing `build_index()` function becomes a dispatcher:
- Single-volume project: calls `build_global_index()` (backward compatible)
- Multi-volume project: calls `build_global_index()` + `build_volume_index()` for current volume

The `RetrievalService.rebuild_index()` method now rebuilds both global and current volume indices.

### Step 3: Add volume-aware search

```python
def search(project_id: int, query: str, top_k: int = 5, volume_number: Optional[int] = None) -> list[dict]:
    """Dual-tier search:
    
    1. If volume_number given: search volume index first, supplement from global if < top_k results
    2. If no volume_number: search global index only (backward compatible)
    3. Merge + deduplicate by source, keep highest score
    """
```

The `RetrievalService.search()` method gains a `volume_number` parameter.

### Step 4: Commit

---

## Task 5: Volume Transition Node

### Step 1: Create volume_transition_node

Create `backend/app/agents/nodes/volume_transition.py`:

```python
async def volume_transition_node(state: NovelState) -> NovelState:
    """卷过渡数据交接节点
    
    职责（仅数据准备，不运行修订节点——修订由图路由处理）：
    1. 当前卷收尾检查：待回收伏笔清单
    2. 角色状态快照 → 写入 Volume.character_snapshot
    3. 当前卷最后情节块摘要 → 写入 Volume.last_block_summary
    4. 跨卷追踪写入：
       - 未回收伏笔升级到 CrossVolumeForeshadowing
       - 跨卷支线升级到 CrossVolumeSubplot
       - 角色变化日志追加到 CharacterChangeLog
    5. 检索索引：当前卷 rebuild + 全局 rebuild
    6. 创建新卷记录（Volume + chapter_offset）
    7. 更新 state: current_volume += 1, revision_context = "per_volume"
    
    返回后，图路由到 structural_review_node（per-volume revision）。
    """
```

This node does NOT call the revision nodes. It prepares data and sets `revision_context = "per_volume"`. The graph then routes to the revision chain.

### Step 2: Add VOLUME_TRANSITION prompt

In `backend/app/agents/prompts.py`:
```python
VOLUME_TRANSITION_PROMPT = """基于以下信息，执行卷过渡数据交接..."""
VOLUME_REVIEW_PROMPT = """对当前卷进行结构完整性检查（卷内范围）..."""
```

### Step 3: Commit

---

## Task 6: Graph Integration — Volume Transition

### Step 1: Add volume_transition_node to graph

In `backend/app/agents/graph.py`:
```python
from app.agents.nodes.volume_transition import volume_transition_node
graph.add_node("volume_transition_node", volume_transition_node)
```

### Step 2: Modify route_after_post_write

Add volume transition trigger logic:

```python
def route_after_post_write(state: NovelState) -> Literal["deep_review", "volume_transition", "context_assembly", "structural_review"]:
    current_chapter = state.get("current_chapter", 1)
    chapter_count = state.get("chapter_count", 0)
    last_review = state.get("last_review_chapter", 0)

    # Every 5 chapters: deep review
    if current_chapter > 0 and (current_chapter % 5 == 0) and last_review < current_chapter - 4:
        return "deep_review"

    # Volume transition check
    if _should_transition_volume(state):
        return "volume_transition"

    # All chapters done → full-book revision
    if current_chapter > chapter_count:
        return "structural_review"

    # Continue writing
    return "context_assembly"
```

### Step 3: Implement _should_transition_volume

Volume transition triggers (spec section 9.1):
1. **Plot block natural end**: current block is the last block AND `completion_summary` exists
2. **Capacity alert**: non-first volume > 1.5x previous volume chapters; first volume > 120 chapters
3. **User says "切卷"**: `confirmation_type == VOLUME_TRANSITION` set by agent tools

Implementation:
```python
def _should_transition_volume(state: NovelState) -> bool:
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    current_volume = state.get("current_volume", 1)
    
    # User explicit trigger
    if state.get("confirmation_type") == "volume_transition":
        return True
    
    kb = KnowledgeBaseService(project_id)
    
    # Plot block natural end
    current_block = kb.get_current_plot_block(current_chapter)
    if current_block and current_block.completion_summary:
        blocks = kb.get_plot_blocks()
        if current_block.id == blocks[-1].id:
            return True
    
    # Capacity alert
    volume = kb.get_volume(current_volume)
    if volume:
        volume_chapters = current_chapter - volume.chapter_offset
        if current_volume == 1 and volume_chapters > 120:
            return True
        if current_volume > 1:
            prev_volume = kb.get_volume(current_volume - 1)
            if prev_volume:
                prev_chapters = ... # calculate from prev volume data
                if volume_chapters > prev_chapters * 1.5:
                    return True
    
    return False
```

### Step 4: Add routing after volume_transition

```python
def route_after_volume_transition(state: NovelState) -> Literal["structural_review"]:
    """After volume transition data prep → per-volume revision"""
    return "structural_review"

# Add edges
graph.add_conditional_edges(
    "volume_transition_node",
    route_after_volume_transition,
    {"structural_review": "structural_review_node"},
)
```

### Step 5: Modify route_after_final_polish

After the revision chain, we need to determine if this was per-volume or full-book revision:

```python
def route_after_final_polish(state: NovelState) -> Literal["context_assembly", "__end__"]:
    revision_context = state.get("revision_context")
    if revision_context == "per_volume":
        # Per-volume revision done → resume writing in new volume
        return "context_assembly"
    # Full-book revision done → END
    return "__end__"
```

Replace the current `graph.add_edge("final_polish_node", END)` with:
```python
graph.add_conditional_edges(
    "final_polish_node",
    route_after_final_polish,
    {"context_assembly": "context_assembly_node", "__end__": END},
)
```

### Step 6: Commit

---

## Task 7: Enhanced Revision Nodes — Cross-Volume

### Step 1: Rewrite structural_review_node

The node reads `revision_context` from state to determine scope:

```python
async def structural_review_node(state: NovelState) -> NovelState:
    revision_context = state.get("revision_context")
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)
    
    if revision_context == "per_volume":
        # Per-volume review: current volume scope
        current_volume = state.get("current_volume", 1)
        volume = kb.get_volume(current_volume)
        # ... scope data to current volume
    else:
        # Full-book review: all volumes
        # ... include cross-volume tracking data
```

Cross-volume additions for full-book review:
- Read `CrossVolumeForeshadowing`: check if all resolved
- Read `CrossVolumeSubplot`: check if all resolved
- Timeline consistency across volume boundaries (check Volume.character_snapshot transitions)
- Question chain closure across volumes

### Step 2: Rewrite character_arc_review_node

Cross-volume additions:
- Read `CharacterChangeLog` + `Volume.character_snapshot` for character arc verification
- Style consistency check across volumes
- Detect character state jumps without setup (compare snapshots between volumes)
- Same `revision_context` scoping as structural_review

### Step 3: Rewrite final_polish_node — Full Implementation

Replace the current stub with full implementation:

```python
async def final_polish_node(state: NovelState) -> NovelState:
    revision_context = state.get("revision_context")
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)
    
    # 1. Collect review issues from structural_review + character_arc_review
    #    (stored in state or DB)
    # 2. LLM generates revision suggestions based on issues
    # 3. Per 🔴 issues: generate specific fix text
    # 4. Per 🟠 issues: generate modification suggestion
    # 5. 🟡🟢 issues: log but don't modify
    # 6. Final consistency pass
    # 7. Optional: generate setting encyclopedia (full-book revision only)
    
    # Clear revision_context after processing
    updates = {"revision_context": None}
    return {**state, **updates}
```

### Step 4: Add cross-volume revision prompts

In `backend/app/agents/prompts.py`:
- `VOLUME_TRANSITION_PROMPT` — volume transition data handoff
- `PER_VOLUME_STRUCTURAL_REVIEW_PROMPT` — per-volume structural review
- `FULL_BOOK_STRUCTURAL_REVIEW_PROMPT` — full-book structural review with cross-volume
- `PER_VOLUME_CHARACTER_ARC_REVIEW_PROMPT` — per-volume character arc review
- `FULL_BOOK_CHARACTER_ARC_REVIEW_PROMPT` — full-book character arc review with cross-volume
- `FINAL_POLISH_PROMPT` — rewrite existing (currently just placeholder)

### Step 5: Commit

---

## Task 8: Cross-Volume Warning Checks

### Step 1: Add 3 cross-volume warning methods to WarningService

```python
def check_cross_volume_subplot_overdue(self, current_volume: int) -> Optional[dict]:
    """跨卷支线超期：交汇点后2卷未交汇 → 🟡"""

def check_character_state_jump(self, current_volume: int) -> Optional[dict]:
    """角色状态跳变：跨卷角色状态无铺垫 → 🟡"""

def check_long_term_foreshadowing_overdue(self, current_volume: int) -> Optional[dict]:
    """长期伏笔超期：预期回收卷后2卷未回收 → 🟡"""
```

### Step 2: Modify check_all signature

```python
def check_all(self, current_chapter: int, current_volume: int = 1) -> list[dict]:
    # ... existing checks ...
    if current_volume > 1:
        checks.extend([
            self.check_cross_volume_subplot_overdue(current_volume),
            self.check_character_state_jump(current_volume),
            self.check_long_term_foreshadowing_overdue(current_volume),
        ])
```

### Step 3: Update post_write_summary_node call

In `post_write_summary_node`, pass `current_volume` to `check_all()`:
```python
current_volume = state.get("current_volume", 1)
warnings = warning_service.check_all(written_chapter_num, current_volume)
```

### Step 4: Commit

---

## Task 9: SSE Events for Volume Operations

### Step 1: Add volume event types

In `backend/app/agents/sse_events.py`:
```python
def format_volume_transition(data: dict) -> str:
    """Format volume transition event"""

def format_volume_review(data: dict) -> str:
    """Format per-volume revision report event"""

def format_revision_report(data: dict) -> str:
    """Format full-book revision report event"""
```

### Step 2: Commit

---

## Task 10: Frontend — Volume Management + Revision Report

### Step 1: Create VolumePanel component

`frontend/src/components/workbench/VolumePanel.tsx`:
- Volume list with chapter ranges
- Volume status indicators (active/completed)
- Cross-volume tracking summary

### Step 2: Create RevisionReport component

`frontend/src/components/workbench/RevisionReport.tsx`:
- Revision results from structural_review + character_arc_review + final_polish
- Issue severity badges
- Accept/reject suggestions

### Step 3: Integrate into WorkbenchLayout

- Add VolumePanel to structure tab
- Add RevisionReport panel during revision phase

### Step 4: Commit

---

## Task 11: Integration Tests + Docker Rebuild

### Step 1: Create test file

`backend/tests/test_phase4.py` — test all new functionality.

### Step 2: Rebuild Docker + run migration

```bash
docker compose build backend
docker compose up -d backend
docker compose exec backend alembic upgrade head
```

### Step 3: Run tests + verify backend health

### Step 4: Final commit

---

## Execution Order

1. Task 1 (Models + Migration) — foundation
2. Task 2 (NovelState) — small, depends on Task 1 for ConfirmationType
3. Task 3 (KnowledgeBaseService) — depends on Task 1 models
4. Task 4 (Dual-Tier Retrieval) — depends on Task 3
5. Task 5 (Volume Transition Node) — depends on Tasks 1-4
6. Task 6 (Graph Integration) — depends on Task 5
7. Task 7 (Enhanced Revision) — depends on Tasks 1-3, 6
8. Task 8 (Cross-Volume Warnings) — depends on Task 1
9. Task 9 (SSE Events) — independent, can parallel with Tasks 5-8
10. Task 10 (Frontend) — depends on Tasks 5, 7, 9
11. Task 11 (Tests + Docker) — after all implementation
