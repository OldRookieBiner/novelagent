# 模型配置三项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复模型配置的三个根因问题：编辑模式无保存、灵感页分组错误、健康检查只测单模型

**Architecture:** 三个修复相互独立但共享 types 层。按后端优先→前端 types→前端组件的顺序实施。修复1（自动保存）和修复3（健康检查）在后端 update API 有交集（保留 health_status），需先改后端再改前端。

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Zustand (frontend), SQLAlchemy (ORM)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/schemas/model_config.py` | 新增 ModelHealthResult、HealthCheckResponse 扩展、ModelConfigUpdate 加 provider |
| Modify | `backend/app/api/model_configs.py` | update 保留 health_status、health 并发测试 |
| Modify | `frontend/src/types/index.ts` | ModelConfigUpdate 加 provider、ModelItem 加 health_latency、新增 ModelHealthResult、HealthCheckResponse 扩展 |
| Modify | `frontend/src/components/settings/hooks/useSettings.ts` | 拆分 handleSaveModel → handleCreateModel + handleUpdateModel、handleCheckHealth 加 toast |
| Modify | `frontend/src/components/settings/ModelConfigDetail.tsx` | 防抖自动保存、onUpdate prop、健康检查 loading |
| Modify | `frontend/src/components/settings/ModelCard.tsx` | 健康状态指示器 |
| Modify | `frontend/src/components/settings/ModelConfigPanel.tsx` | 传递 onUpdate prop |
| Modify | `frontend/src/pages/Settings.tsx` | 使用 handleCreateModel + handleUpdateModel |
| Modify | `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 按 config.name 分组、删除 providerNames |
| Create | `backend/tests/test_model_config_health_all.py` | 健康检查并发测试的后端测试 |

---

### Task 1: 后端 — ModelConfigUpdate 新增 provider 字段 + update 保留 health_status

**Files:**
- Modify: `backend/app/schemas/model_config.py:39-48`
- Modify: `backend/app/api/model_configs.py:296-303`

- [ ] **Step 1: 在 ModelConfigUpdate schema 新增 provider 字段**

在 `backend/app/schemas/model_config.py` 的 `ModelConfigUpdate` 类中添加 `provider` 字段：

```python
class ModelConfigUpdate(BaseModel):
    """更新模型配置"""

    name: Optional[str] = None
    provider: Optional[str] = None  # 新增：支持编辑提供商
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    models: Optional[list[ModelItem]] = None
    is_enabled: Optional[bool] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False
```

- [ ] **Step 2: 在 update_model_config 中处理 provider 字段**

在 `backend/app/api/model_configs.py` 的 `update_model_config` 函数中，在 `if request.name is not None:` 之后添加 provider 更新逻辑：

```python
    if request.provider is not None:
        config.provider = request.provider
```

- [ ] **Step 3: 修改 update_model_config 的 models 更新逻辑，保留 health_status/health_latency**

替换 `backend/app/api/model_configs.py` 中 `if request.models is not None:` 的处理逻辑（原代码第302-303行）：

```python
    if request.models is not None:
        # 保留已有模型的健康状态
        existing_health = {}
        if config.models:
            for m in config.models:
                existing_health[m.get("id")] = {
                    "health_status": m.get("health_status"),
                    "health_latency": m.get("health_latency"),
                }
        updated_models = []
        for m in request.models:
            item = m.model_dump()
            if m.id in existing_health:
                item["health_status"] = existing_health[m.id].get("health_status")
                item["health_latency"] = existing_health[m.id].get("health_latency")
            updated_models.append(item)
        config.models = updated_models
```

- [ ] **Step 4: 在 build_config_response 中补充 health_latency 字段透传**

在 `backend/app/api/model_configs.py` 的 `build_config_response` 函数中，models 构建逻辑（第49-57行）的 item dict 中添加 `health_latency`：

```python
            item = {
                "id": m.get("id"),
                "name": m.get("name"),
                "is_enabled": m.get("is_enabled", True),
                "health_status": m.get("health_status"),
                "health_latency": m.get("health_latency"),
                "temperature": m.get("temperature", 0.7),
                "reasoning_effort": m.get("reasoning_effort"),
            }
```

