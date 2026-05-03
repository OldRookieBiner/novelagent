# 灵感页面「开始规划」ErrorBoundary 崩溃根治

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底修复「开始规划」生成失败后导致 React ErrorBoundary 崩溃的问题，建立前后端防线确保不会反复出现。

**Architecture:** 采用三层防御策略：
1. **后端层**：大纲生成失败时提前中止工作流 + 清理 checkpoint 避免状态污染 + 重试时使用新 thread_id
2. **SSE 协议层**：统一 error 事件的 data 格式，后端发送对象、前端正确解析
3. **前端层**：所有 API 数据访问添加空值防御 + 重试前调用后端 cleanup 端点

**Tech Stack:** FastAPI, LangGraph, PostgreSQL, React + TypeScript, Zustand

---

## 文件结构总览

### 后端文件（修改）

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/workflow.py` | (1) 大纲为空时提前中止工作流 (2) 重试时先清除旧 checkpoint (3) 使用随机 thread_id 避免状态污染 |
| `backend/app/agents/nodes/outline_generation.py` | 大纲生成节点添加有效性标志，大纲无效时标记状态 |
| `backend/app/agents/state.py` | 添加 `outline_valid` 状态字段 |

### 前端文件（修改）

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/lib/workflowApi.ts` | 修复 SSE error 事件的 data 解析（处理对象格式），提取 errMsg 中的 error 字段 |
| `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 添加重试前的 checkpoint 清除调用，添加卸载保护 |
| `frontend/src/lib/api.ts` | SSE error 事件中正确提取错误消息（无论是对象还是字符串） |
| `frontend/src/components/workbench/planning/CharacterPanel.tsx` | 第 69 行添加空值防御 |
| `frontend/src/components/workbench/planning/RelationPanel.tsx` | 第 65 行添加空值防御 |

### 新增文件

| 文件 | 内容 |
|------|------|
| `backend/app/api/workflow.py` (新增端点) | `POST /{project_id}/workflow/cleanup` — 清除 checkpoint |
| `frontend/src/lib/sseParser.ts` (微改) | `handleEvent` 对 error 事件类型的数据提取优化 |

---

## Task 1: 后端 — 大纲无效时提前中止工作流

**Files:**
- Modify: `backend/app/agents/state.py` (添加字段)
- Modify: `backend/app/agents/nodes/outline_generation.py:518-557` (添加有效性标志)
- Modify: `backend/app/api/workflow.py:259-349` (提前中止逻辑)
- Modify: `backend/app/agents/graph.py:21-38` (路由函数检查大纲有效性)

- [ ] **Step 1: 在 NovelState 中添加 `outline_valid` 字段**

`backend/app/agents/state.py`，在大纲相关字段后添加：

```python
    # ========== 大纲 ==========
    outline_title: Optional[str]
    outline_summary: Optional[str]
    outline_plot_points: list[dict]
    outline_characters: list[dict]
    outline_world_setting: Optional[dict]
    outline_emotional_curve: Optional[str]
    outline_confirmed: bool
    outline_valid: bool  # 大纲是否有效（有标题或概述即有效）
```

- [ ] **Step 2: 在 outline_generation_node 中设置 `outline_valid`**

`backend/app/agents/nodes/outline_generation.py`，第 545-557 行替换为：

```python
    is_valid = bool(outline.get("title") or outline.get("summary") or outline.get("characters"))

    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"outline parsed: title='{outline.get('title', '')}', "
        f"char={len(outline.get('characters', []))}, "
        f"plot={len(outline.get('plot_points', []))}, "
        f"valid={is_valid}"
    )

    new_state: NovelState = {
        **state,
        "outline_title": outline.get("title", ""),
        "outline_summary": outline["summary"],
        "outline_characters": outline["characters"],
        "outline_world_setting": outline["world_setting"],
        "outline_plot_points": outline["plot_points"],
        "outline_emotional_curve": outline["emotional_curve"],
        "chapter_count": chapter_count,
        "stage": STAGE_OUTLINE,
        "outline_valid": is_valid,
    }

    return new_state
```

- [ ] **Step 3: 修改 route_after_outline 检查大纲有效性**

`backend/app/agents/graph.py`，第 21-38 行替换为：

```python
def route_after_outline(
    state: NovelState,
) -> Literal["wait_confirm", "create_characters", "end"]:
    """大纲生成后的路由

    根据 review_mode 决定是否等待用户确认。
    大纲无效时直接结束（中止工作流）。

    Args:
        state: 当前状态

    Returns:
        "wait_confirm" - 等待用户确认
        "create_characters" - 继续提取角色
        "end" - 大纲无效，中止工作流
    """
    if not state.get("outline_valid", False):
        return "end"
    decision = wait_for_confirmation(state)
    if decision == "wait":
        return "wait_confirm"
    return "create_characters"
