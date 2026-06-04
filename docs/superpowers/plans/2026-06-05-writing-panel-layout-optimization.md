# Writing Panel Layout Optimization -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add review_chapter and rewrite_chapter Agent tools to fill the capability gap, then remove the redundant AIAssistantPanel and WorkbenchLayout outer sidebar from the writing tab.

**Architecture:** Two new Agent tools reuse existing shared functions from `agents/nodes/review.py` and `agents/nodes/rewrite.py`. Frontend changes are pure deletions.

**Tech Stack:** Python/FastAPI/LangChain + React/TypeScript

---

### Task 1: Add review_chapter Agent tool

**Files:**
- Modify: `backend/app/agents/agent_tools.py`

- [ ] **Step 1: Add imports at the top of agent_tools.py**

After line 17 (`from app.agents.services.retrieval import RetrievalService`), add:

```python
from app.agents.tool_context import get_model_config_id, get_user_id
from app.utils.llm import resolve_llm_service
from app.agents.constants import NODE_TEMPERATURES
from app.agents.nodes.review import _build_review_messages, parse_review_result, check_review_passed
```

- [ ] **Step 2: Add _build_state_for_review helper function**

Before the review_chapter tool function, add:

```python
def _build_state_for_review(project_id: int, chapter_number: int) -> dict:
    """Build a minimal NovelState dict for review message construction.

    Reads characters, relations, world_setting, chapter_outlines, written_chapters
    from KnowledgeBaseService to satisfy the _build_review_messages contract.
    """
    kb = KnowledgeBaseService(project_id)

    # Outline for chapter_count and context window
    outline = kb.get_outline()
    target_words = 100000
    if outline:
        target_words = (outline.chapter_count_confirmed or outline.chapter_count_suggested or 100) * 3000

    # Characters
    chars_raw = kb.get_characters()
    characters = []
    for c in chars_raw:
        characters.append({
            "id": c.id, "name": c.name, "role": getattr(c, "role", ""),
            "personality": getattr(c, "personality", ""),
            "appearance": getattr(c, "appearance", ""),
            "backstory": getattr(c, "backstory", ""),
            "catchphrase": getattr(c, "catchphrase", ""),
            "habit_action": getattr(c, "habit_action", ""),
            "deep_fear": getattr(c, "deep_fear", ""),
            "core_motivation": getattr(c, "core_motivation", ""),
            "growth_arc": getattr(c, "growth_arc", ""),
            "signature_item": getattr(c, "signature_item", ""),
        })

    # Relations
    relations_raw = kb.get_relations()
    relations = []
    for r in relations_raw:
        relations.append({
            "character_a_id": getattr(r, "character_a_id", None),
            "character_b_id": getattr(r, "character_b_id", None),
            "relation_type": getattr(r, "relation_type", ""),
            "current_status": getattr(r, "current_status", ""),
        })

    # Evolution plans
    evolution_plans_raw = kb.get_relations_with_plans()
    evolution_plans = []
    for ep in evolution_plans_raw:
        evolution_plans.append(ep if isinstance(ep, dict) else _serialize(ep))

    # World setting
    ws = kb.get_world_setting()

    # Chapter outlines
    chapter_outlines = []
    from app.models.outline import ChapterOutline
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        co_list = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number).all()
        for co in co_list:
            chapter_outlines.append({
                "chapter_number": co.chapter_number,
                "title": co.title or "",
                "scene": co.scene,
                "characters": co.characters,
                "plot": co.plot or "",
                "conflict": co.conflict,
                "turning_point": co.turning_point,
                "hook": co.hook,
                "transition": co.transition,
                "ending": co.ending,
                "target_words": co.target_words,
            })
    finally:
        db.close()

    # Written chapters (content summaries for context)
    timeline = kb.get_timeline()
    written_chapters = []
    for t in timeline:
        written_chapters.append({
            "chapter_number": t.chapter_number,
            "summary": getattr(t, "summary", ""),
        })

    # Collected info (style preferences, etc.)
    collected_info = {}
    if outline:
        collected_info["novelType"] = getattr(outline, "novel_type", "") or ""
    style = kb.get_style_constraints()
    if style:
        collected_info["stylePreference"] = getattr(style, "style_preference", "") or ""
    collected_info["targetWords"] = target_words

    # Load custom prompts from DB
    _prompts = {}
    try:
        db2 = SessionLocal()
        try:
            from app.models.system_prompt import SystemPrompt
            prompts = db2.query(SystemPrompt).all()
            for p in prompts:
                _prompts[p.node_name] = {"system": p.system_prompt, "user": p.user_prompt}
        finally:
            db2.close()
    except Exception:
        pass

    if not _prompts:
        from app.agents.prompts import DEFAULT_PROMPTS
        _prompts = DEFAULT_PROMPTS

    return {
        "project_id": project_id,
        "current_chapter": chapter_number,
        "characters": characters,
        "relations": relations,
        "evolution_plans": evolution_plans,
        "evolution_records": [],
        "world_setting": _serialize(ws) if ws else {},
        "chapter_outlines": chapter_outlines,
        "written_chapters": written_chapters,
        "collected_info": collected_info,
        "_prompts": _prompts,
        "_context_window": 32000,
    }
```