- [ ] **Step 5: 重启后端验证无报错**

Run: `docker compose restart backend && sleep 3 && docker compose logs backend --tail=20`
Expected: 无启动错误

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/model_config.py backend/app/api/model_configs.py
git commit -m "fix(backend): preserve health_status on model update, add provider to ModelConfigUpdate"
```

---

### Task 2: 后端 — 健康检查并发测试所有模型

**Files:**
- Modify: `backend/app/schemas/model_config.py:80-85`
- Modify: `backend/app/api/model_configs.py:341-404`
- Create: `backend/tests/test_model_config_health_all.py`

- [ ] **Step 1: 新增 ModelHealthResult schema 并扩展 HealthCheckResponse**

在 `backend/app/schemas/model_config.py` 中，在 `HealthCheckResponse` 之前添加：

```python
class ModelHealthResult(BaseModel):
    """单个模型健康检查结果"""

    model_id: str
    model_name: str
    status: str  # "healthy" | "unhealthy"
    latency: Optional[int] = None
    error: Optional[str] = None
```

修改 `HealthCheckResponse`：

```python
class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str  # "healthy" | "unhealthy"
    latency: Optional[int] = None
    error: Optional[str] = None
    model_results: Optional[list[ModelHealthResult]] = None
```

- [ ] **Step 2: 更新 import**

在 `backend/app/api/model_configs.py` 顶部的 import 中添加 `asyncio` 和 `ModelHealthResult`：

```python
import asyncio
import time
```

在 schema import 中添加 `ModelHealthResult`：

```python
from app.schemas.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelConfigListResponse,
    HealthCheckResponse,
    ModelHealthResult,
    FetchModelsRequest,
    FetchModelsResponse,
    ProviderInfo,
    ProvidersListResponse,
)
```

- [ ] **Step 3: 重写 check_model_health 函数**

替换 `backend/app/api/model_configs.py` 中整个 `check_model_health` 函数（第341-404行）：

```python
@router.post("/{config_id}/health", response_model=HealthCheckResponse)
async def check_model_health(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查模型健康状态 — 并发测试所有已添加模型"""
    config = (
        db.query(ModelConfig)
        .filter(ModelConfig.id == config_id, ModelConfig.user_id == current_user.id)
        .first()
    )

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found"
        )

    if not config.api_key_encrypted:
        return HealthCheckResponse(status="unhealthy", error="API Key 未配置")

    api_key = decrypt_api_key(config.api_key_encrypted, current_user.id)

    # 收集所有需要测试的模型
    models_to_test = []
    if config.models:
        for m in config.models:
            models_to_test.append({"id": m.get("id"), "name": m.get("name", m.get("id"))})
    elif config.model_name:
        models_to_test.append({"id": config.model_name, "name": config.model_name})

    if not models_to_test:
        return HealthCheckResponse(status="unhealthy", error="无可测试的模型")

    # 并发测试所有模型
    async def test_single_model(model_id: str, model_name: str) -> ModelHealthResult:
        try:
            llm = LLMService(
                provider="custom",
                api_key=api_key,
                base_url=config.base_url,
                model=model_id,
            )
            start = time.time()
            await asyncio.wait_for(
                llm.chat(messages=[{"role": "user", "content": "Hi"}], max_tokens=5),
                timeout=30,
            )
            latency = int((time.time() - start) * 1000)
            return ModelHealthResult(model_id=model_id, model_name=model_name, status="healthy", latency=latency)
        except Exception as e:
            return ModelHealthResult(model_id=model_id, model_name=model_name, status="unhealthy", error=str(e)[:200])

    # 并发执行，总超时 60s
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[test_single_model(m["id"], m["name"]) for m in models_to_test]),
            timeout=60,
        )
    except asyncio.TimeoutError:
        return HealthCheckResponse(status="unhealthy", error="健康检查超时")

    # 将逐模型健康状态写回 config.models JSON
    if config.models:
        result_map = {r.model_id: r for r in results}
        updated_models = []
        for m in config.models:
            item = dict(m)
            r = result_map.get(m.get("id"))
            if r:
                item["health_status"] = r.status
                item["health_latency"] = r.latency
            updated_models.append(item)
        config.models = updated_models

    # 聚合顶层健康状态
    healthy_count = sum(1 for r in results if r.status == "healthy")
    unhealthy_count = len(results) - healthy_count

    if unhealthy_count == 0:
        config.health_status = "healthy"
        config.health_latency = min((r.latency for r in results if r.latency is not None), default=None)
    else:
        config.health_status = "unhealthy"
        config.health_latency = None

    config.last_health_check = datetime.utcnow()
    db.commit()

    return HealthCheckResponse(
        status=config.health_status,
        latency=config.health_latency,
        model_results=results,
    )
```

- [ ] **Step 4: 写后端测试**

创建 `backend/tests/test_model_config_health_all.py`：

```python
"""测试健康检查并发测试所有模型"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.schemas.model_config import ModelHealthResult, HealthCheckResponse


def test_model_health_result_schema():
    """ModelHealthResult schema 正确构造"""
    r = ModelHealthResult(model_id="gpt-4o", model_name="GPT-4o", status="healthy", latency=150)
    assert r.model_id == "gpt-4o"
    assert r.status == "healthy"
    assert r.latency == 150

    r2 = ModelHealthResult(model_id="bad-model", model_name="Bad", status="unhealthy", error="timeout")
    assert r2.status == "unhealthy"
    assert r2.latency is None


def test_health_check_response_with_model_results():
    """HealthCheckResponse 支持 model_results 字段"""
    resp = HealthCheckResponse(
        status="unhealthy",
        model_results=[
            ModelHealthResult(model_id="m1", model_name="M1", status="healthy", latency=100),
            ModelHealthResult(model_id="m2", model_name="M2", status="unhealthy", error="fail"),
        ],
    )
    assert resp.status == "unhealthy"
    assert len(resp.model_results) == 2
    assert resp.model_results[1].status == "unhealthy"


def test_health_check_response_backward_compatible():
    """HealthCheckResponse 无 model_results 时向后兼容"""
    resp = HealthCheckResponse(status="healthy", latency=100)
    assert resp.model_results is None
```

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_model_config_health_all.py -v`
Expected: 3 个测试全部 PASS

- [ ] **Step 6: 重启后端验证**

Run: `docker compose restart backend && sleep 3 && docker compose logs backend --tail=20`
Expected: 无启动错误

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/model_config.py backend/app/api/model_configs.py backend/tests/test_model_config_health_all.py
git commit -m "feat(backend): concurrent health check for all models in config"
```

---

### Task 3: 前端 Types — 更新类型定义

**Files:**
- Modify: `frontend/src/types/index.ts:303-387`

- [ ] **Step 1: 更新 ModelItem 接口，新增 health_latency**

在 `frontend/src/types/index.ts` 中，修改 `ModelItem` 接口（第303-310行），在 `health_status` 后添加 `health_latency`：

```typescript
export interface ModelItem {
  id: string
  name: string
  is_enabled: boolean
  health_status?: string
  health_latency?: number
  temperature: number
  reasoning_effort?: string | null
}
```

- [ ] **Step 2: 更新 ModelConfigUpdate 接口，新增 provider**

修改 `ModelConfigUpdate` 接口（第373-381行），在 `name` 后添加 `provider`：

```typescript
export interface ModelConfigUpdate {
  name?: string
  provider?: string
  base_url?: string
  model_name?: string
  models?: ModelItem[]
  is_enabled?: boolean
  api_key?: string
  clear_api_key?: boolean
}
```

- [ ] **Step 3: 新增 ModelHealthResult 接口，扩展 HealthCheckResponse**

在 `HealthCheckResponse` 之前（第383行之前）添加：

```typescript
/** 单个模型健康检查结果 */
export interface ModelHealthResult {
  model_id: string
  model_name: string
  status: 'healthy' | 'unhealthy'
  latency?: number
  error?: string
}
```

修改 `HealthCheckResponse`（第383-387行）：

```typescript
export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy'
  latency?: number
  error?: string
  model_results?: ModelHealthResult[]
}
```

- [ ] **Step 4: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无类型错误（或仅已有错误，非本次改动引起）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "fix(frontend): add provider to ModelConfigUpdate, health_latency to ModelItem, ModelHealthResult type"
```

