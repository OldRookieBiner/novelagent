# 全面优化设计 — 分层渐进方案

## 概述

NovelAgent v0.6.4 后的全面优化，按影响面从大到小分 4 层渐进执行，每层独立可交付。

## L1 架构去重

### L1.1 后端：`_get_llm_from_state` 三重复制统一

**现状：** `outline_generation.py:309-364`、`chapter_generation.py:301-356`、`review.py:132-187` 三处完全相同的 `_get_llm_from_state`，且每处都在节点内部创建 DB 会话。

**方案：** 统一到 `app/utils/llm.py`，复用已有 `get_llm_for_user` 逻辑：

```python
# app/utils/llm.py 新增
def get_llm_from_state(state: NovelState) -> LLMService:
    """从工作流状态获取 LLM 服务（统一入口）"""
    from app.database import SessionLocal
    from app.models.project import Project
    from app.models.settings import UserSettings

    db = SessionLocal()
    try:
        project_id = state.get("project_id")
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        user_settings = db.query(UserSettings).filter(
            UserSettings.user_id == project.user_id
        ).first()

        return get_llm_for_user(
            project.user_id, user_settings, db, state.get("llm_config_id")
        )
    finally:
        db.close()
```

3 个节点的 `_get_llm_from_state` 全部删除，改为 `from app.utils.llm import get_llm_from_state`。

**涉及文件：**
- `backend/app/utils/llm.py` — 新增函数
- `backend/app/agents/nodes/outline_generation.py` — 删除私有函数，改用统一导入
- `backend/app/agents/nodes/chapter_generation.py` — 同上
- `backend/app/agents/nodes/review.py` — 同上

### L1.2 后端：`get_project_for_user` 重复统一

**现状：** `chapters.py:41-58` 的 `get_project_for_user` 和 `workflow.py:51-81` 的 `get_project_with_ownership` 功能完全相同。

**方案：** 新建 `app/utils/project.py`，统一函数命名为 `get_project_for_user`，两个 API 模块都导入使用。

**涉及文件：**
- `backend/app/utils/project.py` — 新建
- `backend/app/api/chapters.py` — 删除私有函数，改用导入
- `backend/app/api/workflow.py` — 删除私有函数，改用导入
- `backend/app/api/outline.py` — 检查是否有类似重复，一并处理

### L1.3 后端：大纲生成逻辑重复

**现状：** `outline_generation.py` 中 `generate_outline_node` (170-239) 和 `prepare_outline_prompt` (242-293) 包含完全相同的章节数计算和灵感模板构建逻辑。

**方案：** `generate_outline_node` 直接调用 `prepare_outline_prompt` 获取 prompt 和 chapter_count，删除重复的 60 行代码。

**涉及文件：**
- `backend/app/agents/nodes/outline_generation.py`

### L1.4 前端：SSE 流处理三重复制统一

**现状：** `api.ts` 的 `outlineApi.createStream`、`chapterOutlinesApi.createStream` 和 `workflowApi.ts` 的 `workflowApi.runWorkflow` 各自实现了几乎相同的 SSE 流读取逻辑（认证头 → fetch → reader → processBuffer → 循环），processBuffer 实现了 3 次。而 `sseParser.ts` 已有 `processSSEBuffer` 但未被使用。

**方案：** 在 `sseParser.ts` 中新增通用的 `createSSEStream` 函数：

```typescript
// sseParser.ts 新增

interface SSEStreamOptions {
  url: string
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function createSSEStream(
  options: SSEStreamOptions,
  onEvent: (type: string, data: unknown) => void,
  onError: (error: string) => void
): Promise<void> {
  // 1. 构建认证头（复用 getSessionToken）
  // 2. fetch 请求
  // 3. 错误检查
  // 4. reader 循环，用 processSSEBuffer 解析
  // 5. AbortError 静默处理
}
```

3 个 API 方法都改为调用 `createSSEStream`，各自只需定义 `onEvent` 回调中的业务分发。