- [ ] **Step 3: Add review_chapter tool function**

Add after the _build_state_for_review helper:

```python
@tool
async def review_chapter(chapter_number: int) -> dict:
    """Review a chapter for quality across 6 dimensions.

    Performs a comprehensive quality review analyzing plot consistency,
    character consistency, writing quality, emotional tension, AI flavor,
    and outline deviation. Results are saved to the database.

    Args:
        chapter_number: The chapter number to review (e.g., 1, 2, 3)
    """
    project_id = get_project_id()
    model_config_id = get_model_config_id()
    user_id = get_user_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Resolve LLM service
    from app.services.llm import LLMService
    try:
        llm = resolve_llm_service(model_config_id, user_id)
    except ValueError as e:
        return {"error": f"无法获取 LLM 配置: {e}"}

    # Read chapter from DB
    kb = KnowledgeBaseService(project_id)
    chapter = kb.get_chapter_by_number(chapter_number)
    if not chapter or not chapter.content:
        return {"error": f"第{chapter_number}章不存在或没有内容"}

    # Get chapter outline
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"第{chapter_number}章大纲不存在"}
        chapter_outline_dict = {
            "chapter_number": co.chapter_number,
            "title": co.title or "",
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot or "",
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        chapter_outline_id = co.id
    finally:
        db.close()

    # Build state for review message construction
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_review_messages(state, chapter.content, chapter_outline_dict)
    try:
        response = await llm.chat(messages, temperature=NODE_TEMPERATURES["review"])
        review_result = parse_review_result(response)
        review_result["raw_response"] = response
        passed = check_review_passed(review_result)
    except Exception as e:
        return {"error": f"审核 LLM 调用失败: {e}"}

    # Save to DB
    from app.models.chapter import Chapter
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(
            Chapter.chapter_outline_id == chapter_outline_id
        ).first()
        if ch:
            ch.review_passed = passed
            ch.review_feedback = response
            ch.review_result = review_result
            save_db.commit()
            committed = True
    except Exception as e:
        return {"error": f"保存审核结果失败: {e}"}
    finally:
        if not committed:
            try:
                save_db.rollback()
            except Exception:
                pass
        try:
            save_db.close()
        except Exception:
            pass

    return {
        "chapter_number": chapter_number,
        "passed": passed,
        "scores": review_result.get("scores", {}),
        "issues": review_result.get("issues", []),
        "suggestions": review_result.get("suggestions", ""),
        "message": f"审核{'通过' if passed else '未通过'}，"
                   f"发现 {len(review_result.get('issues', []))} 个问题",
    }
```

- [ ] **Step 4: Add review_chapter to WRITING_TOOLS**

In the WRITING_TOOLS list, after `foreshadowing_check`, add:

```python
    review_chapter,
```

