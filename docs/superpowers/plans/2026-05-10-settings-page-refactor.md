# 设置页面重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构设置页面，统一布局风格、增强模型配置功能、补全智能体 Prompt 管理。

**Architecture:** 前端：Settings 页面从 Layout 嵌套改为全屏独立路由，采用与工作台一致的 Header + Sidebar 布局。后端：fetchModels 端点去掉 provider_type 限制，改用 models_api 判断；模型配置统一使用 models 字段。后端补全 relation_generation 的 AGENT_TYPE 定义。

**Tech Stack:** React 18 + TypeScript + Zustand + Tailwind + FastAPI + Pydantic + SQLAlchemy

---

## File Structure

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| Modify | `frontend/src/App.tsx` | Settings 路由从嵌套改为独立 |
| Modify | `frontend/src/pages/Settings.tsx` | 重写为全屏布局 |
| Modify | `frontend/src/components/settings/hooks/useSettings.ts` | AGENT_TABS 添加 2 项 |
| Modify | `frontend/src/components/settings/ModelConfigDialog.tsx` | 统一获取模型逻辑 |
| Modify | `frontend/src/components/settings/ModelConfigItem.tsx` | single 类型展示模型标签 |
| Modify | `frontend/src/types/index.ts` | ProviderInfo 添加 models_api 字段 |
| Modify | `backend/app/api/model_configs.py` | fetchModels 去掉限制、build_config_response 兼容旧数据 |
| Modify | `backend/app/schemas/model_config.py` | ProviderInfo 添加 models_api |
| Modify | `backend/app/schemas/system_prompt.py` | AgentTypeKey 添加 relation_generation |
| Modify | `backend/app/api/system_prompts.py` | PROMPT_KEY_MAP 和 AGENT_TYPES 补全 |
| Modify | `backend/tests/test_system_prompts.py` | 更新 prompt 数量断言 |
| Modify | `frontend/src/pages/__tests__/Settings.test.tsx` | 更新测试匹配新布局 |

---

### Task 1: 后端 - 补全智能体 Prompt（AGENT_TYPES + PROMPT_KEY_MAP）

**Files:**
- Modify: `backend/app/schemas/system_prompt.py:17-24`
- Modify: `backend/app/api/system_prompts.py:20-27`
- Modify: `backend/tests/test_system_prompts.py:37`

- [ ] **Step 1: 更新 AgentTypeKey 添加 relation_generation**

在 `backend/app/schemas/system_prompt.py` 中，将 `AgentTypeKey` Literal 添加 `"relation_generation"`：

```python
AgentTypeKey = Literal[
    "outline_generation",
    "chapter_outline_generation",
    "chapter_content_generation",
    "review",
    "rewrite",
    "character_generation",
    "relation_generation",
]
```

- [ ] **Step 2: 在 AGENT_TYPES 字典中添加 character_generation 和 relation_generation 元数据**

在 `backend/app/schemas/system_prompt.py` 的 `AGENT_TYPES` 字典末尾（`"character_generation"` 之后）添加：

```python
"relation_generation": {
    "name": "关系生成",
    "description": "基于人物设定生成人物关系网络",
    "variables": ["characters_text", "world_era", "outline_summary"],
    "variable_descriptions": {
        "characters_text": "已生成的角色列表文本，包含姓名、性格、动机等",
        "world_era": "故事世界观的年代设定",
        "outline_summary": "小说大纲概述，用于确保关系与主线关联",
    },
},
```

注意：`character_generation` 的元数据已存在（第119-127行），无需重复添加。

- [ ] **Step 3: 在 PROMPT_KEY_MAP 添加 relation_generation 映射**

在 `backend/app/api/system_prompts.py` 的 `PROMPT_KEY_MAP` 字典中添加：

```python
"relation_generation": "prompt_relation_generation",
```

- [ ] **Step 4: 更新测试断言**

在 `backend/tests/test_system_prompts.py` 中，将 `assert len(data["prompts"]) == 6` 改为：

```python
assert len(data["prompts"]) == 7
# 7 agent types: outline_generation, chapter_outline_generation,
# chapter_content_generation, review, rewrite, character_generation, relation_generation
```

