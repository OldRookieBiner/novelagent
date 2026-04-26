# 全面优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按架构去重→性能优化→安全健壮性→体验增强的顺序，全面优化 NovelAgent 代码库

**Architecture:** 四层渐进优化，每层独立可交付。L1 统一后端重复函数和前端 SSE 流处理、拆分大组件；L2 合并 N+1 查询、复用 DB 会话、并行化请求；L3 添加错误脱敏和 Error Boundary；L4 添加骨架屏和操作反馈。

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph, React 18, Zustand, shadcn/ui, Tailwind

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `backend/app/utils/project.py` | 统一的项目所有权验证函数 |
| `backend/app/utils/error.py` | SSE 错误信息脱敏 |
| `frontend/src/components/project/ChapterListAndDetail.tsx` | 章节列表+详情组件（消除重复 UI） |
| `frontend/src/components/project/InspirationStage.tsx` | 灵感采集阶段 UI |
| `frontend/src/components/project/HistoryView.tsx` | 历史步骤查看 |
| `frontend/src/components/common/ErrorBoundary.tsx` | 全局 Error Boundary |
| `frontend/src/components/common/ProjectDetailSkeleton.tsx` | 项目详情骨架屏 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/utils/llm.py` | 新增 `get_llm_from_state` |
| `backend/app/agents/nodes/outline_generation.py` | 删除私有 `_get_llm_from_state`，改用统一导入；消除重复的 prompt 构建逻辑 |
| `backend/app/agents/nodes/chapter_generation.py` | 删除私有 `_get_llm_from_state`，改用统一导入 |
| `backend/app/agents/nodes/review.py` | 删除私有 `_get_llm_from_state`，改用统一导入 |
| `backend/app/api/chapters.py` | 删除私有 `get_project_for_user`；合并 N+1 查询；SSE 错误脱敏 |
| `backend/app/api/workflow.py` | 删除私有 `get_project_with_ownership`；SSE 错误脱敏；checkpointer 生命周期管理 |
| `backend/app/api/outline.py` | 删除私有 `get_project_and_outline`；SSE 错误脱敏 |
| `backend/app/agents/checkpointer.py` | DB 会话复用，新增 `close()` |
| `frontend/src/lib/sseParser.ts` | 新增 `createSSEStream` 通用函数 |
| `frontend/src/lib/api.ts` | `outlineApi.createStream`、`chapterOutlinesApi.createStream` 改用 `createSSEStream` |
| `frontend/src/lib/workflowApi.ts` | 非流式方法改用 `request`；`runWorkflow` 改用 `createSSEStream` |
| `frontend/src/pages/ProjectDetail.tsx` | 拆分组件、并行请求、操作反馈、骨架屏 |
| `frontend/src/App.tsx` | 包裹 Error Boundary |
| `frontend/src/components/project/OutlineWorkflow.tsx` | 操作反馈 |

---

## Task 1: 后端 — 统一 `get_project_for_user`

**Files:**
- Create: `backend/app/utils/project.py`
- Modify: `backend/app/api/chapters.py:41-58`
- Modify: `backend/app/api/workflow.py:51-81`
- Modify: `backend/app/api/outline.py:57-80`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 创建 `backend/app/utils/project.py`**

```python
"""项目工具函数"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.outline import Outline


def get_project_for_user(
    project_id: int,
    user_id: int,
    db: Session
) -> Project:
    """获取项目并验证所有权

    Args:
        project_id: 项目 ID
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        Project 实例

    Raises:
        HTTPException: 项目不存在或无权访问
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


def get_project_and_outline(
    project_id: int,
    user_id: int,
    db: Session
) -> tuple[Project, Outline]:
    """获取项目和大纲，验证所有权

    Args:
        project_id: 项目 ID
        user_id: 用户 ID
        db: 数据库会话

    Returns:
        (Project, Outline) 元组

    Raises:
        HTTPException: 项目或大纲不存在
    """
    project = get_project_for_user(project_id, user_id, db)

    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    return project, outline
```

- [ ] **Step 2: 修改 `backend/app/api/chapters.py`，删除私有函数，改用导入**

删除第 41-58 行的 `get_project_for_user` 函数定义，在文件头部添加：

```python
from app.utils.project import get_project_for_user
```

- [ ] **Step 3: 修改 `backend/app/api/workflow.py`，删除私有函数，改用导入**

删除第 51-81 行的 `get_project_with_ownership` 函数定义，在文件头部添加：

```python
from app.utils.project import get_project_for_user
```

将文件中所有 `get_project_with_ownership` 调用替换为 `get_project_for_user`。

- [ ] **Step 4: 修改 `backend/app/api/outline.py`，删除私有函数，改用导入**

删除第 57-80 行的 `get_project_and_outline` 函数定义，在文件头部添加：

```python
from app.utils.project import get_project_for_user, get_project_and_outline
```

- [ ] **Step 5: 运行后端测试验证无回归**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/utils/project.py backend/app/api/chapters.py backend/app/api/workflow.py backend/app/api/outline.py
git commit -m "refactor(api): unify get_project_for_user into shared utility"
```