- [ ] **Step 5: Verify syntax**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_tools import WRITING_TOOLS; print(f'WRITING_TOOLS count: {len(WRITING_TOOLS)}')"
```

Expected: no errors, count increased by 1.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(agent): add review_chapter tool"
```

### Task 2: Add rewrite_chapter Agent tool

**Files:**
- Modify: `backend/app/agents/agent_tools.py`

- [ ] **Step 1: Add imports needed for rewrite tool**

Add to the imports block at the top of agent_tools.py (alongside review imports from Task 1):

```python
from app.agents.nodes.rewrite import _build_rewrite_messages, clean_chapter_content
```

- [ ] **Step 2: Add rewrite_chapter tool function**

Add before the "Helper functions" section marker:

```python
@tool
async def rewrite_chapter(chapter_number: int) -> dict:
    """Rewrite a chapter based on its latest review feedback.

    The chapter must have been reviewed first (review_feedback must exist).
    Generates new content, saves it to the database, increments rewrite_count,
    and clears the review state so it can be re-reviewed.

    Args:
        chapter_number: The chapter number to rewrite (e.g., 1, 2, 3)
    """
    project_id = get_project_id()
    model_config_id = get_model_config_id()
    user_id = get_user_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Resolve LLM service
    try:
        llm = resolve_llm_service(model_config_id, user_id)
    except ValueError as e:
        return {"error": f"无法获取 LLM 配置: {e}"}

    # Read chapter from DB
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.models.chapter import Chapter

    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"第{chapter_number}章大纲不存在"}

        chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == co.id
        ).first()
        if not chapter or not chapter.content:
            return {"error": f"第{chapter_number}章不存在或没有内容"}

        # Must have review feedback
        review_feedback = ""
        if chapter.review_result:
            review_feedback = (
                chapter.review_result.get("raw_response", "")
                or chapter.review_result.get("suggestions", "")
            )
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback
        if not review_feedback:
            return {"error": f"第{chapter_number}章尚未审核，请先使用 review_chapter 工具审核"}

        chapter_outline_dict = {
            "chapter_number": co.chapter_number,
            "title": co.title or "",
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot or "",
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        original_content = chapter.content
        chapter_id = chapter.id
        chapter_outline_id = co.id
    finally:
        db.close()

    # Build state
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_rewrite_messages(
        state, chapter_outline_dict, original_content, review_feedback
    )
    try:
        response = await llm.chat(
            messages,
            temperature=NODE_TEMPERATURES["rewrite"],
            max_tokens=16384,
        )
        new_content = clean_chapter_content(response)
    except Exception as e:
        return {"error": f"重写 LLM 调用失败: {e}"}

    # Save to DB
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if ch:
            ch.content = new_content
            ch.word_count = len(new_content)
            ch.rewrite_count = (ch.rewrite_count or 0) + 1
            ch.review_passed = False
            ch.review_result = None
            ch.review_feedback = None
            save_db.commit()
            committed = True
            word_count = len(new_content)
        else:
            return {"error": "章节已被删除"}
    except Exception as e:
        return {"error": f"保存重写结果失败: {e}"}
    finally:
        if not committed:
            try:
                save_db.rollback()
            except Exception:
                pass
        try:
            save_db.close()
        except Exception:
            pass

    return {
        "action": "rewritten",
        "chapter_number": chapter_number,
        "word_count": word_count,
        "message": f"第{chapter_number}章已重写（{word_count}字），请重新审核",
    }
```

- [ ] **Step 3: Add rewrite_chapter to WRITING_TOOLS**

In the WRITING_TOOLS list, after `review_chapter`, add:

```python
    rewrite_chapter,
```

- [ ] **Step 4: Verify syntax**

```bash
docker exec novelagent-backend-1 python -c "from app.agents.agent_tools import WRITING_TOOLS; print(f'WRITING_TOOLS count: {len(WRITING_TOOLS)}')"
```

Expected: no errors, count increased by 1 more (total +2 from baseline).

- [ ] **Step 5: Run backend tests**