- [ ] **Step 5: 运行测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_system_prompts.py -v`
Expected: 所有测试 PASS，prompt 数量为 7

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/system_prompt.py backend/app/api/system_prompts.py backend/tests/test_system_prompts.py
git commit -m "feat(api): add relation_generation to AGENT_TYPES and PROMPT_KEY_MAP"
```

---

### Task 2: 后端 - fetchModels 支持 OpenAI 兼容 API

**Files:**
- Modify: `backend/app/api/model_configs.py:104-107`
- Modify: `backend/app/schemas/model_config.py:100-107`
- Modify: `backend/app/api/model_configs.py:77-89`

- [ ] **Step 1: 修改 fetchModels 端点，去掉 provider_type 限制**

在 `backend/app/api/model_configs.py` 中，将第 104-107 行：

```python
if provider_config["provider_type"] != "coding_plan":
    return FetchModelsResponse(
        models=[], error="该提供商不是 Coding Plan 类型", allow_manual=False
    )
```

替换为：

```python
if not provider_config.get("models_api"):
    return FetchModelsResponse(
        models=[], error="该提供商不支持获取模型列表", allow_manual=False
    )
```

- [ ] **Step 2: 更新 fetchModels 端点 docstring**

将 `fetch_available_models` 函数的 docstring 从：

```python
"""从 Coding Plan API 获取可用模型列表"""
```

改为：

```python
"""从提供商 API 获取可用模型列表（支持所有配置了 models_api 的提供商）"""
```

- [ ] **Step 3: 在 ProviderInfo schema 中添加 models_api 字段**

在 `backend/app/schemas/model_config.py` 的 `ProviderInfo` 类中添加 `models_api` 字段：

```python
class ProviderInfo(BaseModel):
    """提供商信息"""

    id: str
    name: str
    provider_type: str
    base_url: str
    models_api: Optional[str] = None
```

- [ ] **Step 4: 更新 list_providers 端点返回 models_api**

在 `backend/app/api/model_configs.py` 的 `list_providers` 函数中，将 `ProviderInfo` 构造改为：

```python
providers = [
    ProviderInfo(
        id=key,
        name=config["name"],
        provider_type=config["provider_type"],
        base_url=config["base_url"],
        models_api=config.get("models_api"),
    )
    for key, config in PRESET_PROVIDERS.items()
]
```

- [ ] **Step 5: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_api.py -v -k model`
Expected: 相关测试 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/model_configs.py backend/app/schemas/model_config.py
git commit -m "feat(api): fetchModels supports all providers with models_api"
```

---

### Task 3: 后端 - 模型配置读取兼容旧数据（model_name 回退到 models）

**Files:**
- Modify: `backend/app/api/model_configs.py:43-74`

- [ ] **Step 1: 修改 build_config_response 函数，兼容旧数据**

将 `backend/app/api/model_configs.py` 中的 `build_config_response` 函数改为：

```python
def build_config_response(c: ModelConfig) -> ModelConfigResponse:
    """构建模型配置响应"""
    # 转换 models 字段
    models = None
    if c.models:
        models = [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "is_enabled": m.get("is_enabled", True),
                "health_status": m.get("health_status"),
            }
            for m in c.models
        ]
    elif c.model_name:
        # 旧数据兼容：model_name 回退为单元素 models 列表
        models = [
            {
                "id": c.model_name,
                "name": c.model_name,
                "is_enabled": True,
                "health_status": c.health_status,
            }
        ]

    return ModelConfigResponse(
        id=c.id,
        name=c.name,
        provider=c.provider,
        provider_type=c.provider_type or "single",
        base_url=c.base_url,
        model_name=c.model_name,
        models=models,
        has_api_key=bool(c.api_key_encrypted),
        is_enabled=c.is_enabled,
        is_default=c.is_default,
        health_status=c.health_status,
        health_latency=c.health_latency,
        last_health_check=c.last_health_check,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )
```

