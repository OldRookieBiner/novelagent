# Writing Panel Layout Optimization & Agent Capability Gap-fill -- Design Doc

Date: 2026-06-05
Status: Confirmed
Supersedes: docs/superpowers/specs/2026-06-04-writing-panel-layout-optimization-design.md

## Discovery

Audit confirmed Agent WRITING_TOOLS has no review/rewrite tools.
`propose_chapter_rewrite` only creates a proposal record -- it never
executes a rewrite. The review panel's backend endpoints
(`chapters.py:792`, `chapters.py:985`) call `llm.chat_stream()`
directly in route handlers, violating the AGENTS.md hard constraint:
"LLM calls MUST go through LangGraph nodes."

## Solution

Three phases: fill the Agent capability gap (new tools), then remove
redundant UI panels.

### 1. New Agent Tool: review_chapter

Add `review_chapter` tool so Agent can perform 6-dimension quality
review on any chapter.

**Implementation**:
- Read `project_id`, `model_config_id`, `user_id` from `tool_context`
- Create `LLMService` via `resolve_llm_service()`
- Reuse `agents/nodes/review.py` shared functions:
  `_build_review_messages()` + `parse_review_result()`
- Use `llm.chat()` non-streaming (tool mode, no SSE needed)
- Write review result to DB
- Return structured result: `{passed, scores, issues, suggestions}`

### 2. New Agent Tool: rewrite_chapter

Add `rewrite_chapter` tool so Agent can rewrite a chapter based on
review feedback.

**Implementation**:
- Read existing `review_feedback` from DB (review must exist first)
- Reuse `agents/nodes/rewrite.py` shared functions:
  `_build_rewrite_messages()` + `clean_chapter_content()`
- Non-streaming LLM call to generate new content
- Update `Chapter.content`, increment `rewrite_count`, clear `review_*` fields
- Return: `{action, chapter_number, word_count, message}`

### 3. WorkbenchLayout Left Sidebar: hide on writing tab

In `ProjectWorkbench.tsx`, change `showChapterList` condition from
`activeTab === 'writing' || activeTab === 'tracking'` to
`activeTab === 'tracking'`.

### 4. AIAssistantPanel: remove

Delete all AIAssistantPanel-related code from `WritingPanel.tsx`.

### Preserved

- `AIAssistantPanel.tsx` file kept but no longer rendered
- `chapters.py` review/rewrite endpoints preserved
- `agents/nodes/review.py` and `agents/nodes/rewrite.py` shared
  functions unchanged (Agent tools reuse them)
- All existing type definitions unchanged

## Impact

- Backend: 2 new Agent tools, ~150 lines added to `agent_tools.py`
- Frontend: `ProjectWorkbench.tsx` 1 line, `WritingPanel.tsx` ~120 lines,
  `creation/index.ts` 1 line
- No store changes, no new dependencies

## Verification

1. Agent panel: "review chapter 3" -> Agent calls `review_chapter` tool
2. Agent panel: "rewrite chapter 3" -> Agent calls `rewrite_chapter` tool
3. Writing tab: no outer left sidebar, no review panel
4. Tracking tab: left sidebar still visible
5. Core writing functions intact