```bash
docker exec novelagent-backend-1 pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/agent_tools.py
git commit -m "feat(agent): add rewrite_chapter tool"
```

### Task 3: Remove outer left sidebar from writing tab

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx:107`

- [ ] **Step 1: Change showChapterList condition**

On line 107 of `ProjectWorkbench.tsx`, change:

```tsx
const showChapterList = activeTab === 'writing' || activeTab === 'tracking'
```

to:

```tsx
const showChapterList = activeTab === 'tracking'
```

- [ ] **Step 2: Build and verify no compile errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx
git commit -m "refactor(frontend): hide outer left sidebar on writing tab"
```

---

### Task 4: Remove AIAssistantPanel from WritingPanel

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`
- Modify: `frontend/src/components/workbench/creation/index.ts`

- [ ] **Step 1: Remove imports**

Delete these lines from the imports block (near lines 1-15):

```tsx
// Delete line 10:
import { AIAssistantPanel } from './AIAssistantPanel'

// Delete line 15 (mapReviewResult import):
import { mapReviewResult } from '@/types'

// On line 14, remove ReviewResponse from the type import:
// Change: import type { ChapterOutline, Chapter, ReviewResponse } from '@/types'
// To:     import type { ChapterOutline, Chapter } from '@/types'
```

- [ ] **Step 2: Remove review-related state and refs**

Delete these state declarations (lines ~117-118, ~121):

```tsx
const [rightCollapsed, setRightCollapsed] = useState(false)
const [rewriting, setRewriting] = useState(false)
```

Delete:

```tsx
const rewriteAccumulatedRef = useRef('')
```

- [ ] **Step 3: Remove callback functions**

Delete these entire callback blocks:
- `handleRewriteChunk` (lines ~388-399)
- `handleRewriteDone` (lines ~401-424)
- `handleReviewCleared` (lines ~426-437)
- `handleReviewComplete` (lines ~440-456)
- `initialReviewResultMemo` (lines ~458-461)
- `handleIssueClick` (lines ~465-483)

- [ ] **Step 4: Remove AIAssistantPanel JSX**

Delete the `<AIAssistantPanel .../>` block (lines ~754-767).

- [ ] **Step 5: Update creation/index.ts barrel export**

Delete this line from `frontend/src/components/workbench/creation/index.ts`:

```tsx
export { AIAssistantPanel } from './AIAssistantPanel'
```

- [ ] **Step 6: Build and verify no compile errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 7: Run frontend tests**

```bash
cd frontend && npm run test:run 2>&1 | tail -20
```

Expected: all existing tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx frontend/src/components/workbench/creation/index.ts
git commit -m "refactor(frontend): remove AIAssistantPanel from WritingPanel"
```

---

### Task 5: Docker rebuild and smoke test

- [ ] **Step 1: Rebuild backend and frontend**

```bash
docker compose build --no-cache backend && docker compose build --no-cache frontend && docker compose up -d backend frontend
```

- [ ] **Step 2: Wait for services to start**

```bash
sleep 5 && docker compose ps
```

Expected: backend and frontend services are "Up".

- [ ] **Step 3: Verify backend health**

```bash
curl -s http://localhost:8000/api/health | head -5
```

- [ ] **Step 4: Open browser to verify UI**

Open http://localhost:3001, navigate to a project's writing tab.

Verify:
- No outer left sidebar (only WritingPanel's own chapter list)
- No right review panel
- Chapter list, editor, AI generate, save all functional
- Right-side Agent panel functional
- Switching to tracking tab shows outer ChapterListPanel
- Switching to other tabs (knowledge, structure) works correctly

- [ ] **Step 5: Smoke test Agent tools**

In the Agent panel, send: "审核第1章"
Expected: Agent calls `review_chapter` tool, returns review results.

Then send: "重写第1章"
Expected: Agent calls `rewrite_chapter` tool, rewrites chapter.

- [ ] **Step 6: Commit any remaining changes**

Only if any fixes are needed from smoke testing.