---

### Task 4: 前端 — useSettings 拆分 handleSaveModel + handleCheckHealth toast

**Files:**
- Modify: `frontend/src/components/settings/hooks/useSettings.ts:5,207-232,270-282`

- [ ] **Step 1: 更新 import 类型**

修改 `frontend/src/components/settings/hooks/useSettings.ts` 第5行，添加 `ModelConfigUpdate`：

```typescript
import type { SettingsUpdate, SystemPrompt, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types'
```

- [ ] **Step 2: 拆分 handleSaveModel 为 handleCreateModel + handleUpdateModel**

替换 `useSettings.ts` 中 `handleSaveModel` 函数（第207-232行）为两个函数：

```typescript
  // 创建模型配置
  const handleCreateModel = useCallback(async (data: ModelConfigCreate) =>
  {
    setSavingConfig(true)
    try
    {
      await modelConfigsApi.create(data)
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to create model config:', err)
      toast.error('创建模型配置失败')
    }
    finally
    {
      setSavingConfig(false)
    }
  }, [loadModelConfigs])

  // 更新模型配置（部分更新）
  const handleUpdateModel = useCallback(async (configId: number, data: ModelConfigUpdate) =>
  {
    try
    {
      await modelConfigsApi.update(configId, data)
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to update model config:', err)
      toast.error('更新模型配置失败')
    }
  }, [loadModelConfigs])
```

