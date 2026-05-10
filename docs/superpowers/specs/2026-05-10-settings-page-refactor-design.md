# 设置页面重构设计文档

**日期**：2026-05-10
**版本**：v0.9.0
**状态**：已确认

---

## 概述

重构设置页面，解决三个核心问题：布局与工作台不统一、模型配置功能受限（无法获取中转站/自定义 API 的模型列表）、智能体 Prompt 管理不完整。

**设计原则**：符合 LangGraph 框架规范，不积累技术债，不改变当前系统使用流程，保证系统稳定运行。

---

## 问题分析

### 1. 布局不统一

| 维度 | 当前设置页面 | 工作台 |
|------|------------|--------|
| 路由 | 嵌套在 `Layout` 组件下（Header + container） | 独立全屏路由 |
| 左侧导航 | 220px 宽，在内容区内，样式简陋 | 全屏 Sidebar，分组+图标 |
| 页面 Header | 无 | 项目 Header（标题 + 进度条） |
| 整体风格 | 传统 container 布局 | 现代全屏布局 |

### 2. 模型配置功能受限

- `fetchModels` 端点只支持 `coding_plan` 类型提供商
- `custom`（中转站等 OpenAI 兼容 API）虽然配置了 `models_api: "/v1/models"`，但被拒绝
- `single` 类型只能手动输入模型名，无法从列表选择
- 一个 API 配置多个模型的场景只支持 coding_plan

### 3. 智能体 Prompt 不完整

| Prompt | 后端 DEFAULT_PROMPTS | 后端 AGENT_TYPES | 前端 AGENT_TABS |
|--------|---------------------|------------------|-----------------|
| outline_generation | ✓ | ✓ | ✓ |
| chapter_outline_generation | ✓ | ✓ | ✓ |
| chapter_content_generation | ✓ | ✓ | ✓ |
| review | ✓ | ✓ | ✓ |
| rewrite | ✓ | ✓ | ✓ |
| character_generation | ✓ | ✓ | **缺失** |
| relation_generation | ✓ | **缺失** | **缺失** |

---

## 设计方案

### 一、布局统一

#### 1.1 路由变更

设置页面从 `Layout` 嵌套路由改为独立全屏路由：

```tsx
// App.tsx - 修改前
<Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
  <Route path="settings" element={<Settings />} />
</Route>

// App.tsx - 修改后
<Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
```

#### 1.2 页面结构

设置页面采用与工作台一致的全屏布局：

```
┌──────────────────────────────────────────────────┐
│  NovelAgent                        admin ⚙ 🚪    │  ← 全局 Header (复用)
├──────────────────────────────────────────────────┤
│  ← 返回  系统设置                                 │  ← 页面 Header
├──────────┬───────────────────────────────────────┤
│ 配置      │                                       │
│  模型配置  │       内容区                           │
│  审核设置  │                                       │
│ 智能体    │                                       │
│  Prompt管理│                                       │
│           │                                       │
└──────────┴───────────────────────────────────────┘
```

#### 1.3 Sidebar 设计

- 宽度：220px（与工作台 Sidebar 一致）
- 分组导航：配置（模型配置、审核设置）/ 智能体（Prompt 管理）
- 每项带 lucide-react 图标
- 配色与工作台 Sidebar 统一（背景色、激活态、hover 态）

#### 1.4 涉及文件

| 文件 | 改动 |
|------|------|
| `frontend/src/App.tsx` | 路由调整：settings 改为独立全屏路由 |
| `frontend/src/pages/Settings.tsx` | 重写：全屏布局 + 页面 Header + Sidebar |
| `frontend/src/components/settings/` | 各面板组件保持不变，由新布局包裹 |

---

### 二、模型配置增强

#### 2.1 后端：fetchModels 支持所有 OpenAI 兼容 API

**改动文件**：`backend/app/api/model_configs.py`

**当前逻辑**：
```python
if provider_info.provider_type != 'coding_plan':
    raise HTTPException(400, "该提供商不是 Coding Plan 类型")
```

**新逻辑**：
```python
if not provider_info.models_api:
    raise HTTPException(400, "该提供商不支持获取模型列表")
```

**影响范围**：
- `custom` 提供商已有 `models_api: "/v1/models"`，自动支持
- `deepseek`（无 models_api）仍不支持，保持现状
- `coding_plan` 类型提供商不受影响

#### 2.2 后端：single 类型支持多模型

**改动文件**：`backend/app/api/model_configs.py`, `backend/app/schemas/model_config.py`

**核心改动**：
- `ModelConfigCreate` schema：`model_name` 变为可选，统一使用 `models` 字段
- 创建/更新模型配置时：如果 `models` 有值则存入 `models` JSON 字段，否则回退到 `model_name`
- 旧数据兼容：读取时如果 `models` 为空但 `model_name` 有值，构造单元素 `models` 列表返回

**Schema 变更**：
```python
class ModelConfigCreate(BaseModel):
    name: str
    provider: str
    base_url: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None  # 可选，兼容旧数据
    models: Optional[list[ModelItem]] = None  # 新：统一使用
    is_default: bool = False
```

