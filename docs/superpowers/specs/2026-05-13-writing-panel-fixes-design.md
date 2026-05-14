# 章节正文生成状态持久化与校验优化设计

## 问题概述

### 问题1：章节正文生成时切换标签页丢失状态

**现象**：章节正文正在流式生成时，切换到其他标签页再切回来，生成状态被清除（进度条消失、已生成的文本丢失、按钮恢复为"AI 生成"）。

**根因**：`WritingPanel` 使用组件内 `useState` 管理 SSE 流状态（`generating`、`generatingChapterId`、`abortControllerRef`），标签页切换时组件卸载，`useEffect` cleanup 调用 `abortControllerRef.current.abort()` 终止 SSE 流，所有状态随组件销毁丢失。

**代码路径**：
- `WritingPanel.tsx:85-86` — `const [generating, setGenerating] = useState(false)`
- `WritingPanel.tsx:89` — `const [generatingChapterId, setGeneratingChapterId] = useState<number | null>(null)`
- `WritingPanel.tsx:86` — `const abortControllerRef = useRef<AbortController | null>(null)`
- `WritingPanel.tsx:160-169` — useEffect cleanup 中 abort SSE
- `ProjectWorkbench.tsx:34-35` — 标签页切换时组件直接卸载

**与章节大纲的对比**：`ChapterOutlinePanel` 已通过 `workflowStore` 持久化生成状态（参考 `2026-05-12-workbench-state-persistence-design.md`），切换标签后能恢复。`WritingPanel` 缺少同样的处理。

---

### 问题2：章节正文可跳章生成

**现象**：生成第1章后，可以跳过第2章直接生成第3章。章节正文应按序生成（前一章已生成才能生成下一章），因为后文依赖前文上下文。

**根因**：
1. **后端**：`generate_chapter` API（chapters.py:574）仅校验 `chapter_outline.confirmed`（大纲是否确认），未校验前序章节是否已生成正文。
2. **前端**：`WritingPanel.handleGenerate`（WritingPanel.tsx:206）未做前序章节检查，所有已确认大纲的章节都可点击生成。

**代码路径**：
- `backend/app/api/chapters.py:607-611` — 仅检查 `chapter_outline.confirmed`
- `WritingPanel.tsx:210-213` — 仅检查 `selectedChapter.confirmed`

---

### 问题3：审核未通过但反馈意见不显示

**现象**：对已生成章节执行审核，审核未通过时，右侧审核面板显示"未通过"状态，但反馈意见和问题列表为空或显示 `[object Object]`。

**根因**：
1. **后端**：`chapters.py:846` 存储 `review_feedback = review_result.get("raw_response")`（LLM 完整原始输出），`chapters.py:853` 返回 `feedback: ch.review_feedback`（原始输出文本，可能包含 JSON 格式）。
2. **前端**：`AIAssistantPanel.tsx:154-159` 渲染 `reviewResult.issues.map((issue, index) => <span>{issue}</span>)`，但后端返回的 `issues` 是对象数组 `[{"type": "AI味", "location": "第三段", "description": "..."}]`，React 无法直接渲染对象，显示 `[object Object]`。
3. **类型不匹配**：前端 `ReviewResponse.issues: string[]`，但后端返回 `issues: dict[]`。

**代码路径**：
- `backend/app/agents/nodes/review.py:26` — `issues: data.get("issues", [])` 返回对象数组
- `backend/app/api/chapters.py:854` — `"issues": review_result.get("issues", [])` 直接透传对象数组
- `frontend/src/types/index.ts:209` — `issues: string[]` 类型声明
- `frontend/src/components/workbench/creation/AIAssistantPanel.tsx:154-159` — `{issue}` 直接渲染

---

## 设计方案

### 问题1修复：章节正文 SSE 状态提升到 workflowStore

**核心理念**：与章节大纲一致，将 SSE 流管理从组件内提升到 `workflowStore`，使 SSE 生命周期与组件解耦。

**架构变化**：

