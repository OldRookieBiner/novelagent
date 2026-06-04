# Writing Panel Layout Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two redundant panels from the writing tab: WorkbenchLayout outer left sidebar (writing tab only) and WritingPanel AIAssistantPanel right sidebar (functionality fully covered by Agent).

**Architecture:** Pure deletion — no new files, no new logic. Three files modified, zero tests affected (no existing tests for these components).

**Tech Stack:** React + TypeScript + Zustand

---

### Task 1: Remove outer left sidebar from writing tab

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

This removes the outer `ChapterListPanel` from the writing tab while preserving it for the tracking tab.

- [ ] **Step 2: Build and verify no compile errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectWorkbench.tsx
git commit -m "refactor(frontend): remove outer left sidebar from writing tab"
```

---

### Task 2: Remove AIAssistantPanel from WritingPanel

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`
- Modify: `frontend/src/components/workbench/creation/index.ts`

- [ ] **Step 1: Remove imports**

Delete lines 10 and 14-15:

```tsx
// Delete line 10:
import { AIAssistantPanel } from './AIAssistantPanel'

// Delete line 14 (ReviewResponse no longer needed):
import type { ChapterOutline, Chapter, ReviewResponse } from '@/types'
// becomes:
import type { ChapterOutline, Chapter } from '@/types'

// Delete line 15:
import { mapReviewResult } from '@/types'
```

- [ ] **Step 2: Remove review-related state and refs (lines 117-121)**

Delete:

```tsx
const [rightCollapsed, setRightCollapsed] = useState(false)
const [rewriting, setRewriting] = useState(false)
```

and:

```tsx
const rewriteAccumulatedRef = useRef('')
```

- [ ] **Step 3: Remove handleRewriteChunk callback (lines ~388-399)**

Delete the entire `handleRewriteChunk` useCallback block.

- [ ] **Step 4: Remove handleRewriteDone callback (lines ~401-424)**

Delete the entire `handleRewriteDone` useCallback block.

- [ ] **Step 5: Remove handleReviewCleared callback (lines ~426-437)**

Delete the entire `handleReviewCleared` useCallback block.

- [ ] **Step 6: Remove handleReviewComplete callback (lines ~440-456)**

Delete the entire `handleReviewComplete` useCallback block.

- [ ] **Step 7: Remove initialReviewResultMemo (lines ~458-461)**

Delete:

```tsx
const initialReviewResultMemo = useMemo(
  () => chapterContent ? mapReviewResult(chapterContent.review_result) : null,
  [chapterContent?.review_result]
)
```

Also remove `useMemo` from the React import on line 1 if it is no longer used. At this point `useMemo` is still used for `wordCount` (line ~488), so keep it.

- [ ] **Step 8: Remove handleIssueClick callback (lines ~465-483)**

Delete the entire `handleIssueClick` useCallback block.

- [ ] **Step 9: Remove AIAssistantPanel JSX (the entire <AIAssistantPanel .../> block)**

Delete lines ~754-767:

```tsx
<AIAssistantPanel
  key={selectedChapter?.chapter_number}
  projectId={projectId}
  chapterNumber={selectedChapter?.chapter_number}
  chapterContent={content}
  initialReviewResult={initialReviewResultMemo}
  onReviewComplete={handleReviewComplete}
  onRewriteChunk={handleRewriteChunk}
  onRewriteDone={handleRewriteDone}
  onReviewCleared={handleReviewCleared}
  onIssueClick={handleIssueClick}
  collapsed={rightCollapsed}
  onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
/>
```

- [ ] **Step 10: Remove AIAssistantPanel from creation/index.ts barrel export**

In `frontend/src/components/workbench/creation/index.ts`, delete line 6:

```tsx
export { AIAssistantPanel } from './AIAssistantPanel'
```

- [ ] **Step 11: Build and verify no compile errors**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 12: Run existing tests**

```bash
cd frontend && npm run test:run
```

Expected: all existing tests pass (no writing panel tests exist, but ensure no import chain breaks).

- [ ] **Step 13: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx frontend/src/components/workbench/creation/index.ts
git commit -m "refactor(frontend): remove AIAssistantPanel from WritingPanel"
```

---

### Task 3: Remove unused ChapterNodePanel import cleanup (if orphaned)

**Files:**
- Check: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: Verify ChapterNodePanel import still needed**

`ChapterNodePanel` is used in `handleGenerate` for the chapter node confirmation card (line ~196-204). It is still needed. No action required.

- [ ] **Step 2: Mark task complete — no changes**

---

### Task 4: Docker rebuild and smoke test

- [ ] **Step 1: Rebuild frontend**

```bash
docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 2: Verify in browser**

Open the app and navigate to a project's writing tab.

Verify:
- No outer left sidebar (only WritingPanel's own chapter list on the far left)
- No right review panel
- Chapter list, editor, AI generate, save — all functional
- Switching tabs (knowledge, structure, tracking) works correctly
- Right-side Agent panel still functional
- Tracking tab still shows the outer ChapterListPanel

- [ ] **Step 3: Commit (if any config changes needed)**

Only if docker config changes are needed; otherwise move on.
PLANEOF</｜DSML｜parameter>
<｜DSML｜parameter name=