- [ ] **Step 2: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_api.py -v`
Expected: 所有测试 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/model_configs.py
git commit -m "fix(api): model config response falls back to model_name when models is empty"
```

---

### Task 4: 前端 - ProviderInfo 类型更新 + AGENT_TABS 补全

**Files:**
- Modify: `frontend/src/types/index.ts:311-316`
- Modify: `frontend/src/components/settings/hooks/useSettings.ts:7-13`

- [ ] **Step 1: 更新 ProviderInfo 类型添加 models_api**

在 `frontend/src/types/index.ts` 中，将 `ProviderInfo` interface 改为：

```typescript
export interface ProviderInfo {
  id: string
  name: string
  provider_type: 'single' | 'coding_plan'
  base_url: string
  models_api?: string
}
```

- [ ] **Step 2: 更新 AGENT_TABS 添加人物生成和关系生成**

在 `frontend/src/components/settings/hooks/useSettings.ts` 中，将 `AGENT_TABS` 从：

```typescript
const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
  { id: 'review', label: '审核' },
  { id: 'rewrite', label: '重写' },
] as const
```

改为：

```typescript
const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
  { id: 'character_generation', label: '人物生成' },
  { id: 'relation_generation', label: '关系生成' },
  { id: 'review', label: '审核' },
  { id: 'rewrite', label: '重写' },
] as const
```