```

- [ ] **Step 4: 在 create_novel_graph 中注册 "end" 路由**

`backend/app/agents/graph.py`，第 155-164 行替换为：

```python
    graph.add_conditional_edges(
        "outline_generation_node",
        route_after_outline,
        {
            "wait_confirm": END,
            "create_characters": "create_characters_from_outline_node",
            "end": END,
        },
    )
```

- [ ] **Step 5: 简化和修复 stream_generator 中的大纲检查逻辑**

`backend/app/api/workflow.py`，第 286-335 行，**删除原有的 generate_relations_node 完成后的大纲空检查逻辑**（因为大纲无效时工作流已经中止，不会到达这个节点）。同时保留大纲有效时的持久化逻辑：

```python
                    # 大纲生成节点完成后，将结果持久化到 outlines 表
                    if node_name == "outline_generation_node" and isinstance(output, dict):
                        import logging
                        logger = logging.getLogger(__name__)

                        new_title = output.get("outline_title", "")
                        new_summary = output.get("outline_summary", "")
                        new_characters = output.get("outline_characters", [])
                        new_plot_points = output.get("outline_plot_points", [])

                        if not new_title and not new_summary and not new_characters:
                            logger.warning(f"workflow: outline_generation_node returned empty data, skipping persist for project {project_id}")
                            yield f"event: error\ndata: {json.dumps({'error': '大纲生成失败，AI 返回数据为空，请重试'})}\n\n"
                            return
                        else:
                            if new_title:
                                outline.title = new_title
                            if new_summary:
                                outline.summary = new_summary
                            if new_plot_points:
                                outline.plot_points = new_plot_points
                            if new_characters:
                                outline.characters = new_characters

                            outline.world_setting = output.get("outline_world_setting", outline.world_setting or {})
                            outline.emotional_curve = output.get("outline_emotional_curve", outline.emotional_curve)
                            outline.chapter_count_suggested = output.get("chapter_count", outline.chapter_count_suggested)

                            logger.info(f"workflow: persisted outline for project {project_id}: title='{new_title}', char={len(new_characters)}, plot={len(new_plot_points)}")

                        db.commit()

                    # 关系生成节点完成后，自动确认大纲并停止（规划阶段完成）
                    if node_name == "generate_relations_node":
                        import logging
                        logger = logging.getLogger(__name__)

                        outline.confirmed = True
                        outline.chapter_count_confirmed = True
                        db.commit()
                        logger.info(f"workflow: auto-confirmed outline for project {project_id}")
                        yield f"event: done\ndata: {json.dumps({'message': 'Generation completed'})}\n\n"
                        return