**涉及文件：**
- `frontend/src/lib/sseParser.ts` — 新增 `createSSEStream`
- `frontend/src/lib/api.ts` — `outlineApi.createStream`、`chapterOutlinesApi.createStream` 改用 `createSSEStream`
- `frontend/src/lib/workflowApi.ts` — `runWorkflow` 改用 `createSSEStream`

### L1.5 前端：认证头构建重复

**现状：** `workflowApi.ts` 中每个非流式方法都重复构建认证头，而 `api.ts` 的 `request` 函数已封装认证逻辑。

**方案：** `workflowApi.ts` 的非流式方法（`confirmWorkflow`、`getWorkflowState`、`cancelWorkflow`、`setWorkflowMode`、`updateStage`）改用 `api.ts` 的 `request` 函数。

**涉及文件：**
- `frontend/src/lib/workflowApi.ts`

### L1.6 前端：ProjectDetail 拆分

**现状：** `ProjectDetail.tsx` 730行，混合了页面状态管理、数据获取、handler、renderHistoryContent、主渲染 JSX。

**方案：** 拆分为：

| 组件 | 文件 | 职责 | 预估行数 |
|------|------|------|----------|
| `ProjectDetail.tsx` | 原文件 | 页面容器，状态管理，数据获取 | ~250 |
| `ChapterListAndDetail.tsx` | `components/project/` | 章节列表+详情（消除重复UI） | ~120 |
| `InspirationStage.tsx` | `components/project/` | 灵感采集阶段的UI逻辑 | ~80 |
| `HistoryView.tsx` | `components/project/` | 历史步骤查看 | ~120 |

**涉及文件：**
- `frontend/src/pages/ProjectDetail.tsx` — 精简
- `frontend/src/components/project/ChapterListAndDetail.tsx` — 新建
- `frontend/src/components/project/InspirationStage.tsx` — 新建
- `frontend/src/components/project/HistoryView.tsx` — 新建

### L1.7 前端：章节列表 UI 重复

**现状：** 章节列表+详情 UI 在 `renderHistoryContent`（case 2/3/4，357-460行）和主渲染（583-686行）完全重复约 80 行。

**方案：** 提取为 `ChapterListAndDetail` 组件（L1.6 已覆盖），两处引用同一组件。

## L2 性能优化

### L2.1 后端：确认章节的 N+1 查询合并

**现状：** `chapters.py:371-379`，确认章节时执行 2 次独立 count 查询。

**方案：** 合并为一条带条件聚合的查询：

```python
from sqlalchemy import func, case

result = db.query(
    func.count(ChapterOutline.id).label('total'),
    func.count(case((ChapterOutline.confirmed == True, ChapterOutline.id))).label('confirmed')
).filter(ChapterOutline.project_id == project_id).one()

total_outlines = result.total
confirmed_outlines = result.confirmed
```

**涉及文件：**
- `backend/app/api/chapters.py`

### L2.2 后端：Checkpointer 会话复用

**现状：** `checkpointer.py` 每次 `get_tuple`/`put`/`list`/`delete` 都 `_get_db()` → `_close_db()`。

**方案：** 改为生命周期绑定模式：

```python
class PostgresCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, project_id, thread_id="default"):
        self.project_id = project_id
        self.thread_id = thread_id
        self.db = None  # 延迟初始化

    def _get_db(self):
        if self.db is None:
            self.db = SessionLocal()
        return self.db

    def close(self):
        """显式关闭，由调用方在工作流结束时调用"""
        if self.db:
            self.db.close()
            self.db = None
```

删除每个方法内的 `_close_db()` 调用。在 `workflow.py` 的 `stream_generator` 中添加 finally 块调用 `checkpointer.close()`。

**涉及文件：**
- `backend/app/agents/checkpointer.py`
- `backend/app/api/workflow.py`

### L2.3 前端：ProjectDetail 串行请求改并行

**现状：** `ProjectDetail.tsx:67-91`，fetchData 串行 3 次 await。

**方案：** outline 和 chapterOutlines 不依赖 project 的返回值，改为并行：