---

## Task 2: 后端 — 统一 `_get_llm_from_state`

**Files:**
- Modify: `backend/app/utils/llm.py`
- Modify: `backend/app/agents/nodes/outline_generation.py:309-378`
- Modify: `backend/app/agents/nodes/chapter_generation.py:301-370`
- Modify: `backend/app/agents/nodes/review.py:132-252`

- [ ] **Step 1: 在 `backend/app/utils/llm.py` 中新增 `get_llm_from_state`**

在文件末尾（`get_llm_service` 函数之后）添加：

```python
def get_llm_from_state(state: dict) -> "LLMService":
    """从工作流状态获取 LLM 服务（统一入口）

    根据 state 中的 llm_config_id 和 project_id 获取对应的 LLM 服务。
    优先级：指定模型配置 > 默认模型配置 > 用户设置

    Args:
        state: NovelState 字典

    Returns:
        LLMService 实例

    Raises:
        ValueError: 项目未找到或用户设置未找到
    """
    from app.database import SessionLocal
    from app.models.project import Project
    from app.models.settings import UserSettings

    db = SessionLocal()
    try:
        project_id = state.get("project_id")
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        user_id = project.user_id
        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == user_id
        ).first()

        if not user_settings:
            raise ValueError(f"User settings not found for user {user_id}")

        return get_llm_for_user(
            user_id, user_settings, db, state.get("llm_config_id")
        )
    finally:
        db.close()
```

- [ ] **Step 2: 修改 `backend/app/agents/nodes/outline_generation.py`**

删除第 309-364 行的 `_get_llm_from_state` 函数定义。

在文件头部将：
```python
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service
```
改为：
```python
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state
```

将 `outline_generation_node` 函数中 `llm = _get_llm_from_state(state)` 改为 `llm = get_llm_from_state(state)`。

- [ ] **Step 3: 修改 `backend/app/agents/nodes/chapter_generation.py`**

删除第 301-356 行的 `_get_llm_from_state` 函数定义。

在文件头部将：
```python
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service
```
改为：
```python
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state
```

将 `chapter_outlines_node` 和 `generate_chapter_content_node` 中 `llm = _get_llm_from_state(state)` 改为 `llm = get_llm_from_state(state)`。

- [ ] **Step 4: 修改 `backend/app/agents/nodes/review.py`**

删除第 132-187 行的 `_get_llm_from_state` 函数定义。

在文件头部将：
```python
from app.services.llm import LLMService, get_llm_service_from_config, get_llm_service
```
改为：
```python
from app.services.llm import LLMService
from app.utils.llm import get_llm_from_state
```

将 `review_node` 中 `llm = _get_llm_from_state(state)` 改为 `llm = get_llm_from_state(state)`。

- [ ] **Step 5: 运行后端测试验证无回归**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/utils/llm.py backend/app/agents/nodes/outline_generation.py backend/app/agents/nodes/chapter_generation.py backend/app/agents/nodes/review.py
git commit -m "refactor(agents): unify _get_llm_from_state into shared utility"
```

---

## Task 3: 后端 — 消除大纲生成重复逻辑

**Files:**
- Modify: `backend/app/agents/nodes/outline_generation.py:170-239`

- [ ] **Step 1: 重构 `generate_outline_node` 调用 `prepare_outline_prompt`**

将 `outline_generation.py` 中 `generate_outline_node` 函数（170-239行）替换为：

```python
async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """从灵感模板生成大纲"""
    prompt, chapter_count = prepare_outline_prompt(state)

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],
        "outline_world_setting": outline["world_setting"],
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
    }

    return new_state
```

- [ ] **Step 2: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_agents.py -v`
Expected: 所有测试 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/nodes/outline_generation.py
git commit -m "refactor(agents): deduplicate outline generation prompt building"
```

---

## Task 4: 前端 — 统一 SSE 流处理

**Files:**
- Modify: `frontend/src/lib/sseParser.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/workflowApi.ts`

- [ ] **Step 1: 在 `frontend/src/lib/sseParser.ts` 中新增 `createSSEStream`**

在文件末尾添加：

```typescript
/**
 * 创建 SSE 流式连接的通用函数
 * 统一处理认证、fetch、流读取、缓冲区解析、错误处理
 */
export interface SSEStreamOptions
{
  url: string
  method?: string
  body?: unknown
  signal?: AbortSignal
}