- [ ] **Step 3: 改进 handleCheckHealth，添加 toast 反馈**

替换 `handleCheckHealth` 函数（第270-282行）：

```typescript
  // 健康检查
  const handleCheckHealth = useCallback(async (configId: number) =>
  {
    try
    {
      const result = await modelConfigsApi.checkHealth(configId)
      await loadModelConfigs()
      // 反馈检查结果
      if (result.model_results && result.model_results.length > 0)
      {
        const healthy = result.model_results.filter(r => r.status === 'healthy').length
        const unhealthy = result.model_results.length - healthy
        if (unhealthy === 0)
        {
          toast.success(`全部 ${healthy} 个模型健康`)
        }
        else
        {
          toast.error(`${healthy} 个模型健康，${unhealthy} 个模型异常`)
        }
      }
      else if (result.status === 'healthy')
      {
        toast.success('模型连接正常')
      }
      else
      {
        toast.error(`模型异常：${result.error || '未知错误'}`)
      }
    }
    catch (err)
    {
      console.error('Health check failed:', err)
      toast.error('健康检查失败')
    }
  }, [loadModelConfigs])
```

- [ ] **Step 4: 更新 return 对象**

将 return 中的 `handleSaveModel` 替换为 `handleCreateModel` 和 `handleUpdateModel`：

```typescript
    handleCreateModel,
    handleUpdateModel,
```

