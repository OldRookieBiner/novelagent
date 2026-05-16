# 模型配置三项修复设计文档

> 日期: 2026-05-15
> 状态: 审查修订版

## 问题概述

1. 模型配置编辑模式缺少保存功能，修改后刷新/切换页面数据丢失
2. 灵感页 AI 模型下拉框按 provider 硬编码分组，应按用户配置的显示名称分组
3. 健康检查只测试第一个启用模型，应测试所有已添加模型

## 修复1：编辑模式自动保存

### 根因

`ModelConfigDetail.tsx` 编辑模式无保存入口。同时 `handleSaveModel` 对新建和编辑统一使用 `ModelConfigCreate`，编辑时应使用 `ModelConfigUpdate`（部分更新）。后端 `update_model_config` 对 `models` 整列替换，会覆盖健康检查写入的 `health_status`。

### 方案

**防抖自动保存**：每个字段变更 handler 显式触发防抖保存（不用 useEffect 监听状态，避免初始化/切换配置误触发）。编辑模式使用 `ModelConfigUpdate` 部分更新。

### 改动

**`frontend/src/types/index.ts`：**
- `ModelConfigUpdate` 新增 `provider?: string` 字段（支持编辑提供商）

**`frontend/src/components/settings/hooks/useSettings.ts`：**
- `handleSaveModel` 拆分为 `handleCreateModel(data: ModelConfigCreate)` 和 `handleUpdateModel(configId: number, data: ModelConfigUpdate)`
- `handleUpdateModel` 使用 `modelConfigsApi.update`

**`frontend/src/components/settings/ModelConfigDetail.tsx`：**
- 新建模式保持不变（底部"取消"和"添加配置"按钮，调用 `handleCreateModel`）
- 编辑模式：无底部栏，无保存状态 UI
- 新增防抖 hook：`useDebouncedCallback(fn, 500ms)`
- 每个字段变更 handler（setProvider/setName/setBaseUrl/setApiKey/setModels）在更新本地状态后，显式调用防抖保存
- 防抖保存仅在编辑模式下触发（`isEditMode && config?.id`）
- 编辑模式保存构建 `ModelConfigUpdate`：只发送变更字段，apiKey 为空时不传（保持原有不变）
- `onSave` prop 类型改为联合：`(data: ModelConfigCreate, configId?: number) => Promise<void>` 或单独的 `onUpdate` prop

**`backend/app/api/model_configs.py`：**
- `update_model_config` 更新 `models` 时，保留每个模型已有的 `health_status`/`health_latency`，不被前端传来的值覆盖：
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

### 自动保存触发时机

| 字段 | 触发方式 |
|------|----------|
| provider | Select onValueChange → setProvider + triggerDebouncedSave |
| name | Input onChange → setName + triggerDebouncedSave |
| baseUrl | Input onChange → setBaseUrl + triggerDebouncedSave |
| apiKey | Input onChange → setApiKey + triggerDebouncedSave |
| models | 添加/移除/温度/思考强度变更 → setModels + triggerDebouncedSave |

### 不触发的场景

- 新建模式（无 config.id）
- 初始化时 useEffect 重置状态（因为不是 useEffect 监听，而是 handler 显式触发）
- 切换选中配置时（只是 setProvider/setName 等，不调用 triggerDebouncedSave）

### 竞态防护

- 防抖回调执行时先检查 `config?.id` 是否仍有效（切换配置后旧防抖应作废）
- 使用 ref 追踪当前 configId，防抖回调中比对

## 修复2：灵感页模型下拉分组

### 根因

`InspirationPanel.tsx` 按 `provider`（如 "deepseek"、"openai"）分组，使用硬编码的 `providerNames` 映射显示名称。同一 provider 下多个配置被合并到同一分组，无法区分。`providerNames` 是重复数据源，与 `ModelConfig.name` 矛盾。

### 方案

按 `config.name`（用户在设置中定义的显示名称）分组。每个模型配置是独立分组，分组标签即配置名。删除 `providerNames` 硬编码。

### 改动

**`InspirationPanel.tsx`：**
- `ModelOption` 接口新增 `configName: string`，取 `config.name`
- 删除 `providerNames` 硬编码映射（234-242 行）
- 构建选项时 `configName: config.name`
- 分组逻辑改为按 `modelConfigId` 分组（保证唯一性：同一 config 下多个模型归同一组）
- `SelectLabel` 显示 `configName`