export async function createSSEStream(
  options: SSEStreamOptions,
  onEvent: (type: string, data: unknown) => void,
  onError: (error: string) => void
): Promise<void>
{
  // 动态导入避免循环依赖
  const { getSessionToken } = await import('./api')

  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const headers: HeadersInit = {}

  if (options.method === 'POST' || options.body)
  {
    headers['Content-Type'] = 'application/json'
  }

  // 构建认证头
  const token = getSessionToken()
  if (token)
  {
    const credentials = btoa(`${token}:`)
    headers['Authorization'] = `Basic ${credentials}`
  }

  const response = await fetch(`${API_BASE_URL}${options.url}`, {
    method: options.method || 'GET',
    headers,
    signal: options.signal,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok)
  {
    const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
    onError(errorData.detail || `HTTP ${response.status}`)
    return
  }

  const reader = response.body?.getReader()
  if (!reader)
  {
    onError('无法获取数据流')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try
  {
    while (true)
    {
      const { done, value } = await reader.read()

      if (done)
      {
        // 处理剩余缓冲区
        if (buffer.trim())
        {
          const [remaining, events] = processSSEBuffer(buffer, '')
          for (const event of events)
          {
            const parsedData = parseSSEData(event.data)
            onEvent(event.type, parsedData)
          }
        }
        break
      }

      const newData = decoder.decode(value, { stream: true })
      const [remaining, events] = processSSEBuffer(buffer, newData)
      buffer = remaining

      for (const event of events)
      {
        const parsedData = parseSSEData(event.data)
        onEvent(event.type, parsedData)
      }
    }
  }
  catch (err)
  {
    // 用户主动取消，不触发错误回调
    if (err instanceof Error && err.name === 'AbortError')
    {
      return
    }
    onError(err instanceof Error ? err.message : '未知错误')
  }
}
```

- [ ] **Step 2: 重构 `frontend/src/lib/api.ts` 中 `outlineApi.createStream`**

将 `outlineApi.createStream` 方法体替换为：

```typescript
  async createStream(
    projectId: number,
    callbacks: OutlineStreamCallbacks,
    options?: StreamOptions,
    llmConfigId?: number
  ): Promise<void> {
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/outline`,
        method: 'POST',
        body: llmConfigId ? { llm_config_id: llmConfigId } : {},
        signal: options?.signal,
      },
      (type, data) => {
        if (type === 'done') {
          callbacks.onDone(data as OutlineStreamResult)
        } else if (type === 'error') {
          callbacks.onError(typeof data === 'string' ? data : String(data))
        } else {
          callbacks.onChunk(typeof data === 'string' ? data : String(data))
        }
      },
      callbacks.onError
    )
  },
```

在文件头部添加 `import { createSSEStream } from './sseParser'`。

- [ ] **Step 3: 重构 `frontend/src/lib/api.ts` 中 `chapterOutlinesApi.createStream`**

将 `chapterOutlinesApi.createStream` 方法体替换为：

```typescript
  async createStream(
    projectId: number,
    callbacks: ChapterOutlineStreamCallbacks,
    options?: StreamOptions,
    llmConfigId?: number
  ): Promise<void> {
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/chapter-outlines`,
        method: 'POST',
        body: llmConfigId ? { llm_config_id: llmConfigId } : {},
        signal: options?.signal,
      },
      (type, data) => {
        if (type === 'progress') {
          const progress = data as { chapter_number: number; total: number; chapter: { id: number; chapter_number: number; title: string } }
          callbacks.onProgress(progress.chapter_number, progress.total, progress.chapter)
        } else if (type === 'done') {
          const done = data as { total: number; stage: string }
          callbacks.onDone(done.total, done.stage)
        } else if (type === 'error') {
          callbacks.onError(typeof data === 'string' ? data : String(data))
        }
      },
      callbacks.onError
    )
  },