**返回数据兼容**：
```python
# 读取时兼容旧数据
if config.models:
    result_models = config.models
elif config.model_name:
    result_models = [{"id": config.model_name, "name": config.model_name, "is_enabled": True}]
```

#### 2.3 前端：模型配置弹窗统一

**改动文件**：`frontend/src/components/settings/ModelConfigDialog.tsx`

**当前问题**：
- single 类型：只有手动输入 model_name 的文本框
- coding_plan 类型：有"获取模型"按钮 + 模型选择列表

**新设计**：
- 所有配置了 `models_api` 的提供商都显示"获取模型"按钮
- 获取成功后展示模型选择列表
- 如果获取失败或提供商无 `models_api`，退回手动输入模式
- 选择模型后统一存入 `models` 字段

**表单流程**：
```
选择提供商 → 填写 base_url + api_key →
  ├─ 有 models_api → [获取模型] → 模型选择列表（可手动输入）
  └─ 无 models_api → 手动输入模型名
```

#### 2.4 涉及文件

| 文件 | 改动 |
|------|------|
| `backend/app/api/model_configs.py` | fetchModels 去掉 provider_type 限制；创建/更新支持 models 字段 |
| `backend/app/schemas/model_config.py` | ModelConfigCreate 的 model_name 改为可选 |
| `backend/app/models/model_config.py` | 无需改动（models JSON 字段已存在） |
| `backend/app/services/model_providers.py` | 无需改动（custom 已有 models_api） |
| `frontend/src/components/settings/ModelConfigDialog.tsx` | 统一获取模型逻辑 |
| `frontend/src/components/settings/ModelConfigItem.tsx` | single 类型也展示模型标签 |
| `frontend/src/types/index.ts` | ModelConfigCreate 类型更新 |

---

### 三、智能体 Prompt 补全

#### 3.1 后端补全

**改动文件 1**：`backend/app/schemas/system_prompt.py`

添加 `relation_generation` 到 `AgentTypeKey`：
```python
AgentTypeKey = Literal[
    "outline_generation",
    "chapter_outline_generation",
    "chapter_content_generation",
    "review",
    "rewrite",
    "character_generation",
    "relation_generation",  # 新增
]
```

**改动文件 2**：`backend/app/api/system_prompts.py`

`PROMPT_KEY_MAP` 添加 `relation_generation` 映射：
```python
"relation_generation": "prompt_relation_generation",
```

> 注：`get_prompt_key` 有 fallback `f"prompt_{agent_type}"`，不添加也能工作，但显式添加更清晰。

`AGENT_TYPES` 字典添加：
```python
"character_generation": {
    "name": "人物生成",
    "description": "根据小说大纲概述和世界观设定，生成性格鲜明的人物角色列表",
    "variables": ["outline_summary", "world_era"],
    "variable_descriptions": {
        "outline_summary": "小说大纲的概述内容，包含核心冲突和故事主线",
        "world_era": "故事世界观的年代设定，如古代、现代、未来、架空",
    },
},
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

#### 3.2 前端补全

**改动文件**：`frontend/src/components/settings/hooks/useSettings.ts`

`AGENT_TABS` 添加：
```typescript
{ id: 'character_generation', label: '人物生成' },
{ id: 'relation_generation', label: '关系生成' },
```

#### 3.3 不变的部分

- `prompts.py` 的 `DEFAULT_PROMPTS` 已包含这两个 prompt，无需修改
- `prompt_loader.py` 加载逻辑不变
- 前端编辑/保存/重置交互不变

#### 3.4 涉及文件

| 文件 | 改动 |
|------|------|
| `backend/app/schemas/system_prompt.py` | AgentTypeKey 添加 relation_generation |
| `backend/app/api/system_prompts.py` | AGENT_TYPES 添加 character_generation 和 relation_generation 元数据 |
| `frontend/src/components/settings/hooks/useSettings.ts` | AGENT_TABS 添加人物生成和关系生成 |

---

## 数据兼容性

### 模型配置数据迁移

无需数据库迁移。现有 `model_name` 字段保留，`models` JSON 字段已存在。

**读取兼容**：
- 旧数据：`models=null, model_name="gpt-4"` → 前端构造单元素列表展示
- 新数据：`models=[{id:"gpt-4",name:"GPT-4",is_enabled:true}], model_name=null`

**写入兼容**：
- 新创建的配置统一使用 `models` 字段
- `model_name` 保留但不再作为主字段

### 系统提示词数据迁移

无需数据库迁移。`relation_generation` 的 prompt 已在 `DEFAULT_PROMPTS` 中定义，`prompt_loader` 会自动加载。

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 模型配置弹窗改动影响现有配置流程 | 保留手动输入模式作为 fallback |
| 旧数据 model_name 为空时前端展示异常 | 读取时兼容：models 为空则回退到 model_name |
| fetchModels 对某些 API 返回格式不同 | 前端做好错误处理，获取失败时退回手动输入 |
| 设置页面路由变更影响导航 | Header 的设置链接改为 `/settings` 直接路由 |

---

## 不涉及的内容

- 不改变工作流执行逻辑
- 不改变 LangGraph 节点实现
- 不改变模型选择器在工作台中的使用方式
- 不新增数据库表或迁移文件