```
当前架构（问题根因）：
WritingPanel (组件内部)
├── AbortController (组件局部 ref)
├── useState: generating, generatingChapterId
├── SSE 回调 → 更新本地 state (content, chapterContent)
└── useEffect cleanup → abort() 终止 SSE
→ 标签页切换 → 组件卸载 → SSE 流断开 → 状态丢失

改进后架构：
workflowStore (全局 store)
├── state: writingChapterGenerating, writingGeneratingChapterId
└── (组件卸载不触发 abort)
WritingPanel (组件)
├── AbortController 仍在组件内（useRef）
├── 从 store 读取 generating 状态
├── SSE 启动/回调仍保留在组件内（content 是 UI 数据，与编辑器绑定）
└── 组件挂载时从 store 恢复状态，从 API 恢复内容
→ 标签页切换 → 组件卸载 → Store 保留 → SSE 自然断开 → 状态标记可恢复
```

**新增 workflowStore 状态**：

| 状态 | 类型 | 说明 |
|------|------|------|
| `writingChapterGenerating` | `boolean` | 是否正在生成章节正文 |
| `writingGeneratingChapterId` | `number \| null` | 正在生成的章节 ID |

**新增 workflowStore actions**：

| Action | 说明 |
|--------|------|
| `setWritingChapterGenerating(generating: boolean)` | 设置生成状态 |
| `setWritingGeneratingChapterId(id: number \| null)` | 设置正在生成的章节 ID |
| `clearWritingGenerationState()` | 清理生成状态（生成完成后调用） |

注：AbortController 保留在组件内（用 `useRef` 管理），不存入 store。原因：SSE 回调需要访问组件闭包中的 `setContent` 等状态，AbortController 的生命周期应与组件绑定。store 只管理"是否在生成"的标记。SSE 流的启动（`createSSEStream`）和回调（`onChunk`/`onDone`）也保留在组件内。

**WritingPanel 修改**：

1. 移除本地 `generating`、`generatingChapterId` 状态（改为从 store 读取）
2. 保留 `abortControllerRef`（AbortController 仍在组件内管理）
3. 从 store 读取：`const { generating, generatingChapterId } = useWorkflowStore(useShallow(...))`
4. `handleGenerate` 中将 `setGenerating`/`setGeneratingChapterId` 替换为 `setWritingChapterGenerating`/`setWritingGeneratingChapterId`
5. **移除** useEffect cleanup 中的 `abort()` 调用
6. 组件挂载时检查 store 中 `writingChapterGenerating`，为 true 则从后端刷新当前章节内容恢复显示

**组件挂载恢复逻辑**：

- 挂载时检查 `writingChapterGenerating`
  - 为 `true`：说明上次生成可能中断（组件卸载后 SSE 回调无法传递到新实例）。此时应：1) 清除生成标记 `writingChapterGenerating = false` 2) 从后端 API 获取已保存的内容（如果生成完成则后端已原子写入）3) 如果 API 返回空内容，说明生成中断未完成，提示用户"生成因切换页面中断，请重新生成"
  - 为 `false`：正常初始化，从后端获取章节内容

**关键设计决策**：
- AbortController 保留在组件内（`useRef`），不存入 store。原因：SSE 回调需要访问组件闭包中的 `setContent` 等状态，AbortController 的生命周期应与组件绑定。章节大纲的 AbortController 存入 store 是因为其 SSE 回调不依赖组件闭包
- SSE 流在组件卸载后会自然断开（浏览器 fetch 连接关闭），不会产生幽灵请求
- Store 只管理"是否在生成"的标记，确保切换标签后能看到正确状态

---

### 问题2修复：章节正文按序生成校验

**后端校验**：

在 `generate_chapter` API 中增加前序章节校验：

```python
# chapters.py generate_chapter() 内，confirmed 校验之后增加：
if chapter_num > 1:
    prev_outline = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_num - 1
    ).first()
    if prev_outline:
        prev_chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == prev_outline.id
        ).first()
        if not prev_chapter or not prev_chapter.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Please generate chapter {chapter_num - 1} first"
            )
```

**前端校验**：

1. `WritingPanel` 中新增计算函数，判断章节是否可生成：