```

- [ ] **Step 4: 重构 `frontend/src/lib/workflowApi.ts` 中 `runWorkflow`**

将 `runWorkflow` 方法体替换为：

```typescript
  async runWorkflow(
    projectId: number,
    callbacks: WorkflowStreamCallbacks,
    options?: StreamOptions
  ): Promise<void>
  {
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/run`,
        method: 'POST',
        signal: options?.signal,
      },
      (type, data) => {
        switch (type)
        {
          case 'node_start':
            callbacks.onNodeStart?.(data as string)
            break
          case 'node_done':
            {
              const nodeData = data as { node: string; data: unknown }
              callbacks.onNodeDone?.(nodeData.node, nodeData.data)
            }
            break
          case 'chunk':
            callbacks.onChunk?.(data as string)
            break
          case 'checkpoint':
            callbacks.onCheckpoint?.(data as WorkflowStateResponse)
            break
          case 'waiting':
            callbacks.onWaiting?.(data as string)
            break
          case 'done':
            callbacks.onDone?.(data as { stage: string; chapters: WrittenChapter[] })
            break
          case 'error':
            callbacks.onError?.(data as string)
            break
        }
      },
      (error) => callbacks.onError?.(error)
    )
  },
```

在文件头部添加 `import { createSSEStream } from './sseParser'`，删除不再需要的 `import { parseSSEEventBlock, parseSSEData } from './sseParser'`。

- [ ] **Step 5: 运行前端测试验证**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/lib/sseParser.ts frontend/src/lib/api.ts frontend/src/lib/workflowApi.ts
git commit -m "refactor(frontend): unify SSE stream handling into createSSEStream"
```

---

## Task 5: 前端 — workflowApi 非流式方法复用 request

**Files:**
- Modify: `frontend/src/lib/workflowApi.ts`

- [ ] **Step 1: 重构 workflowApi 非流式方法**

在文件头部添加：
```typescript
import { request } from './api'
```

将 `confirmWorkflow` 方法替换为：

```typescript
  async confirmWorkflow(projectId: number): Promise<void>
  {
    await request(`/api/projects/${projectId}/workflow/confirm`, {
      method: 'POST',
    })
  },
```

将 `getWorkflowState` 方法替换为：

```typescript
  async getWorkflowState(projectId: number): Promise<WorkflowStateResponse>
  {
    return request<WorkflowStateResponse>(`/api/projects/${projectId}/workflow/state`)
  },
```

将 `cancelWorkflow` 方法替换为：

```typescript
  async cancelWorkflow(projectId: number): Promise<void>
  {
    await request(`/api/projects/${projectId}/workflow/cancel`, {
      method: 'POST',
    })
  },
```

将 `setWorkflowMode` 方法替换为：

```typescript
  async setWorkflowMode(projectId: number, mode: WorkflowMode): Promise<void>
  {
    await request(`/api/projects/${projectId}/workflow/mode`, {
      method: 'PUT',
      body: { mode },
    })
  },
```

将 `updateStage` 方法替换为：

```typescript
  async updateStage(projectId: number, stage: string): Promise<void>
  {
    await request(`/api/projects/${projectId}/workflow/stage`, {
      method: 'PUT',
      body: { stage },
    })
  },
```

删除文件中所有不再使用的 `getSessionToken` 导入和 `API_BASE_URL` 常量（`runWorkflow` 已在 Task 4 中改用 `createSSEStream`）。

- [ ] **Step 2: 运行前端测试验证**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/lib/workflowApi.ts
git commit -m "refactor(frontend): workflowApi non-stream methods reuse request helper"
```

---

## Task 6: 前端 — 拆分 ProjectDetail 组件

**Files:**
- Create: `frontend/src/components/project/ChapterListAndDetail.tsx`
- Create: `frontend/src/components/project/InspirationStage.tsx`
- Create: `frontend/src/components/project/HistoryView.tsx`
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 创建 `ChapterListAndDetail.tsx`**

```tsx
// 章节列表 + 章节详情组件
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ChapterOutline } from '@/types'

interface ChapterListAndDetailProps
{
  chapterOutlines: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  onSelectChapter: (chapter: ChapterOutline) => void
  projectId: number
  onConfirmOutline: (chapterNum: number) => void
}

export default function ChapterListAndDetail({
  chapterOutlines,
  selectedChapter,
  onSelectChapter,
  projectId,
  onConfirmOutline,
}: ChapterListAndDetailProps)
{
  return (
    <>
      {/* 章节列表 */}
      <Card className="w-64 shrink-0">
        <CardHeader>
          <CardTitle className="text-lg">章节列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="max-h-96 overflow-y-auto">
            {chapterOutlines.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground text-sm">
                暂无章节
              </div>
            ) : (
              chapterOutlines.map((chapter) => (
                <div
                  key={chapter.id}
                  className={`px-4 py-2 border-b cursor-pointer hover:bg-muted ${
                    selectedChapter?.id === chapter.id ? 'bg-muted' : ''
                  }`}
                  onClick={() => onSelectChapter(chapter)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm">
                      {chapter.chapter_number}. {chapter.title || '未命名'}
                    </span>
                    {chapter.has_content && (
                      <span className="text-xs text-green-600">✓</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* 章节详情 */}
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">
            {selectedChapter
              ? `第 ${selectedChapter.chapter_number} 章：${selectedChapter.title || '未命名'}`
              : '章节详情'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {selectedChapter ? (
            <div className="space-y-4">
              <div>
                <div className="text-sm font-medium text-muted-foreground">场景</div>
                <div>{selectedChapter.scene || '-'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">人物</div>
                <div>{selectedChapter.characters || '-'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">情节</div>
                <div>{selectedChapter.plot || '-'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">冲突</div>
                <div>{selectedChapter.conflict || '-'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">结局</div>
                <div>{selectedChapter.ending || '-'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">预计字数</div>
                <div>{selectedChapter.target_words} 字</div>
              </div>

              <div className="flex gap-2 pt-4">
                {!selectedChapter.confirmed && (
                  <Button
                    onClick={() => onConfirmOutline(selectedChapter.chapter_number)}
                  >
                    确认章节大纲
                  </Button>
                )}
                {selectedChapter.confirmed && (
                  <Link to={`/project/${projectId}/write`}>
                    <Button>
                      {selectedChapter.has_content ? '编辑正文' : '开始写作'}
                    </Button>
                  </Link>
                )}
                {selectedChapter.has_content && (
                  <Link to={`/project/${projectId}/read/${selectedChapter.chapter_number}`}>
                    <Button variant="outline">阅读正文</Button>
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-10">
              选择左侧章节查看详情
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}
```

- [ ] **Step 2: 创建 `InspirationStage.tsx`**

```tsx
// 灵感采集阶段组件
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import InspirationForm from '@/components/project/InspirationForm'
import InspirationEditor from '@/components/project/InspirationEditor'
import type { InspirationData } from '@/lib/inspiration'

interface InspirationStageProps
{
  collectedInfo: Record<string, unknown> | undefined
  showEditor: boolean
  inspirationData: InspirationData | null
  inspirationTemplate: string
  onSubmit: (data: InspirationData, modelId?: number) => void
  onEditorDataChange: (data: InspirationData) => void
  onEditorTemplateChange: (template: string) => void
  onEditorConfirm: () => void
  onEditorBack: () => void
}

export default function InspirationStage({
  collectedInfo,
  showEditor,
  inspirationData,
  inspirationTemplate,
  onSubmit,
  onEditorDataChange,
  onEditorTemplateChange,
  onEditorConfirm,
  onEditorBack,
}: InspirationStageProps)
{
  if (!showEditor)
  {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle>灵感采集</CardTitle>
        </CardHeader>
        <CardContent>
          <InspirationForm
            initialData={collectedInfo as Partial<InspirationData>}
            onSubmit={onSubmit}
          />
        </CardContent>
      </Card>
    )
  }

  if (!inspirationData) return null

  return (
    <Card className="flex-1">
      <CardHeader>
        <CardTitle>灵感模板</CardTitle>
      </CardHeader>
      <CardContent>
        <InspirationEditor
          data={inspirationData}
          template={inspirationTemplate}
          onDataChange={onEditorDataChange}
          onTemplateChange={onEditorTemplateChange}
          onConfirm={onEditorConfirm}
          onBack={onEditorBack}
        />
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 3: 创建 `HistoryView.tsx`**

```tsx
// 历史步骤查看组件
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import InspirationForm from '@/components/project/InspirationForm'
import InspirationDisplay from '@/components/project/InspirationDisplay'
import ChapterListAndDetail from '@/components/project/ChapterListAndDetail'
import type { ChapterOutline, Outline } from '@/types'
import type { InspirationData } from '@/lib/inspiration'

interface HistoryViewProps
{
  stepIndex: number
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  onSelectChapter: (chapter: ChapterOutline) => void
  projectId: number
  onConfirmOutline: (chapterNum: number) => void
  onInspirationUpdate: (data: InspirationData) => void
}

export default function HistoryView({
  stepIndex,
  outline,
  chapterOutlines,
  selectedChapter,
  onSelectChapter,
  projectId,
  onConfirmOutline,
  onInspirationUpdate,
}: HistoryViewProps)
{
  switch (stepIndex)
  {
    case 0: // 灵感采集
    {
      const info = outline?.collected_info
      // 如果大纲未确认，允许修改灵感采集
      if (outline && !outline.confirmed)
      {
        return (
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>修改灵感采集</CardTitle>
            </CardHeader>
            <CardContent>
              <InspirationForm
                initialData={info as Partial<InspirationData>}
                onSubmit={(data) => {
                  onInspirationUpdate(data)
                }}
              />
            </CardContent>
          </Card>
        )
      }
      return (
        <Card className="flex-1">
          <CardHeader>
            <CardTitle>灵感采集记录</CardTitle>
          </CardHeader>
          <CardContent>
            {info && Object.keys(info).length > 0 ? (
              <InspirationDisplay data={info} />
            ) : (
              <div className="text-muted-foreground">暂无灵感采集记录</div>
            )}
          </CardContent>
        </Card>
      )
    }

    case 1: // 大纲生成
      return (
        <Card className="flex-1">
          <CardHeader>
            <CardTitle>大纲信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {outline ? (
              <>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">标题</div>
                  <div className="text-lg font-bold">{outline.title || '未设置'}</div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">简介</div>
                  <div>{outline.summary || '未设置'}</div>
                </div>
                {outline.plot_points && outline.plot_points.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">主要情节节点</div>
                    <ul className="list-disc list-inside text-sm mt-1">
                      {outline.plot_points.map((point, idx) => {
                        const eventText = typeof point === 'string' ? point : point.event
                        return <li key={idx} className="mb-1">{eventText}</li>
                      })}
                    </ul>
                  </div>
                )}
                <div>
                  <div className="text-sm font-medium text-muted-foreground">章节数</div>
                  <div>{outline.chapter_count_suggested || 0} 章</div>
                </div>
              </>
            ) : (
              <div className="text-muted-foreground">暂无大纲信息</div>
            )}
          </CardContent>
        </Card>
      )

    case 2: // 章节大纲
    case 3: // 写作
    case 4: // 审核
      return (
        <ChapterListAndDetail
          chapterOutlines={chapterOutlines}
          selectedChapter={selectedChapter}
          onSelectChapter={onSelectChapter}
          projectId={projectId}
          onConfirmOutline={onConfirmOutline}
        />
      )

    default:
      return null
  }
}
```

- [ ] **Step 4: 精简 `ProjectDetail.tsx`**

将 `ProjectDetail.tsx` 中的 `renderHistoryContent` 函数和重复的章节列表/详情 JSX 删除，改为使用新组件。关键改动：

1. 添加导入：
```tsx
import ChapterListAndDetail from '@/components/project/ChapterListAndDetail'
import InspirationStage from '@/components/project/InspirationStage'
import HistoryView from '@/components/project/HistoryView'
```

2. 删除 `renderHistoryContent` 函数（约 180 行），在 `viewingStep !== null` 的渲染位置替换为：
```tsx
{viewingStep !== null ? (
  <HistoryView
    stepIndex={viewingStep}
    outline={outline}
    chapterOutlines={chapterOutlines}
    selectedChapter={selectedChapter}
    onSelectChapter={setSelectedChapter}
    projectId={project.id}
    onConfirmOutline={handleConfirmChapterOutline}
    onInspirationUpdate={handleInspirationUpdate}
  />
) : (
  <>
    {/* 灵感采集阶段 */}
    {showInspirationCollection && (
      <InspirationStage
        collectedInfo={outline?.collected_info}
        showEditor={showInspirationEditor}
        inspirationData={inspirationData}
        inspirationTemplate={inspirationTemplate}
        onSubmit={handleInspirationSubmit}
        onEditorDataChange={setInspirationData}
        onEditorTemplateChange={setInspirationTemplate}
        onEditorConfirm={handleInspirationConfirm}
        onEditorBack={() => setShowInspirationEditor(false)}
      />
    )}

    {/* 大纲工作流阶段 */}
    {showOutlineWorkflow && outline && (
      <OutlineWorkflow
        projectId={project.id}
        outline={outline}
        modelId={selectedModelId}
        onOutlineUpdate={handleOutlineUpdate}
        onStageChange={handleStageChange}
        onGeneratingChange={setIsGenerating}
      />
    )}

    {/* 章节列表阶段 */}
    {showChapterList && (
      <ChapterListAndDetail
        chapterOutlines={chapterOutlines}
        selectedChapter={selectedChapter}
        onSelectChapter={setSelectedChapter}
        projectId={project.id}
        onConfirmOutline={handleConfirmChapterOutline}
      />
    )}
  </>
)}
```

3. 删除主渲染中重复的章节列表+详情 JSX（约 100 行）

- [ ] **Step 5: 运行前端测试验证**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/project/ChapterListAndDetail.tsx frontend/src/components/project/InspirationStage.tsx frontend/src/components/project/HistoryView.tsx frontend/src/pages/ProjectDetail.tsx
git commit -m "refactor(frontend): split ProjectDetail into focused components"
```

