# 前端 API 客户端合并实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `workflowApi.ts` 中与 `api.ts` 重复的认证和请求逻辑，统一 API 客户端。

**Architecture:** 将 `workflowApi.ts` 的非流式方法（`confirmWorkflow`, `getWorkflowState`, `cancelWorkflow`, `setWorkflowMode`, `updateStage`）改用 `api.ts` 的 `request()` 函数。删除重复的 `buildAuthHeaders()` 和 `makeRequest()` 函数。`runWorkflow()` 保持使用 `createSSEStream`，但认证通过 `getSessionToken()` 统一获取。

**Tech Stack:** TypeScript, React, Vitest

**Spec:** `docs/superpowers/specs/2026-05-08-architecture-optimization-design.md` Section 3.1

---

## 文件结构

| 文件 | 变更 | 职责 |
|------|------|------|
| `frontend/src/lib/workflowApi.ts` | 修改 | 删除重复函数，改用 `request()` |
| `frontend/src/lib/workflowApi.test.ts` | 修改 | 更新测试以覆盖重构后的方法 |

---

### Task 1: 准备工作 — 运行基线测试

**Files:**
- Test: `frontend/src/lib/workflowApi.test.ts`

- [ ] **Step 1: 运行现有测试确认基线**

Run: `cd /opt/project/novelagent/frontend && npm run test -- src/lib/workflowApi.test.ts`

Expected: 所有测试通过（记录通过数量作为基线）

---

### Task 2: 重构 workflowApi — 删除重复函数，改用 request()

**Files:**
- Modify: `frontend/src/lib/workflowApi.ts:22-72`

- [ ] **Step 1: 删除 buildAuthHeaders 函数**

删除 `frontend/src/lib/workflowApi.ts` 第 22-39 行：

```typescript
// 删除以下函数
/**
 * 构建认证请求头
 */
function buildAuthHeaders(includeContentType = false): HeadersInit
{
  const headers: HeadersInit = {}

  if (includeContentType)
  {
    headers['Content-Type'] = 'application/json'
  }

  const token = getSessionToken()
  if (token)
  {
    const credentials = btoa(`${token}:`)
    headers['Authorization'] = `Basic ${credentials}`
  }

  return headers
}
```

- [ ] **Step 2: 删除 makeRequest 函数**

删除 `frontend/src/lib/workflowApi.ts` 第 44-72 行：

```typescript
// 删除以下函数
/**
 * 发送请求并处理错误
 */
async function makeRequest<T = void>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  defaultErrorMsg: string,
  body?: unknown
): Promise<T>
{
  const headers = buildAuthHeaders(!!body)

  const response = await fetch(`${API_BASE_URL}${url}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok)
  {
    const errorData = await response.json().catch(() => ({ detail: defaultErrorMsg }))
    throw new Error(errorData.detail || `HTTP ${response.status}`)
  }

  // 对于 POST/PUT/DELETE 返回 void，对于 GET 返回 JSON
  if (method === 'GET')
  {
    return response.json()
  }

  return undefined as T
}
```

- [ ] **Step 3: 添加 request 导入**

在 `frontend/src/lib/workflowApi.ts` 顶部修改导入：

```typescript
import { getSessionToken, StreamOptions, request } from './api'
```

- [ ] **Step 4: 重构 confirmWorkflow 方法**

将 `confirmWorkflow` 方法改为使用 `request()`：

```typescript
/**
 * 确认工作流当前节点
 * @param projectId - 项目 ID
 */
async confirmWorkflow(projectId: number): Promise<void>
{
  await request<void>(`/api/projects/${projectId}/workflow/confirm`, {
    method: 'POST',
  })
}
```

- [ ] **Step 5: 重构 getWorkflowState 方法**

将 `getWorkflowState` 方法改为使用 `request()`：

```typescript
/**
 * 获取工作流状态
 * @param projectId - 项目 ID
 * @returns 工作流状态
 */
async getWorkflowState(projectId: number): Promise<WorkflowStateResponse>
{
  return request<WorkflowStateResponse>(`/api/projects/${projectId}/workflow/state`)
}
```

- [ ] **Step 6: 重构 cancelWorkflow 方法**

将 `cancelWorkflow` 方法改为使用 `request()`：

```typescript
/**
 * 取消工作流
 * @param projectId - 项目 ID
 */