（删除 `handleSaveModel,`）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/hooks/useSettings.ts
git commit -m "refactor(frontend): split handleSaveModel into create/update, add health check toast"
```

---

### Task 5: 前端 — ModelConfigDetail 防抖自动保存 + 健康检查 loading

**Files:**
- Modify: `frontend/src/components/settings/ModelConfigDetail.tsx`

- [ ] **Step 1: 更新 import 和 Props 类型**

修改 `frontend/src/components/settings/ModelConfigDetail.tsx`：

顶部 import 添加 `useRef, useCallback`：

```typescript
import { useState, useEffect, useRef, useCallback } from 'react'
import { ModelConfig, ModelConfigCreate, ModelConfigUpdate, ModelItem, ProviderInfo } from '@/types'
```

修改 Props 接口，将 `onSave` 改为 `onCreate` + `onUpdate`，`onCheckHealth` 改为接受 configId：

```typescript
interface ModelConfigDetailProps
{
  config: ModelConfig | null  // null = 新建模式
  providers: ProviderInfo[]
  onCreate: (data: ModelConfigCreate) => Promise<void>
  onUpdate: (configId: number, data: ModelConfigUpdate) => Promise<void>
  onSetDefault: (configId: number) => Promise<void>
  onDelete: () => void
  onCheckHealth: (configId: number) => Promise<void>
  saving: boolean
}
```

修改函数参数解构：

```typescript
export function ModelConfigDetail({
  config,
  providers,
  onCreate,
  onUpdate,
  onSetDefault,
  onDelete,
  onCheckHealth,
  saving,
}: ModelConfigDetailProps)
```

- [ ] **Step 2: 添加防抖自动保存逻辑（formStateRef 模式）**

在 `baseUrlAutoFilled` state 之后（第56行后），添加防抖保存逻辑：

```typescript
  // 防抖自动保存（编辑模式）— 使用 ref 避免闭包陷阱
  const configIdRef = useRef<number | null>(config?.id ?? null)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [healthChecking, setHealthChecking] = useState(false)

  // 用 ref 追踪最新表单状态，防抖回调从 ref 读取（避免 useCallback 闭包捕获旧值）
  const formStateRef = useRef({ name, provider, baseUrl, apiKey, models })
  useEffect(() =>
  {
    formStateRef.current = { name, provider, baseUrl, apiKey, models }
  }, [name, provider, baseUrl, apiKey, models])

  // 同步 configId ref
  useEffect(() =>
  {
    configIdRef.current = config?.id ?? null
  }, [config?.id])

  // 组件卸载时清理防抖计时器
  useEffect(() =>
  {
    return () =>
    {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current)
    }
  }, [])

  /**
   * 触发防抖自动保存（仅编辑模式）
   * 500ms 内无新变更才执行保存
   * 从 formStateRef 读取最新状态，避免闭包陷阱
   */
  const triggerAutoSave = useCallback(() =>
  {
    if (debounceTimerRef.current)
    {
      clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = setTimeout(() =>
    {
      const currentConfigId = configIdRef.current
      if (!currentConfigId) return  // 新建模式不自动保存

      // 从 ref 读取最新表单状态
      const { name, provider, baseUrl, apiKey, models } = formStateRef.current
      const data: ModelConfigUpdate = {
        name,
        provider,
        base_url: baseUrl,
        models,
      }
      if (apiKey)
      {
        data.api_key = apiKey
      }
      onUpdate(currentConfigId, data)
    }, 500)
  }, [onUpdate])  // 只依赖 onUpdate，不依赖表单状态（从 ref 读取）
```

注意：`triggerAutoSave` 只依赖 `onUpdate`，表单状态从 `formStateRef` 读取，避免 useCallback 闭包捕获旧值。

- [ ] **Step 3: 修改各字段 handler，编辑模式下显式触发防抖保存**

保持 `useEffect` 重置本地状态的代码不变（无需 skipAutoSaveRef，因为自动保存只在用户交互回调中触发，React state 变更不会触发 Select 的 onValueChange/Input 的 onChange）：

```typescript
  // 当 config prop 变化时（用户选择不同配置），重置本地状态
  useEffect(() =>
  {
    setProvider(config?.provider ?? '')
    setName(config?.name ?? '')
    setBaseUrl(config?.base_url ?? '')
    setApiKey('')
    setModels(config?.models ?? [])
    setBaseUrlAutoFilled(false)
  }, [config])
```

修改各 handler 在编辑模式下调用 `triggerAutoSave()`：

`handleProviderChange` 改为：
```typescript
  const handleProviderChange = (newProvider: string) =>
  {
    setProvider(newProvider)
    const found = providers.find(p => p.id === newProvider)
    if (found)
    {
      if (!baseUrl || baseUrlAutoFilled)
      {
        setBaseUrl(found.base_url)
        setBaseUrlAutoFilled(true)
      }
    }
    if (config?.id) triggerAutoSave()
  }
```

`handleBaseUrlChange` 改为：
```typescript
  const handleBaseUrlChange = (value: string) =>
  {
    setBaseUrl(value)
    setBaseUrlAutoFilled(false)
    if (config?.id) triggerAutoSave()
  }
```

name 的 Input onChange 改为：
```typescript
  onChange={e => { setName(e.target.value); if (config?.id) triggerAutoSave() }}
```

apiKey 的 Input onChange 改为：
```typescript
  onChange={e => { setApiKey(e.target.value); if (config?.id) triggerAutoSave() }}
```

models 相关 handler（handleAddModel, handleRemoveModel, handleTemperatureChange, handleReasoningEffortChange, handleModelCardRemove）在每个函数末尾添加：
```typescript
    if (config?.id) triggerAutoSave()
```

注意：这些 handler 使用 `setModels(prev => ...)` 形式，`triggerAutoSave` 需在 setState 之后调用。由于 React 批量更新，`triggerAutoSave` 中的 `models` 闭包值在 setTimeout 执行时可能未更新。解决方案：将 `triggerAutoSave` 的调用放在 `setTimeout(() => triggerAutoSave(), 0)` 中，确保在状态更新后执行。

对以上所有 handler 末尾改为：
```typescript
    setTimeout(() => { if (config?.id) triggerAutoSave() }, 0)
```

- [ ] **Step 4: 修改 handleSave（新建模式用）**

将 `handleSave` 改为只用于新建模式：

```typescript
  /**
   * 保存配置（仅新建模式使用）
   */
  const handleSave = async () =>
  {
    if (!provider || !baseUrl.trim())
    {
      toast.error('请填写提供商和API地址')
      return
    }
    const data: ModelConfigCreate = {
      name,
      provider,
      provider_type: 'single',
      base_url: baseUrl,
      model_name: models.length > 0 ? models[0].name : undefined,
      models,
      api_key: apiKey || undefined,
    }
    await onCreate(data)
  }
```

- [ ] **Step 5: 修改健康检查按钮，添加 loading + 传 configId**

替换健康检查按钮（第213-222行区域）：

```typescript
            {/* 健康检查按钮 */}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
              {
                if (config?.id)
                {
                  setHealthChecking(true)
                  onCheckHealth(config.id).finally(() => setHealthChecking(false))
                }
              }}
              disabled={healthChecking}
              className="text-xs h-7"
            >
              <Globe className="h-3.5 w-3.5 mr-1" />
              {healthChecking ? '检查中...' : '健康检查'}
            </Button>