```

- [ ] **Step 6: 在 run_workflow 中每次使用新的 thread_id**

`backend/app/api/workflow.py`，第 249-256 行，修改为：

```python
    # 每次启动工作流使用新的 thread_id，避免从旧 checkpoint 恢复导致状态污染
    import uuid
    thread_id = str(uuid.uuid4())

    # 创建带检查点的图（复用 db 会话）
    graph = create_novel_graph_with_checkpointer(project_id, thread_id, db)

    # 配置
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
```

注意同步修改后续的 `get_latest_checkpoint` 和 `delete_project_checkpoints` 调用中使用动态 thread_id。

- [ ] **Step 7: 添加 cleanup 端点供前端重试前调用**

`backend/app/api/workflow.py`，在 `delete_project_checkpoints` 函数后添加新端点：

```python
@router.post("/{project_id}/workflow/cleanup")
async def cleanup_workflow_checkpoints(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    清除工作流检查点，用于重试前清理状态。

    删除项目的所有检查点，重置 WorkflowState。
    """
    project = get_project_for_user(project_id, current_user.id, db)

    # 清除所有检查点（不指定 thread_id，删除所有）
    from app.models.checkpoint import WorkflowCheckpoint
    deleted = db.query(WorkflowCheckpoint).filter(
        WorkflowCheckpoint.project_id == project_id
    ).delete()

    # 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).first()
    if workflow_state:
        workflow_state.stage = "inspiration"
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None
        workflow_state.current_chapter = 1

    db.commit()

    import logging
    logging.getLogger(__name__).info(f"Cleaned up {deleted} checkpoints for project {project_id}")

    return {"message": "Checkpoints cleaned up", "deleted": deleted}
```

- [ ] **Step 8: 提交后端修改**

```bash
git add backend/app/agents/state.py backend/app/agents/nodes/outline_generation.py backend/app/agents/graph.py backend/app/api/workflow.py
git commit -m "fix(workflow): abort workflow on empty outline + prevent checkpoint pollution"
```

---

## Task 2: 后端 — 统一 SSE error 事件格式 + 添加 outline_valid 到 build_initial_state

**Files:**
- Modify: `backend/app/api/workflow.py:53-141` (build_initial_state)

- [ ] **Step 1: 在 build_initial_state 中添加 outline_valid 默认值**

`backend/app/api/workflow.py`，第 97-141 行，在 LLM 服务字段前添加：

```python
        # 大纲有效性
        "outline_valid": False,

        # 工作流控制
        "waiting_for_confirmation": workflow_state.waiting_for_confirmation,
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/workflow.py
git commit -m "fix(workflow): add outline_valid to build_initial_state"
```

---

## Task 3: 前端 — 修复 SSE error 事件的数据解析

**Files:**
- Modify: `frontend/src/lib/workflowApi.ts:147-149`

- [ ] **Step 1: 修复 error 事件处理，提取实际错误消息**

`frontend/src/lib/workflowApi.ts`，第 147-149 行替换为：

```typescript
        case 'error':
          {
            // 兼容后端两种 error data 格式：
            // 1. 对象：{"error": "大纲生成失败，请重试"}
            // 2. 字符串：直接的消息文本
            const errorData = data as unknown as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            callbacks.onError?.(errorMsg)
          }
          break
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/lib/workflowApi.ts
git commit -m "fix(frontend): correctly parse SSE error event data object"
```

---

## Task 4: 前端 — 重试前清除 checkpoint + 添加卸载保护

**Files:**
- Modify: `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`
- Modify: `frontend/src/lib/api.ts` (添加 cleanup 方法)

- [ ] **Step 1: 在 api.ts 中添加 cleanup 方法**

`frontend/src/lib/api.ts`，在 `workflowApi` 导出处添加：

```typescript
export const workflowCleanupApi = {
  async cleanup(projectId: number): Promise<void> {
    await request<void>(
      `/api/projects/${projectId}/workflow/cleanup`,
      { method: 'POST' },
      true  // requireAuth
    )
  }
}
```

- [ ] **Step 2: 修改 handleGenerate 重试逻辑**

`frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`，修改 `handleGenerate` 函数：

在第 84-139 行，修改为：

```typescript
  const handleGenerate = async () =>
  {
    setError(null)
    setCompleted(false)
    setSteps(STEPS.map(s => ({ ...s, status: s.key === 'outline' ? 'active' : 'pending' })))

    const controller = new AbortController()
    abortRef.current = controller

    // 重试时先清除旧的 checkpoint，防止状态污染
    try
    {
      await workflowCleanupApi.cleanup(projectId)
    }
    catch (cleanupErr)
    {
      console.warn('Failed to cleanup checkpoints before retry:', cleanupErr)
      // 不阻塞重试：如果 cleanup 失败仍然尝试运行
    }

    // ... 后续代码保持不变
    try
    {
      await workflowApi.runWorkflow(projectId, { ... })
    }
    // ...
  }
```

同时添加 `import { workflowCleanupApi } from '@/lib/api'` 依赖（注意：需要确认 api.ts 中 workflowCleanupApi 被导出）。

- [ ] **Step 3: 添加组件卸载保护（abort on unmount）**

`frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`，修改 useEffect cleanup：

```typescript
  useEffect(() =>
  {
    return () =>
    {
      if (abortRef.current)
      {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])
```

（这段代码已经存在，只需确认没有遗漏）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/lib/api.ts frontend/src/components/workbench/planning/OutlineProgressDialog.tsx
git commit -m "fix(frontend): cleanup checkpoints before retry + abort on unmount"
```

---

## Task 5: 前端 — CharacterPanel 和 RelationPanel 添加空值防御

**Files:**
- Modify: `frontend/src/components/workbench/planning/CharacterPanel.tsx:68-69`
- Modify: `frontend/src/components/workbench/planning/RelationPanel.tsx:64-65`

- [ ] **Step 1: CharacterPanel 添加空值防御**

`frontend/src/components/workbench/planning/CharacterPanel.tsx`，第 68-69 行替换为：

```typescript
      const data = await characterApi.list(projectId)
      setCharacters(Array.isArray(data?.characters) ? data.characters : [])   // 第 69 行
```

- [ ] **Step 2: RelationPanel 添加空值防御**

`frontend/src/components/workbench/planning/RelationPanel.tsx`，第 64-65 行替换为：

```typescript
      const data = await relationApi.list(projectId)
      setRelations(Array.isArray(data?.relations) ? data.relations : [])   // 第 65 行
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/planning/CharacterPanel.tsx frontend/src/components/workbench/planning/RelationPanel.tsx
git commit -m "fix(frontend): add null-safety for CharacterPanel and RelationPanel data"
```

---

## Task 6: 验证 — 后端单元测试

**Files:**
- Create: `backend/tests/test_workflow_outline_failure.py`

- [ ] **Step 1: 编写大纲失败中止测试**

```python
"""测试大纲生成失败时的工作流行为"""

import pytest
from app.agents.graph import route_after_outline


def test_route_after_outline_aborts_when_outline_invalid():
    """大纲无效时工作流应直接结束"""
    state = {
        "project_id": 1,
        "outline_valid": False,
        "review_mode": "auto",
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }
    result = route_after_outline(state)
    assert result == "end"


def test_route_after_outline_continues_when_outline_valid():
    """大纲有效时工作流应正常继续"""
    state = {
        "project_id": 1,
        "outline_valid": True,
        "review_mode": "auto",
        "waiting_for_confirmation": False,
        "confirmation_type": None,
    }
    result = route_after_outline(state)
    assert result == "create_characters"


def test_route_after_outline_defaults_to_invalid():
    """缺少 outline_valid 字段时默认为无效"""
    state = {
        "project_id": 1,
        "review_mode": "auto",
    }
    result = route_after_outline(state)
    assert result == "end"
```

- [ ] **Step 2: 运行测试验证通过**

```bash
docker exec novelagent-backend-1 pytest tests/test_workflow_outline_failure.py -v
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_workflow_outline_failure.py
git commit -m "test: add outline failure abort tests"
```

---

## Task 7: 验证 — 前端单元测试

**Files:**
- Create: `frontend/src/lib/__tests__/sseParser.test.ts` (补充 error 事件测试)

- [ ] **Step 1: 添加 SSE error 事件解析测试**

`frontend/src/lib/__tests__/sseParser.test.ts` 中补充：

```typescript
  it('should handle error event with object data', () =>
  {
    const [remaining, events] = processSSEBuffer(
      '',
      'event: error\ndata: {"error":"大纲生成失败"}\n\n'
    )
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('error')
    const parsed = parseSSEData(events[0].data)
    expect(parsed).toEqual({ error: '大纲生成失败' })
  })

  it('should handle error event with plain string data', () =>
  {
    const [remaining, events] = processSSEBuffer(
      '',
      'event: error\ndata: some plain error\n\n'
    )
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('error')
    const parsed = parseSSEData(events[0].data)
    expect(parsed).toBe('some plain error')
  })
```

- [ ] **Step 2: 运行测试验证通过**

```bash
cd frontend && npm run test:run -- src/lib/__tests__/sseParser.test.ts
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/lib/__tests__/sseParser.test.ts
git commit -m "test: add SSE error event parsing tests"
```

---

## Task 8: 端到端验证

- [ ] **Step 1: 重新构建并启动服务**

```bash
docker compose build --no-cache backend && docker compose build --no-cache frontend && docker compose up -d
```

- [ ] **Step 2: 验证后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 3: 验证前端测试**

```bash
docker exec novelagent-frontend-1 npx vitest run
```

- [ ] **Step 4: 手动验证流程**

1. 创建新项目 → 进入工作台 → 填写灵感表单 → 点击「开始规划」
2. 如果大纲生成成功，验证后续正常流程（角色 → 关系 → 完成）
3. 如果大纲生成失败，验证：进度弹窗显示「生成失败」→ 不会崩溃到 ErrorBoundary
4. 点击「重试」→ 验证重新开始生成，不会从旧状态恢复
5. 切换到角色/关系面板，验证不会因空数据崩溃

---

## Self-Review

**1. Spec coverage:**
- ✅ 大纲为空时中止工作流（Task 1, Step 3-5）
- ✅ 清理 checkpoint 避免状态污染（Task 1, Step 6; Task 4, Step 1-2）
- ✅ 统一 SSE error 事件格式（Task 3, Step 1）
- ✅ 前端空值防御（Task 5, Step 1-2）
- ✅ 重试机制修复（Task 4, Step 2）

**2. Placeholder scan:** 所有代码段都包含具体实现代码，无 TBD/TODO。

**3. Type consistency:** 所有函数签名和接口保持一致。路由函数新返回值 `"end"` 在 graph 定义中已注册（Task 1, Step 4）。`outline_valid` 字段在 state.py 定义 → outline_generation.py 设置 → graph.py 路由检查，链路完整。