```typescript
const [projectData, outlineData, chaptersData] = await Promise.all([
  projectsApi.get(parseInt(id)),
  outlineApi.get(parseInt(id)),
  chapterOutlinesApi.list(parseInt(id)),
])
```

**涉及文件：**
- `frontend/src/pages/ProjectDetail.tsx`

### L2.4 前端：workflowApi 非流式方法复用 request

**现状：** `workflowApi.ts` 的 5 个非流式方法各自手写 fetch + 认证头。

**方案：** 复用 `api.ts` 的 `request` 函数（L1.5 已覆盖），减少代码量同时复用超时/错误处理。

**涉及文件：**
- `frontend/src/lib/workflowApi.ts`

## L3 安全与健壮性

### L3.1 后端：SSE 错误信息脱敏

**现状：** `workflow.py:342`、`chapters.py:248,683` 中 SSE 错误直接返回 `str(e)`，可能泄露内部信息。

**方案：** 新增 `app/utils/error.py`：

```python
def sanitize_error(e: Exception) -> str:
    """脱敏异常信息，返回用户可读的错误描述"""
    if isinstance(e, ValueError):
        return str(e)
    if isinstance(e, httpx.TimeoutException):
        return "AI 服务响应超时，请稍后重试"
    if isinstance(e, PermissionError):
        return "权限不足"
    return "服务暂时不可用，请稍后重试"
```

所有 SSE 流生成器中的 `str(e)` 改为 `sanitize_error(e)`。

**涉及文件：**
- `backend/app/utils/error.py` — 新建
- `backend/app/api/workflow.py`
- `backend/app/api/chapters.py`
- `backend/app/api/outline.py`

### L3.2 前端：全局 Error Boundary

**现状：** 无 Error Boundary，React 组件崩溃时页面白屏。

**方案：** 在 `App.tsx` 路由层添加 Error Boundary：

```tsx
// components/common/ErrorBoundary.tsx
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback onRetry={() => window.location.reload()} />
    }
    return this.props.children
  }
}
```

**涉及文件：**
- `frontend/src/components/common/ErrorBoundary.tsx` — 新建
- `frontend/src/App.tsx` — 包裹路由

### L3.3 前端：SSE 断连提示

**现状：** SSE 流中断时无自动重连或用户引导。

**方案：** 在 `createSSEStream`（L1.4）的 onError 回调中，通过 toast 提示用户连接中断可重新操作。不实现自动重连（AI 生成是幂等操作，重连逻辑复杂且容易导致重复生成）。

**涉及文件：**
- `frontend/src/lib/sseParser.ts` — `createSSEStream` 中的错误处理

## L4 体验增强

### L4.1 加载骨架屏

**现状：** `ProjectDetail.tsx:468` 加载中只显示文字"加载中..."。

**方案：** 使用 shadcn/ui 的 Skeleton 组件替换，为项目列表、章节列表等关键区域添加骨架屏。

```tsx
// 加载状态
{loading && <ProjectDetailSkeleton />}
```

**涉及文件：**
- `frontend/src/components/common/ProjectDetailSkeleton.tsx` — 新建
- `frontend/src/pages/ProjectDetail.tsx`

### L4.2 操作反馈优化

**现状：** 部分 handler（如 `handleStageChange`、`handleInspirationUpdate`）失败时只 `console.error`，用户无感知。

**方案：** 统一使用 `toast.error()` 展示失败提示，成功操作添加 `toast.success()` 反馈。

**涉及文件：**
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/components/project/OutlineWorkflow.tsx`

## 执行顺序

```
L1 架构去重（7项）→ L2 性能优化（4项）→ L3 安全健壮性（3项）→ L4 体验增强（2项）
```

每层完成后运行测试验证，确认无回归再进入下一层。

## 影响范围

| 层次 | 后端文件 | 前端文件 | 新建文件 |
|------|----------|----------|----------|
| L1 | 5 | 4 | 4 |
| L2 | 2 | 2 | 0 |
| L3 | 4 | 3 | 1 |
| L4 | 0 | 3 | 1 |
| **合计** | **11** | **12** | **6** |