```

- [ ] **Step 6: 移除编辑模式下多余的底部栏条件**

当前底部栏已有 `!isEditMode &&` 条件，编辑模式不显示。无需改动。

- [ ] **Step 7: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无新增类型错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/settings/ModelConfigDetail.tsx
git commit -m "feat(frontend): debounced auto-save for model config edit mode, health check loading state"
```

---

### Task 6: 前端 — ModelCard 健康状态指示器

**Files:**
- Modify: `frontend/src/components/settings/ModelCard.tsx`

- [ ] **Step 1: 添加健康状态指示器**

在 `frontend/src/components/settings/ModelCard.tsx` 中，在模型名称和移除按钮之间（第35-43行区域），修改头部区域：

```typescript
      {/* 头部：模型名称 + 健康状态 + 移除按钮 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-medium truncate">{model.name}</span>
          {/* 健康状态指示器 */}
          {model.health_status === 'healthy' && (
            <span className="flex items-center gap-1 text-[10px] text-green-600 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              {model.health_latency != null ? `${model.health_latency}ms` : ''}
            </span>
          )}
          {model.health_status === 'unhealthy' && (
            <span className="flex items-center gap-1 text-[10px] text-red-500 shrink-0" title={model.health_status === 'unhealthy' ? '连接异常' : undefined}>
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
              异常
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="text-red-500 text-xs hover:text-red-700 hover:underline shrink-0 ml-2"
        >
          移除
        </button>
      </div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/settings/ModelCard.tsx
git commit -m "feat(frontend): add health status indicator to ModelCard"
```

