# Phase 3: Semantic Retrieval + Writing Quality Polish

> **Goal:** Replace full-text loading with on-demand semantic retrieval, polish post-write checks and deep review, and add proactive warning mechanism.

**Architecture:** RetrievalService wraps FAISS+BM25 hybrid search (core logic from novelskills search.py, data source from DB instead of Markdown files). context_assembly_node uses RetrievalService for on-demand retrieval instead of loading all characters/settings. Post-write checks enhanced with knowledge boundary detection, foreshadowing 3-level progression enforcement, style drift detection. Deep review enhanced with timeline contradiction, foreshadowing overdue, rhythm monotone, setting violation, POV review. Proactive warnings pushed via SSE.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/requirements.txt` | Modify | Add faiss-cpu, sentence-transformers, jieba, rank-bm25, numpy |
| `backend/app/agents/services/retrieval.py` | Create | RetrievalService: FAISS+BM25 hybrid search from DB |
| `backend/app/agents/nodes/context_assembly.py` | Rewrite | Use RetrievalService for on-demand retrieval |
| `backend/app/agents/nodes/character_consistency.py` | Rewrite | Knowledge boundary detection + structured output |
| `backend/app/agents/nodes/tracking_update.py` | Rewrite | Foreshadowing 3-level progression enforcement |
| `backend/app/agents/nodes/style_check.py` | Rewrite | Add style drift detection |
| `backend/app/agents/nodes/deep_review.py` | Rewrite | Enhanced deep review with 6 dimensions + structured output |
| `backend/app/agents/services/warning.py` | Create | WarningService: proactive warning generation + SSE push |
| `backend/app/agents/sse_events.py` | Modify | Add warning subtype events |
| `backend/app/agents/prompts.py` | Modify | Add enhanced prompts for deep review, character consistency |
| `backend/tests/test_retrieval_service.py` | Create | RetrievalService unit tests |
| `backend/tests/test_phase3.py` | Create | Phase 3 integration tests |

---

### Task 1: Add Python Dependencies

- [ ] Step 1: Add faiss-cpu, sentence-transformers, jieba, rank-bm25, numpy to requirements.txt
- [ ] Step 2: Rebuild Docker image
- [ ] Step 3: Verify imports work inside container

### Task 2: RetrievalService

- [ ] Step 1: Create `backend/app/agents/services/retrieval.py` with:
  - `chunk_text()` — split text into chunks (from novelskills search.py)
  - `tokenize_chinese()` — jieba tokenization with bigram fallback
  - `RetrievalService` class:
    - `__init__(project_id)` — loads model lazily
    - `rebuild_index()` — read all KB data from DB, build FAISS+BM25 indices, save to `.index/{project_id}/`
    - `search(query, top_k=5)` — hybrid search: FAISS × 0.7 + BM25 × 0.3, time-decay for timeline
    - `mark_for_indexing(content)` — mark content with `<!-- 待索引 -->` (placeholder for incremental)
  - Data source: KnowledgeBaseService reads (world_setting, characters, foreshadowings, timeline, plot_blocks, style_constraints, scene_entries)
  - Index storage: `/tmp/novelagent_index/{project_id}/` (inside container)
- [ ] Step 2: Commit

### Task 3: Rewrite context_assembly_node

- [ ] Step 1: Replace full-text loading with RetrievalService.search()
  - Load: current plot block goal + style constraints (always)
  - Retrieve: involved characters + involved settings via semantic search
  - Check: pending foreshadowings + question chain
  - Remove: full get_characters() / get_world_setting() calls
- [ ] Step 2: Commit

### Task 4: Rewrite character_consistency_node — Knowledge Boundary Detection

- [ ] Step 1: Enhanced check:
  - For each character present in chapter, load their `knowledge_boundary`
  - LLM checks if any character reveals info outside their boundary
  - Structured output: list of violations with character name + violated boundary + quoted text
  - If violations found, write warning to DB and trigger SSE warning
- [ ] Step 2: Commit

### Task 5: Rewrite tracking_update_node — Foreshadowing 3-Level Progression

- [ ] Step 1: Enforce novelskills rules:
  - New foreshadowing → append (appearance_count=1, level="hint")
  - Re-mention → increment count, ≥2 and "hint" → upgrade to "strengthened"
  - Reclaim → confirm ≥2 and "strengthened" → mark "revealed" (not just "pending_reclaim")
  - Reclaim with <2 appearances → log warning (violates minimum progression)
  - Track: `appearance_count`, `level` (hint→strengthened→revealed), `status` (active→pending_reclaim→resolved)
- [ ] Step 2: Commit

### Task 6: Rewrite style_check_node — Style Drift Detection

- [ ] Step 1: Add drift detection:
  - After writing style stats, compare against baseline (first 3 chapters average, or style_anchor)
  - If dialogue_ratio deviates >25% from baseline → mark drift
  - If avg_sentence_length deviates >25% → mark drift
  - Write drift status to style snapshot
  - If drift detected, trigger SSE warning
- [ ] Step 2: Commit

### Task 7: Rewrite deep_review_node — 6-Dimension Enhanced Review

- [ ] Step 1: Enhanced review with structured output:
  - Timeline contradiction detection
  - Foreshadowing overdue check (with 2-block tolerance)
  - Rhythm monotone check (3+ chapters same emotion)
  - Setting violation check (🔴 setting breach)
  - Style drift check (last 10 chapters vs baseline)
  - POV review (non-POV inner thoughts, >3 POV switches per chapter)
  - Each dimension outputs: ✅/⚠️/❌ + specific issues
  - Review result stored in DB for frontend display
- [ ] Step 2: Commit

### Task 8: WarningService + Proactive Warning Mechanism

- [ ] Step 1: Create `backend/app/agents/services/warning.py`:
  - `WarningService.check_and_emit(project_id, chapter_number, event_type)`:
    - Foreshadowing overdue → 🟡 warning
    - Style drift detected → 🟡 warning
    - Setting conflict → 🔴 warning
    - Rhythm monotone → 🟡 warning
  - Warnings stored in a `warnings` list in memory per project (or DB table)
  - SSE push via existing `format_warning()` mechanism
- [ ] Step 2: Integrate WarningService calls into post-write nodes
- [ ] Step 3: Commit

### Task 9: Tests

- [ ] Step 1: RetrievalService unit tests (mocked DB, real FAISS/BM25)
- [ ] Step 2: Phase 3 integration tests
- [ ] Step 3: Run all tests + verify backend health
- [ ] Step 4: Final commit