注意：人物生成和关系生成放在正文生成之后、审核之前，与工作流阶段顺序一致。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/settings/hooks/useSettings.ts
git commit -m "feat(frontend): add models_api to ProviderInfo type and complete AGENT_TABS"
```

---

### Task 5: 前端 - ModelConfigDialog 统一获取模型逻辑

**Files:**
- Modify: `frontend/src/components/settings/ModelConfigDialog.tsx`

- [ ] **Step 1: 修改对话框，用 models_api 判断是否显示"获取模型"按钮**

在 `ModelConfigDialog.tsx` 中，将 `isCodingPlan` 的判断逻辑从：

```typescript
const isCodingPlan = selectedProviderInfo?.provider_type === 'coding_plan' || editConfig?.provider_type === 'coding_plan'
```

改为：

```typescript
// 有 models_api 的提供商都支持获取模型列表
const hasModelsApi = selectedProviderInfo?.models_api || editConfig?.provider_type === 'coding_plan'
const isCodingPlan = selectedProviderInfo?.provider_type === 'coding_plan' || editConfig?.provider_type === 'coding_plan'
```

- [ ] **Step 2: 将模型选择区域的条件从 isCodingPlan 改为 hasModelsApi**

将原来的 Coding Plan 模型选择区域（约第 362-437 行）的条件：

```typescript
{isCodingPlan && (
```

改为：

```typescript
{hasModelsApi && (
```

将单模型名称输入区域（约第 342-360 行）的条件：

```typescript
{!isCodingPlan && selectedProvider && (
```

改为：

```typescript
{!hasModelsApi && selectedProvider && (
```

- [ ] **Step 3: 更新表单验证逻辑**

将 `getFormData` 函数中的验证条件（约第 189 行）：

```typescript
if (!isCodingPlan && !modelName.trim()) {
  newErrors.modelName = '请输入模型名称'
}
```

改为：

```typescript
if (!hasModelsApi && !modelName.trim()) {
  newErrors.modelName = '请输入模型名称'
}
```

将 coding_plan 验证条件（约第 194 行）：

```typescript
if (isCodingPlan) {
```

改为：

```typescript
if (hasModelsApi) {
```

- [ ] **Step 4: 更新表单提交数据构建逻辑**

将 `getFormData` 中构建提交数据的 provider_type 逻辑（约第 209 行）：

```typescript
provider_type: isCodingPlan ? 'coding_plan' : 'single',
```

保持不变（provider_type 仍由提供商原始类型决定，不由是否可获取模型决定）。

将 models 数据构建逻辑（约第 214-218 行）：

```typescript
if (isCodingPlan) {
  data.models = availableModels.filter(m => m.is_enabled)
} else {
  data.model_name = modelName.trim()
}
```

改为：

```typescript
if (hasModelsApi) {
  data.models = availableModels.filter(m => m.is_enabled)
} else {
  data.model_name = modelName.trim()
}
```

- [ ] **Step 5: 更新 label 文字**

将模型列表区域的 Label 从 `"模型列表"` 保持不变（已合理）。

将 "获取模型" 按钮附近的提示文字保持不变。

- [ ] **Step 6: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/settings/ModelConfigDialog.tsx
git commit -m "feat(frontend): ModelConfigDialog supports fetchModels for all providers with models_api"
```

---

### Task 6: 前端 - ModelConfigItem single 类型展示模型标签

**Files:**
- Modify: `frontend/src/components/settings/ModelConfigItem.tsx:49-103`

- [ ] **Step 1: 修改 single 类型的展示，当有 models 时显示模型标签**

将 `ModelConfigItem.tsx` 中 single 类型渲染部分（约第 49-103 行）替换为：

```tsx
// 单模型配置
if (config.provider_type === 'single') {
  // 有 models 列表时展示标签（新数据格式）
  const displayModels = config.models || []

  return (
    <div className="flex items-center p-3 border rounded-lg hover:bg-muted/50 transition-colors">
      {/* 默认标记 */}
      {config.is_default ? (
        <Star className="h-4 w-4 text-yellow-500 mr-2 fill-yellow-500" />
      ) : (
        <button
          onClick={() => onSetDefault?.(config.id)}
          className="h-4 w-4 mr-2 text-gray-300 hover:text-yellow-500 transition-colors"
          title="设为默认"
        >
          <Star className="h-4 w-4" />
        </button>
      )}

      {/* 名称 */}
      <span className="font-medium flex-1">{config.name}</span>

      {/* 模型信息 */}
      {displayModels.length > 0 ? (
        <span className="text-sm text-muted-foreground mr-3">
          {displayModels.length === 1
            ? displayModels[0].name
            : `${displayModels.filter(m => m.is_enabled).length} 个模型`}
        </span>
      ) : config.model_name ? (
        <span className="text-sm text-muted-foreground mr-3">{config.model_name}</span>
      ) : null}

      {/* 健康状态 */}
      <span className={cn('text-sm mr-3', getHealthColor(config.health_status))}>
        {getHealthText(config.health_status)}
        {config.health_latency && ` · ${config.health_latency}ms`}
      </span>

      {/* 操作按钮 */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onEdit?.(config)}
        title="编辑"
      >
        <Pencil className="h-4 w-4" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onRefresh?.(config.id)}
        title="健康检查"
      >
        <RefreshCw className="h-4 w-4" />
      </Button>
      {!config.is_default && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete?.(config.id)}
          title="删除"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/settings/ModelConfigItem.tsx
git commit -m "feat(frontend): ModelConfigItem displays model tags for single type with models"
```

---

### Task 7: 前端 - 设置页面布局重构（全屏布局 + Sidebar）

**Files:**
- Modify: `frontend/src/App.tsx:36-74`
- Modify: `frontend/src/pages/Settings.tsx`
- Modify: `frontend/src/pages/__tests__/Settings.test.tsx`

- [ ] **Step 1: 修改 App.tsx 路由，Settings 改为独立全屏路由**

将 `frontend/src/App.tsx` 中的路由从：

```tsx
{/* Settings 和项目重定向使用 Layout */}
<Route
  path="/"
  element={
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  }
>
  <Route path="project/:id" element={<RedirectToWorkbench />} />
  <Route path="settings" element={<Settings />} />
</Route>
```

改为：

```tsx
{/* 设置页面使用独立全屏布局 */}
<Route
  path="/settings"
  element={
    <PrivateRoute>
      <Settings />
    </PrivateRoute>
  }
/>
{/* 项目重定向使用 Layout */}
<Route
  path="/"
  element={
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  }
>
  <Route path="project/:id" element={<RedirectToWorkbench />} />
</Route>
```

- [ ] **Step 2: 重写 Settings.tsx 为全屏布局**

将 `frontend/src/pages/Settings.tsx` 整个文件替换为：

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Monitor, Shield, Bot, ArrowLeft } from 'lucide-react'
import { useSettings } from '@/components/settings/hooks/useSettings'
import Header from '@/components/layout/Header'
import ModelConfigPanel from '@/components/settings/ModelConfigPanel'
import ReviewConfigPanel from '@/components/settings/ReviewConfigPanel'
import AgentPromptPanel from '@/components/settings/AgentPromptPanel'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const SETTINGS_NAV = [
  {
    group: '配置',
    items: [
      { id: 'model' as const, label: '模型配置', icon: Monitor },
      { id: 'review' as const, label: '审核设置', icon: Shield },
    ],
  },
  {
    group: '智能体',
    items: [
      { id: 'agents' as const, label: 'Prompt 管理', icon: Bot },
    ],
  },
]

type SettingsTab = 'model' | 'review' | 'agents'

export default function Settings()
{
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const navigate = useNavigate()
  const {
    loading,
    // 模型配置
    modelConfigs,
    configsLoading,
    showConfigDialog,
    savingConfig,
    editingConfig,
    loadModelConfigs,
    handleSaveModel,
    handleEditModel,
    handleAddModel,
    handleSetDefault,
    handleDeleteModel,
    handleCheckHealth,
    handleCloseConfigDialog,
    // 审核设置
    reviewMode,
    setReviewMode,
    maxRewriteCount,
    setMaxRewriteCount,
    workflowMode,
    setWorkflowMode,
    saving,
    saved,
    handleSaveReviewSettings,
    // 系统提示词
    prompts,
    promptsLoading,
    loadPrompts,
    selectedAgent,
    setSelectedAgent,
    editContent,
    setEditContent,
    savingPrompt,
    resettingPrompt,
    handleSavePrompt,
    handleResetPrompt,
  } = useSettings()

  // 切换到模型配置 tab 时加载
  useEffect(() =>
  {
    if (activeTab === 'model')
    {
      loadModelConfigs()
    }
  }, [activeTab, loadModelConfigs])

  // 切换到智能体管理 tab 时加载
  useEffect(() =>
  {
    if (activeTab === 'agents')
    {
      loadPrompts()
    }
  }, [activeTab, loadPrompts])

  if (loading)
  {
    return <LoadingSpinner fullPage text="加载中..." />
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 页面 Header */}
      <header className="h-14 border-b bg-white flex items-center px-6 shrink-0">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors mr-4"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="text-sm">返回</span>
        </button>
        <h1 className="text-lg font-semibold">系统设置</h1>
      </header>

      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧导航栏 */}
        <nav className="w-[220px] border-r bg-white shrink-0">
          {SETTINGS_NAV.map((group) => (
            <div key={group.group}>
              <div className="px-4 pt-4 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {group.group}
              </div>
              {group.items.map((item) =>
              {
                const Icon = item.icon
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                      activeTab === item.id
                        ? 'text-primary bg-primary/10 border-r-2 border-primary font-medium'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    )}
                  >
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* 右侧内容区 */}
        <main className="flex-1 p-6 overflow-auto">
          {activeTab === 'model' && (
            <ModelConfigPanel
              modelConfigs={modelConfigs}
              configsLoading={configsLoading}
              onSetDefault={handleSetDefault}
              onEdit={handleEditModel}
              onDelete={handleDeleteModel}
              onCheckHealth={handleCheckHealth}
              onAdd={handleAddModel}
              showConfigDialog={showConfigDialog}
              savingConfig={savingConfig}
              editingConfig={editingConfig}
              onSaveModel={handleSaveModel}
              onCloseConfigDialog={handleCloseConfigDialog}
            />
          )}

          {activeTab === 'review' && (
            <ReviewConfigPanel
              reviewMode={reviewMode}
              maxRewriteCount={maxRewriteCount}
              onReviewModeChange={setReviewMode}
              onMaxRewriteCountChange={setMaxRewriteCount}
              workflowMode={workflowMode}
              onWorkflowModeChange={setWorkflowMode}
              saving={saving}
              saved={saved}
              onSave={handleSaveReviewSettings}
            />
          )}

          {activeTab === 'agents' && (
            <AgentPromptPanel
              prompts={prompts}
              promptsLoading={promptsLoading}
              selectedAgent={selectedAgent}
              editContent={editContent}
              savingPrompt={savingPrompt}
              resettingPrompt={resettingPrompt}
              onAgentChange={setSelectedAgent}
              onContentChange={setEditContent}
              onSave={handleSavePrompt}
              onReset={handleResetPrompt}
            />
          )}
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 更新 Settings 测试文件**

将 `frontend/src/pages/__tests__/Settings.test.tsx` 替换为：

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/utils'
import Settings from '@/pages/Settings'

// mock useSettings hook
const mockUseSettings = vi.fn(() => ({
  loading: false,
  modelConfigs: [],
  configsLoading: false,
  showConfigDialog: false,
  savingConfig: false,
  editingConfig: null,
  loadModelConfigs: vi.fn(),
  handleSaveModel: vi.fn(),
  handleEditModel: vi.fn(),
  handleAddModel: vi.fn(),
  handleSetDefault: vi.fn(),
  handleDeleteModel: vi.fn(),
  handleCheckHealth: vi.fn(),
  handleCloseConfigDialog: vi.fn(),
  reviewMode: 'manual',
  setReviewMode: vi.fn(),
  maxRewriteCount: 3,
  setMaxRewriteCount: vi.fn(),
  workflowMode: 'hybrid',
  setWorkflowMode: vi.fn(),
  saving: false,
  saved: false,
  handleSaveReviewSettings: vi.fn(),
  prompts: [],
  promptsLoading: false,
  loadPrompts: vi.fn(),
  selectedAgent: 'outline_generation',
  setSelectedAgent: vi.fn(),
  editContent: '',
  setEditContent: vi.fn(),
  savingPrompt: false,
  resettingPrompt: false,
  handleSavePrompt: vi.fn(),
  handleResetPrompt: vi.fn(),
}))

vi.mock('@/components/settings/hooks/useSettings', () => ({
  useSettings: () => mockUseSettings(),
}))

vi.mock('@/lib/api', () => ({
  settingsApi: { get: vi.fn(), update: vi.fn() },
  modelConfigsApi: { list: vi.fn() },
  systemPromptsApi: { list: vi.fn() },
  projectsApi: {},
  authApi: {},
  workflowApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

describe('Settings', () => {
  it('renders settings page with navigation', () => {
    render(<Settings />)

    expect(screen.getByText('系统设置')).toBeInTheDocument()
    expect(screen.getByText('模型配置')).toBeInTheDocument()
    expect(screen.getByText('审核设置')).toBeInTheDocument()
    expect(screen.getByText('Prompt 管理')).toBeInTheDocument()
  })

  it('renders back button', () => {
    render(<Settings />)

    expect(screen.getByText('返回')).toBeInTheDocument()
  })
})
```

- [ ] **Step 4: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/Settings.tsx frontend/src/pages/__tests__/Settings.test.tsx
git commit -m "refactor(frontend): Settings page uses fullscreen layout with sidebar navigation"
```

---

### Task 8: 集成验证 + 清理

**Files:**
- 无新文件

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 所有测试 PASS

- [ ] **Step 2: 运行全部前端测试**

Run: `cd frontend && npm run test:run`
Expected: 所有测试 PASS

- [ ] **Step 3: 重建前端并验证页面可访问**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 前端构建成功

- [ ] **Step 4: 访问 http://localhost:3001/settings 验证页面布局**

验证项：
- 页面为全屏布局（与工作台风格一致）
- 左侧导航有分组（配置/智能体）
- 模型配置 tab：点击"添加自定义模型"→ 选择"自定义"→ 有"获取模型"按钮
- 智能体 tab：显示 7 个 Prompt（大纲生成、章节大纲、正文生成、人物生成、关系生成、审核、重写）
- 审核设置 tab：工作流模式选择正常

- [ ] **Step 5: 更新 wolf anatomy**

更新 `.wolf/anatomy.md` 中变更的文件描述。

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: settings page refactor - integration verification and cleanup"
```