---

### Task 7: 前端 — ModelConfigPanel + Settings 适配新 Props

**Files:**
- Modify: `frontend/src/components/settings/ModelConfigPanel.tsx:9-14,72-74`
- Modify: `frontend/src/pages/Settings.tsx:42,154`

- [ ] **Step 1: 更新 ModelConfigPanel Props 和传递**

修改 `frontend/src/components/settings/ModelConfigPanel.tsx`：

更新 Props 接口：

```typescript
interface ModelConfigPanelProps
{
  modelConfigs: ModelConfig[]
  configsLoading: boolean
  selectedConfigId: number | null
  savingConfig: boolean
  onCreateModel: (data: ModelConfigCreate) => Promise<void>
  onUpdateModel: (configId: number, data: ModelConfigUpdate) => Promise<void>
  onSetDefault: (configId: number) => Promise<void>
  onDeleteModel: (configId: number) => Promise<void>
  onCheckHealth: (configId: number) => Promise<void>
  onToggleEnabled: (configId: number, enabled: boolean) => void
  onSelectConfig: (configId: number | null) => void
}
```

添加 `ModelConfigUpdate` import：

```typescript
import { ModelConfig, ModelConfigCreate, ModelConfigUpdate, ProviderInfo } from '@/types'
```

更新函数参数解构：

```typescript
export default function ModelConfigPanel({
  modelConfigs,
  configsLoading,
  selectedConfigId,
  savingConfig,
  onCreateModel,
  onUpdateModel,
  onSetDefault,
  onDeleteModel,
  onCheckHealth,
  onToggleEnabled,
  onSelectConfig,
}: ModelConfigPanelProps)
```

更新 `ModelConfigDetail` 的 props 传递：

```typescript
      <ModelConfigDetail
        config={selectedConfig}
        providers={providers}
        onCreate={onCreateModel}
        onUpdate={onUpdateModel}
        onSetDefault={onSetDefault}
        onDelete={() =>
        {
          if (selectedConfigId)
          {
            onDeleteModel(selectedConfigId)
          }
        }}
        onCheckHealth={onCheckHealth}
        saving={savingConfig}
      />
```

- [ ] **Step 2: 更新 Settings 页面**

修改 `frontend/src/pages/Settings.tsx`：

更新 import 中的 handler（第42行附近），将 `handleSaveModel` 改为 `handleCreateModel` 和 `handleUpdateModel`：

```typescript
    handleCreateModel,
    handleUpdateModel,
```

更新 `ModelConfigPanel` 的 props（第149-160行区域）：

```typescript
            <ModelConfigPanel
              modelConfigs={modelConfigs}
              configsLoading={configsLoading}
              selectedConfigId={selectedConfigId}
              savingConfig={savingConfig}
              onCreateModel={handleCreateModel}
              onUpdateModel={handleUpdateModel}
              onSetDefault={handleSetDefault}
              onDeleteModel={handleDeleteModel}
              onCheckHealth={handleCheckHealth}
              onToggleEnabled={handleToggleEnabled}
              onSelectConfig={handleSelectConfig}
            />
```

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无新增类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/ModelConfigPanel.tsx frontend/src/pages/Settings.tsx
git commit -m "refactor(frontend): adapt ModelConfigPanel and Settings to split create/update handlers"
```

---

### Task 8: 前端 — InspirationPanel 按 config.name 分组

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx:44-52,232-274,1040-1071`

- [ ] **Step 1: 修改 ModelOption 接口**

替换 `InspirationPanel.tsx` 中 `ModelOption` 接口（第44-52行）：

```typescript
/** 扁平化后的模型选项 */
interface ModelOption
{
  modelConfigId: number  // model_configs 表 ID
  modelName: string      // 具体模型名
  configName: string     // 模型配置的显示名称（用于分组标签）
  isDefault: boolean     // 是否为默认配置
}
```