### 示例

修改前（按 provider 分组）：
```
DeepSeek (深度求索)
  ├ deepseek-chat        ← 来自 "DeepSeek Pro" 配置
  └ deepseek-reasoner    ← 来自 "DeepSeek Pro" 配置
OpenAI
  ├ gpt-4o               ← 来自 "OpenAI 主力" 配置
  └ gpt-4o-mini          ← 来自 "OpenAI 便宜版" 配置
```

修改后（按 config.name 分组）：
```
DeepSeek Pro            ← 用户自定义的配置名
  ├ deepseek-chat
  └ deepseek-reasoner
便宜版 DeepSeek          ← 同 provider 不同配置
  └ deepseek-chat
OpenAI 主力
  ├ gpt-4o
  └ gpt-4o-mini
OpenAI 便宜版
  └ gpt-4o-mini
```

## 修复3：健康检查测试所有模型

### 根因

后端 `check_model_health` 只取第一个启用模型测试。`ModelConfig` 顶层 `health_status`/`health_latency` 是 `single` 类型遗留，无法表达多模型逐个状态。前端无逐模型健康状态展示。

### 方案

后端并发测试所有模型，逐模型结果写入 `models` JSON。顶层 `health_status` 改为聚合值。前端 ModelCard 展示每个模型的健康状态。

### 后端改动

**`backend/app/schemas/model_config.py`：**
- 新增 `ModelHealthResult` schema：`model_id: str, model_name: str, status: str, latency: Optional[int], error: Optional[str]`
- `HealthCheckResponse` 新增 `model_results: Optional[list[ModelHealthResult]] = None`

**`backend/app/api/model_configs.py`：**
- `check_model_health` 改为并发测试 `config.models` 所有模型：
  ```python
  async def test_single_model(model_id, model_name, api_key, base_url):
      try:
          llm = LLMService(provider="custom", api_key=api_key, base_url=base_url, model=model_id)
          start = time.time()
          await asyncio.wait_for(llm.chat(messages=[{"role": "user", "content": "Hi"}], max_tokens=5), timeout=30)
          latency = int((time.time() - start) * 1000)
          return ModelHealthResult(model_id=model_id, model_name=model_name, status="healthy", latency=latency)
      except Exception as e:
          return ModelHealthResult(model_id=model_id, model_name=model_name, status="unhealthy", error=str(e))

  tasks = [test_single_model(m["id"], m["name"], api_key, config.base_url) for m in config.models]
  results = await asyncio.gather(*tasks)
  ```
- 逐模型 `health_status`/`health_latency` 写回 `config.models` JSON
- 顶层 `health_status` 改为聚合值：全部 healthy → "healthy"，任一 unhealthy → "unhealthy"
- `config.health_latency` 取健康模型中最小延迟
- 返回 `HealthCheckResponse` 含 `model_results`
- 总超时保护：`asyncio.wait_for(asyncio.gather(...), timeout=60)`

### 前端改动

**`frontend/src/types/index.ts`：**
- `HealthCheckResponse` 新增 `model_results?: ModelHealthResult[]`
- 新增 `ModelHealthResult` 接口：`model_id, model_name, status, latency?, error?`
- `ModelItem` 接口新增 `health_status?: string, health_latency?: number`

**`frontend/src/lib/api.ts`：**
- `checkHealth` 返回类型更新

**`frontend/src/components/settings/ModelCard.tsx`：**
- 显示健康状态指示器：
  - healthy：绿色圆点 + "Xms"
  - unhealthy：红色圆点 + 错误提示（hover 显示 error）
  - unknown/null：无指示器
- 从 `model.health_status` 和 `model.health_latency` 读取

**`frontend/src/components/settings/ModelConfigDetail.tsx`：**
- 健康检查按钮增加 loading 状态（checking... + disabled）
- 检查完成后刷新配置列表

**`frontend/src/components/settings/hooks/useSettings.ts`：**
- `handleCheckHealth` 传入 configId，完成后 `loadModelConfigs` + toast 反馈："X 个模型健康 / Y 个模型异常"

## 不涉及的改动

- 不修改 ModelConfig 数据库模型（不新增列，health_status 存在 models JSON 中）
- 不修改 LangGraph 工作流（此修复不涉及 AI 生成流程）
- 不修改新建模式交互
- 不添加保存状态 UI