---

## Task 7: 后端 — 合并确认章节 N+1 查询

**Files:**
- Modify: `backend/app/api/chapters.py:371-379`

- [ ] **Step 1: 合并两次 count 查询为一次聚合查询**

将 `chapters.py` 中 `confirm_chapter_outline` 函数的第 371-379 行：

```python
    # Check if all chapter outlines are confirmed
    total_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).count()

    confirmed_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id,
        ChapterOutline.confirmed == True
    ).count()
```

替换为：

```python
    # 检查是否所有章节大纲已确认（单次聚合查询）
    from sqlalchemy import func, case as sql_case

    result = db.query(
        func.count(ChapterOutline.id).label('total'),
        func.count(sql_case((ChapterOutline.confirmed == True, ChapterOutline.id))).label('confirmed')
    ).filter(ChapterOutline.project_id == project_id).one()

    total_outlines = result.total
    confirmed_outlines = result.confirmed
```

- [ ] **Step 2: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/chapters.py
git commit -m "perf(api): merge N+1 count queries into single aggregation"
```

---

## Task 8: 后端 — Checkpointer 会话复用

**Files:**
- Modify: `backend/app/agents/checkpointer.py`
- Modify: `backend/app/api/workflow.py`

- [ ] **Step 1: 修改 `checkpointer.py`，移除方法内的 `_close_db` 调用，新增 `close()`**

将 `PostgresCheckpointSaver` 类修改为：

```python
class PostgresCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph checkpoint saver using PostgreSQL.

    用于持久化工作流状态，支持暂停/恢复功能。
    DB 会话在首次使用时创建，工作流结束后由调用方显式关闭。
    """

    def __init__(self, project_id: int, thread_id: str = "default"):
        self.project_id = project_id
        self.thread_id = thread_id
        self.db: Optional[Session] = None

    def _get_db(self) -> Session:
        """获取数据库会话（延迟初始化，复用同一会话）"""
        if self.db is None:
            self.db = SessionLocal()
        return self.db

    def close(self):
        """显式关闭数据库会话，由调用方在工作流结束时调用"""
        if self.db:
            self.db.close()
            self.db = None
```

在 `get_tuple`、`put`、`list`、`delete` 方法中，删除所有 `self._close_db()` 调用和 `finally: self._close_db()` 块（改为空 finally 或直接删除 try/finally）。

删除 `_close_db` 方法。

- [ ] **Step 2: 修改 `workflow.py` 的 `stream_generator`，在工作流结束时关闭 checkpointer**

在 `run_workflow` 端点中，将 `stream_generator` 修改为引用 checkpointer 实例：

```python
    # 创建带检查点的图
    graph = create_novel_graph_with_checkpointer(project_id, "default")

    # 获取 checkpointer 引用，用于工作流结束后关闭
    from app.agents.graph import create_novel_graph
    from app.agents.checkpointer import get_checkpoint_saver
    checkpointer = get_checkpoint_saver(project_id, "default")

    # ... config 等不变 ...

    async def stream_generator():
        """LangGraph 工作流 SSE 流生成器"""
        try:
            # ... 原有逻辑不变 ...
        except Exception as e:
            # ... 原有逻辑不变 ...
        finally:
            # 工作流结束后关闭 checkpointer 的 DB 会话
            checkpointer.close()
```

- [ ] **Step 3: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py -v`
Expected: 所有测试 PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/checkpointer.py backend/app/api/workflow.py
git commit -m "perf(agents): reuse DB session in checkpointer lifecycle"
```

---

## Task 9: 前端 — ProjectDetail 并行请求

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 将 fetchData 中的串行请求改为并行**

将 `ProjectDetail.tsx` 中 `fetchData` 函数：

```typescript
  const fetchData = async () => {
    if (!id) return

    try {
      const projectData = await projectsApi.get(parseInt(id))
      setProject(projectData)
      setCurrentProject(projectData)

      const outlineData = await outlineApi.get(parseInt(id))
      setOutline(outlineData)
      setProjectOutline(outlineData)

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
      setProjectChapterOutlines(chaptersData)

      if (chaptersData.length > 0) {
        setSelectedChapter(chaptersData[0])
      }
    } catch (err) {
      console.error('Failed to fetch project:', err)
    } finally {
      setLoading(false)
    }
  }
```

替换为：

```typescript
  const fetchData = async () => {
    if (!id) return

    try {
      // 并行请求：三个请求互不依赖
      const [projectData, outlineData, chaptersData] = await Promise.all([
        projectsApi.get(parseInt(id)),
        outlineApi.get(parseInt(id)),
        chapterOutlinesApi.list(parseInt(id)),
      ])

      setProject(projectData)
      setCurrentProject(projectData)
      setOutline(outlineData)
      setProjectOutline(outlineData)
      setChapterOutlines(chaptersData)
      setProjectChapterOutlines(chaptersData)

      if (chaptersData.length > 0) {
        setSelectedChapter(chaptersData[0])
      }
    } catch (err) {
      console.error('Failed to fetch project:', err)
    } finally {
      setLoading(false)
    }
  }
```

- [ ] **Step 2: 运行前端测试验证**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "perf(frontend): parallelize ProjectDetail API requests"
```

---

## Task 10: 后端 — SSE 错误信息脱敏

**Files:**
- Create: `backend/app/utils/error.py`
- Modify: `backend/app/api/workflow.py:341-343`
- Modify: `backend/app/api/chapters.py:247-248,681-683`
- Modify: `backend/app/api/outline.py` (查找所有 `str(e)` SSE 错误)

- [ ] **Step 1: 创建 `backend/app/utils/error.py`**

```python
"""错误处理工具函数"""

import httpx


def sanitize_error(e: Exception) -> str:
    """脱敏异常信息，返回用户可读的错误描述

    业务逻辑错误（ValueError）内容安全，直接返回。
    外部服务错误和未知异常统一脱敏处理。

    Args:
        e: 原始异常

    Returns:
        用户可读的错误描述
    """
    if isinstance(e, ValueError):
        return str(e)

    if isinstance(e, httpx.TimeoutException):
        return "AI 服务响应超时，请稍后重试"

    if isinstance(e, httpx.ConnectError):
        return "AI 服务连接失败，请稍后重试"

    if isinstance(e, PermissionError):
        return "权限不足"

    return "服务暂时不可用，请稍后重试"
```

- [ ] **Step 2: 修改 `backend/app/api/workflow.py`**

在文件头部添加：
```python
from app.utils.error import sanitize_error
```

将 `stream_generator` 中的错误处理：
```python
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
```
改为：
```python
            yield f"event: error\ndata: {json.dumps({'error': sanitize_error(e)})}\n\n"
```

同时删除 `error_msg = str(e)` 这行（不再需要）。

- [ ] **Step 3: 修改 `backend/app/api/chapters.py`**

在文件头部添加：
```python
from app.utils.error import sanitize_error
```

将章节大纲生成 `stream_generator` 中：
```python
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
```
改为：
```python
            yield f"event: error\ndata: {json.dumps(sanitize_error(e))}\n\n"
```

将章节内容生成 `stream_generator` 中：
```python
            yield f"event: error\ndata: {str(e)}\n\n"
```
改为：
```python
            yield f"event: error\ndata: {sanitize_error(e)}\n\n"
```

- [ ] **Step 4: 修改 `backend/app/api/outline.py`**

在文件头部添加：
```python
from app.utils.error import sanitize_error
```

查找并替换所有 SSE 流生成器中的 `str(e)` 为 `sanitize_error(e)`。

- [ ] **Step 5: 运行后端测试验证**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/utils/error.py backend/app/api/workflow.py backend/app/api/chapters.py backend/app/api/outline.py
git commit -m "fix(api): sanitize SSE error messages to prevent info leakage"
```

---

## Task 11: 前端 — 全局 Error Boundary

**Files:**
- Create: `frontend/src/components/common/ErrorBoundary.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/common/ErrorBoundary.tsx`**

```tsx
// 全局 Error Boundary 组件
import { Component, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props
{
  children: ReactNode
}

interface State
{
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State>
{
  constructor(props: Props)
  {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State
  {
    return { hasError: true, error }
  }

  render()
  {
    if (this.state.hasError)
    {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <Card className="w-96">
            <CardHeader>
              <CardTitle>页面出错了</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {this.state.error?.message || '发生了未知错误'}
              </p>
              <Button
                onClick={() => window.location.reload()}
                className="w-full"
              >
                刷新页面
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}
```

- [ ] **Step 2: 在 `App.tsx` 中包裹 Error Boundary**

将 `App.tsx` 的路由区域用 Error Boundary 包裹：

```tsx
import ErrorBoundary from '@/components/common/ErrorBoundary'

// ...

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {/* 原有路由不变 */}
        </Routes>
        <Toaster />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
```

- [ ] **Step 3: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功，无报错

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/common/ErrorBoundary.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add global Error Boundary"
```

---

## Task 12: 前端 — 加载骨架屏

**Files:**
- Create: `frontend/src/components/common/ProjectDetailSkeleton.tsx`
- Modify: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 安装 shadcn/ui Skeleton 组件**

Run: `cd frontend && npx shadcn@latest add skeleton`

- [ ] **Step 2: 创建 `frontend/src/components/common/ProjectDetailSkeleton.tsx`**

```tsx
// 项目详情页骨架屏
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

export default function ProjectDetailSkeleton()
{
  return (
    <div>
      {/* 项目标题骨架 */}
      <div className="mb-6">
        <Skeleton className="h-8 w-64 mb-2" />
        <div className="flex gap-6">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-20" />
        </div>
      </div>

      {/* 步骤导航骨架 */}
      <Skeleton className="h-10 w-full mb-4" />

      {/* 主内容区骨架 */}
      <div className="flex gap-6 mt-4">
        <Card className="w-64 shrink-0">
          <CardHeader>
            <Skeleton className="h-5 w-20" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
        <Card className="flex-1">
          <CardHeader>
            <Skeleton className="h-5 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i}>
                  <Skeleton className="h-3 w-16 mb-2" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 在 `ProjectDetail.tsx` 中使用骨架屏**

将加载状态的渲染：
```tsx
  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }
```

替换为：
```tsx
  if (loading) {
    return <ProjectDetailSkeleton />
  }
```

添加导入：
```tsx
import ProjectDetailSkeleton from '@/components/common/ProjectDetailSkeleton'
```

- [ ] **Step 4: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/common/ProjectDetailSkeleton.tsx frontend/src/components/ui/skeleton.tsx frontend/src/pages/ProjectDetail.tsx
git commit -m "feat(frontend): add loading skeleton for ProjectDetail"
```

---

## Task 13: 前端 — 操作反馈优化

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`
- Modify: `frontend/src/components/project/OutlineWorkflow.tsx`

- [ ] **Step 1: 在 `ProjectDetail.tsx` 中添加 toast 错误反馈**

将 `handleStageChange` 中的 catch 块：
```typescript
    } catch (err) {
      console.error('Failed to update stage:', err)
    }
```
改为：
```typescript
    } catch (err) {
      console.error('Failed to update stage:', err)
      toast.error('切换阶段失败')
    }
```

将 `handleInspirationConfirm` 中的 catch 块：
```typescript
    } catch (err) {
      console.error('Failed to confirm inspiration:', err)
    }
```
改为：
```typescript
    } catch (err) {
      console.error('Failed to confirm inspiration:', err)
      toast.error('确认灵感失败')
    }
```

将 `handleInspirationUpdate` 中的 catch 块：
```typescript
    } catch (err) {
      console.error('Failed to update inspiration:', err)
    }
```
改为：
```typescript
    } catch (err) {
      console.error('Failed to update inspiration:', err)
      toast.error('更新灵感失败')
    }
```

确保文件头部已有 `import { toast } from 'sonner'`。

- [ ] **Step 2: 在 `OutlineWorkflow.tsx` 中添加 toast 反馈**

检查 `OutlineWorkflow.tsx` 中所有 `console.error` 调用，添加对应的 `toast.error`。确保文件头部已有 `import { toast } from 'sonner'`。

- [ ] **Step 3: 运行前端测试验证**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/ProjectDetail.tsx frontend/src/components/project/OutlineWorkflow.tsx
git commit -m "fix(frontend): add toast feedback for failed operations"
```

---

## 最终验证

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 2: 运行全部前端测试**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 3: 前端构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: 提交设计文档**

```bash
git add docs/superpowers/specs/2026-04-26-full-optimization-design.md docs/superpowers/plans/2026-04-26-full-optimization-plan.md
git commit -m "docs: add full optimization design and implementation plan"
```