```typescript
function canGenerateChapter(chapter: ChapterOutline, chapters: ChapterOutline[]): boolean
{
  if (!chapter.confirmed) return false
  if (chapter.chapter_number === 1) return true
  const prevChapter = chapters.find(c => c.chapter_number === chapter.chapter_number - 1)
  return prevChapter?.has_content === true
}
```

2. 章节列表中，不可生成的章节显示为禁用态（灰色文字 + tooltip 提示原因）
3. `handleGenerate` 开头增加 `canGenerateChapter` 校验，不满足时 toast 提示

---

### 问题3修复：审核反馈显示修复

**后端修改**：

1. `chapters.py` review 端点的 `done` 事件中，`feedback` 字段返回 `suggestions`（已解析的修改建议），而非 `raw_response`：

```python
result_data = {
    "passed": ch.review_passed if ch else False,
    "feedback": review_result.get("suggestions", ""),  # 修改建议，非原始输出
    "issues": review_result.get("issues", []),  # 可能为 string[] 或 dict[]，前端已兼容
    "scores": review_result.get("scores", {}),   # 可能为空，前端已兼容
}
```

2. `review_feedback` 字段继续存储 `raw_response`（保留完整数据供后续分析），但 `feedback` API 返回值改为 `suggestions`。

**前端修改**：

1. 更新 `ReviewResponse` 类型定义：

```typescript
// 兼容后端两种格式：JSON 返回 {type,location,description}，旧格式返回 string
export interface ReviewIssue {
  type?: string
  location?: string
  description: string  // 必填：旧格式时整个 issue 作为 description
}

export interface ReviewResponse {
  passed: boolean
  feedback: string
  issues: ReviewIssue[]
  scores?: Record<string, number>  // 可选，旧格式可能无此字段
}
```

2. `AIAssistantPanel.tsx` 中 issues 渲染改为结构化显示，兼容 string 和 object 两种格式：

```tsx
{reviewResult.issues.map((issue, index) => {
  // 兼容：后端旧格式 issues 是 string[]，新格式是 ReviewIssue[]
  const description = typeof issue === 'string' ? issue : issue.description
  const type = typeof issue === 'string' ? '' : issue.type
  const location = typeof issue === 'string' ? '' : issue.location
  return (
    <div key={index} className="...">
      <AlertCircle className="..." />
      <span className="...">
        {type ? `[${type}] ` : ''}{location ? `${location}：` : ''}{description}
      </span>
    </div>
  )
})}
```

3. 新增评分展示区域（可选，优先级低）：

```tsx
{reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
  <div className="...">
    <span className="...">评分详情</span>
    {Object.entries(reviewResult.scores).map(([key, value]) => (
      <div key={key}>{SCORE_LABELS[key]}：{value}/10</div>
    ))}
  </div>
)}
```

4. 兼容旧格式：issues 中如果元素是 string 而非 object，降级显示为纯文本。

---

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/stores/workflowStore.ts` | 新增章节正文生成状态和 actions |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 本地状态替换为 store；移除 useEffect abort；增加按序生成校验 |
| `frontend/src/types/index.ts` | 更新 ReviewResponse 类型（issues 改为结构化、新增 scores） |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | issues 结构化渲染；兼容旧格式；新增评分展示 |
| `backend/app/api/chapters.py` | generate_chapter 增加前序章节校验；review done 事件反馈字段修正 |

---

## 改动评估

| 维度 | 评估 |
|------|------|
| 改动文件数 | 5 个（4 前端 + 1 后端） |
| 后端改动 | chapters.py 增加1个校验 + 修改1个返回字段 |
| API 层改动 | generate_chapter 增加校验逻辑；review done 事件字段调整 |
| LangGraph 节点改动 | 无（review.py、chapter_generation.py 不变） |
| 其他面板影响 | 无 |
| 用户操作流程 | 完全不变，只是修复了3个 bug |
| 系统稳定性 | 低风险，校验逻辑为纯增量、状态提升与已有模式一致 |

---

## 不涉及的变更

- LangGraph 节点逻辑不变（review_node、generate_chapter_content_stream 等）
- SSE 事件格式不变（仍为 chunk/done/error）
- API 端点路径不变
- 数据库 schema 不变
- Prompt 模板不变