删除 `providerName` 和 `provider` 字段，新增 `configName`。

- [ ] **Step 2: 修改加载模型列表逻辑**

替换 `InspirationPanel.tsx` 中加载模型列表的 `useEffect`（第224-296行）：

```typescript
  // 加载可用模型列表
  useEffect(() =>
  {
    const loadModels = async () =>
    {
      setLoadingModels(true)
      try
      {
        const response = await modelConfigsApi.list()
        const options: ModelOption[] = []
        for (const config of response.models)
        {
          // 只显示已启用的配置
          if (!config.is_enabled) continue
          // 统一遍历 config.models
          if (config.models && config.models.length > 0)
          {
            for (const model of config.models)
            {
              if (!model.is_enabled) continue
              options.push({
                modelConfigId: config.id,
                modelName: model.name,
                configName: config.name,
                isDefault: config.is_default,
              })
            }
          }
          else if (config.model_name)
          {
            // 旧数据回退
            options.push({
              modelConfigId: config.id,
              modelName: config.model_name,
              configName: config.name,
              isDefault: config.is_default,
            })
          }
        }
        setModelOptions(options)
        // 设置默认选中
        if (!selectedModelKey)
        {
          const defaultOption = options.find(o => o.isDefault) || options[0]
          if (defaultOption)
          {
            setSelectedModelKey(`${defaultOption.modelConfigId}:${defaultOption.modelName}`)
          }
        }
      }
      catch (err)
      {
        console.error('Failed to load model options:', err)
      }
      finally
      {
        setLoadingModels(false)
      }
    }
    loadModels()
  }, [])
```

- [ ] **Step 3: 修改 Select 分组逻辑**

替换 `InspirationPanel.tsx` 中 Select 分组渲染（第1040-1071行）：

```typescript
                <SelectContent>
                  {/* 按模型配置名称分组 */}
                  {(() =>
                  {
                    // 按 modelConfigId 分组（同一配置下的模型归为一组）
                    const grouped = new Map<number, ModelOption[]>()
                    for (const opt of modelOptions)
                    {
                      if (!grouped.has(opt.modelConfigId))
                      {
                        grouped.set(opt.modelConfigId, [])
                      }
                      grouped.get(opt.modelConfigId)!.push(opt)
                    }
                    return Array.from(grouped.entries()).map(([configId, options]) => (
                      <SelectGroup key={configId}>
                        <SelectLabel>{options[0].configName}</SelectLabel>
                        {options.map(opt => (
                          <SelectItem
                            key={`${opt.modelConfigId}:${opt.modelName}`}
                            value={`${opt.modelConfigId}:${opt.modelName}`}
                          >
                            <span className="flex items-center gap-1.5">
                              {opt.modelName}
                              {opt.isDefault && (
                                <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">默认</span>
                              )}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    ))
                  })()}
                </SelectContent>
```

- [ ] **Step 4: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无新增类型错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "fix(frontend): group model selector by config.name instead of hardcoded provider"
```

---

### Task 9: 端到端验证

**Files:** None (verification only)

- [ ] **Step 1: 重建前端并验证**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功

- [ ] **Step 2: 重启后端**

Run: `docker compose restart backend`
Expected: 后端正常启动

- [ ] **Step 3: 运行后端测试**

Run: `docker exec novelagent-backend-1 pytest tests/test_model_config_health_all.py -v`
Expected: 全部 PASS

- [ ] **Step 4: 运行前端类型检查**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit`
Expected: 无新增错误

- [ ] **Step 5: 功能验证清单**

手动验证：
1. 模型配置编辑模式：修改名称/地址/API Key → 切换页面 → 切回 → 数据已保存
2. 灵感页面：模型下拉按配置名称分组，不再是 "DeepSeek (深度求索)" 等硬编码
3. 健康检查：点击"健康检查" → 按钮显示"检查中..." → 完成后 toast 反馈 → 每个模型卡片显示健康状态
4. 新建模式：底部"添加配置"按钮仍正常工作