async cancelWorkflow(projectId: number): Promise<void>
{
  await request<void>(`/api/projects/${projectId}/workflow/cancel`, {
    method: 'POST',
  })
}
```

- [ ] **Step 7: 重构 setWorkflowMode 方法**

将 `setWorkflowMode` 方法改为使用 `request()`：

```typescript
/**
 * 设置工作流模式
 * @param projectId - 项目 ID
 * @param mode - 工作流模式
 */
async setWorkflowMode(projectId: number, mode: WorkflowMode): Promise<void>
{
  await request<void>(`/api/projects/${projectId}/workflow/mode`, {
    method: 'PUT',
    body: { mode },
  })
}
```

- [ ] **Step 8: 重构 updateStage 方法**

将 `updateStage` 方法改为使用 `request()`：

```typescript
/**
 * 更新工作流阶段
 * @param projectId - 项目 ID
 * @param stage - 新阶段
 */
async updateStage(projectId: number, stage: string): Promise<void>
{
  await request<void>(`/api/projects/${projectId}/workflow/stage`, {
    method: 'PUT',
    body: { stage },
  })
}
```

- [ ] **Step 9: 删除未使用的 API_BASE_URL 常量**

删除 `frontend/src/lib/workflowApi.ts` 第 15-16 行：

```typescript
// 删除以下常量（runWorkflow 已通过 createSSEStream 处理 URL）
const API_BASE_URL = import.meta.env.VITE_API_URL || ''
```

- [ ] **Step 10: 运行测试确认重构未破坏功能**

Run: `cd /opt/project/novelagent/frontend && npm run test -- src/lib/workflowApi.test.ts`

Expected: 所有测试通过

- [ ] **Step 11: 提交变更**

```bash
git add frontend/src/lib/workflowApi.ts
git commit -m "refactor(frontend): merge workflowApi into unified request helper

- Remove duplicate buildAuthHeaders() and makeRequest() functions
- Refactor confirmWorkflow, getWorkflowState, cancelWorkflow, setWorkflowMode, updateStage to use api.ts request()
- runWorkflow keeps createSSEStream but uses getSessionToken() for auth

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 更新测试覆盖重构后的方法

**Files:**
- Modify: `frontend/src/lib/workflowApi.test.ts`

- [ ] **Step 1: 检查现有测试是否需要更新**

Read: `frontend/src/lib/workflowApi.test.ts`

检查是否 mock 了 `buildAuthHeaders` 或 `makeRequest`，如果是则需要改为 mock `request`。

- [ ] **Step 2: 更新测试 mock（如需要）**

如果测试中 mock 了已删除的函数，更新为 mock `request`：

```typescript
// 旧的 mock（如果存在）
// vi.mock('./api', () => ({ buildAuthHeaders: ... }))

// 新的 mock
vi.mock('./api', () => ({
  getSessionToken: () => 'test-token',
  request: vi.fn(),
  StreamOptions: {} as any,
}))
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd /opt/project/novelagent/frontend && npm run test -- src/lib/workflowApi.test.ts`

Expected: 所有测试通过

- [ ] **Step 4: 提交测试更新**

```bash
git add frontend/src/lib/workflowApi.test.ts
git commit -m "test(frontend): update workflowApi tests for unified request helper

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 验证整体功能

- [ ] **Step 1: 运行完整前端测试套件**

Run: `cd /opt/project/novelagent/frontend && npm run test`

Expected: 所有测试通过

- [ ] **Step 2: 启动前端开发服务器手动验证**

Run: `cd /opt/project/novelagent && docker compose up -d frontend`

访问 http://localhost:3001，验证：
- 登录功能正常
- 工作流状态获取正常
- 工作流确认/取消功能正常

- [ ] **Step 3: 最终提交**

```bash
git status
```

确认无未提交文件。

---

## 验收标准

- [ ] `npm run test -- src/lib/workflowApi.test.ts` 全部通过
- [ ] `npm run test` 全部通过
- [ ] 删除了约 50 行重复代码（`buildAuthHeaders` + `makeRequest`）
- [ ] 所有非流式 workflowApi 方法使用统一的 `request()` 函数
- [ ] `runWorkflow()` 保持使用 `createSSEStream`，无功能变更
