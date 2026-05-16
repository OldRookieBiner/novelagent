# 模型配置页面优化设计文档

## 概述

优化"设置-模型配置"页面，支持温度和思考强度配置，并重构页面为双栏布局。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 思考强度实现 | `reasoning_effort` (OpenAI 标准) | 最通用的思考控制方式，兼容 API 均支持 |
| 参数作用域 | 模型级别 | 每个 ModelItem 独立设置温度和思考强度，不同模型参数不同 |
| 页面布局 | 双栏（左列表 + 右详情） | 替代原弹窗模式，浏览和编辑更高效 |
| 模型选取 | 两步式：获取模型弹窗 → 主页配置参数 | 弹窗只负责选取，参数在主页设置，交互更清晰 |
| 启用开关 | 复用 `ModelConfig.is_enabled` | 开启则在灵感页模型选择下拉框可见，关闭则不可见 |
| 数据统一 | 所有配置统一使用 models 列表 | single 类型也存为单元素 models 数组，消除 provider_type 分歧 |

## 数据模型变更

### 统一 models 列表

**关键变更**：取消 `provider_type`（single/coding_plan）的区分，所有配置统一使用 `models` JSON 列表。

- **single 类型**：`models` 为单元素数组 `[{id: "gpt-4", name: "gpt-4", ...}]`
- **多模型类型**：`models` 为多元素数组
- **`model_name` 字段**：保留但不作为主要数据源，从 models[0].name 回退读取

**理由**：
1. 消除 single/coding_plan 分支逻辑，前端和后端代码简化
2. temperature/reasoning_effort 存储在 ModelItem 上，single 类型也需要 ModelItem
3. 旧数据兼容：`model_name` 字段仍存在，读取时优先 models，回退 model_name

### ModelItem 扩展

在现有 `ModelItem`（models JSON 数组元素）中增加两个字段：

```python
# 新增字段
{
    "id": "deepseek-v4",
    "name": "deepseek-v4",
    "is_enabled": true,
    "health_status": "healthy",
    "temperature": 0.7,          # 新增：温度，默认 0.7，范围 0-2
    "reasoning_effort": "none"   # 新增：思考强度，默认 none
}
```

**reasoning_effort 可选值**：`none` / `low` / `medium` / `high` / `xhigh`

**UI 到 API 映射**：

| UI 显示 | API 值 | 说明 |
|---------|--------|------|
| 关闭 | `none` | 不使用思考（默认） |
| 低 | `low` | 快速响应 |
| 中 | `medium` | 平衡 |
| 高 | `high` | 深度思考 |
| 最强 | `xhigh` | 最强推理 |

### 无需数据库迁移

`models` 字段是 JSON 列，新增字段直接存储在 JSON 中，无需 Alembic 迁移。旧数据缺少这两个字段时，后端返回默认值（temperature=0.7, reasoning_effort=null 表示 none）。

### is_enabled 两层语义

| 层级 | 字段 | 作用 |
|------|------|------|
| ModelConfig 级别 | `is_enabled` | 左栏启用开关。关闭 = 整个配置在灵感页不可见 |
| ModelItem 级别 | `is_enabled` | 单个模型的启用状态。关闭 = 该模型在灵感页下拉框中不可见 |

灵感页加载逻辑（已有，不需改动）：先检查 `config.is_enabled`，再检查 `model.is_enabled`，两层都通过才显示。

### Schema 变更

**ModelItem**（Pydantic）新增：
```python
class ModelItem(BaseModel):
    id: str
    name: str
    is_enabled: bool = True
    health_status: Optional[str] = None
    temperature: float = 0.7           # 新增
    reasoning_effort: Optional[str] = None  # 新增：none/low/medium/high/xhigh
```

**前端类型**同步更新。

### LLMService 变更

**构造函数变更**：

```python
def __init__(self, provider, api_key, base_url, model,
             temperature=0.7, reasoning_effort=None):
    self.temperature = temperature
    self.reasoning_effort = reasoning_effort
```

**chat() / chat_stream() 变更**：

使用 `self.temperature` 和 `self.reasoning_effort` 作为默认值，仍允许调用时覆盖。`reasoning_effort` 为 `None` 或 `"none"` 时不传给 API。

```python
async def chat(
    self, messages: list[dict], temperature: float = None,
    max_tokens: int = 4096, reasoning_effort: str = None
) -> str:
    temp = temperature if temperature is not None else self.temperature
    effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort

    kwargs = {
        "model": self.model,
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tokens,
    }
    if effort and effort != "none":
        kwargs["reasoning_effort"] = effort
    response = await self.client.chat.completions.create(**kwargs)
```

`chat_stream()` 同理。

### get_llm_service_from_config 变更

从 `ModelConfig.models` 中查找目标 ModelItem，读取 temperature/reasoning_effort：

```python
def get_llm_service_from_config(model_config, user_id, model_override=None):
    # 解密 API Key...

    # 确定模型名：优先 model_override > models 列表第一个启用模型 > model_name
    model = model_override or model_config.model_name
    target_item = None

    if model_config.models:
        for m in model_config.models:
            if m.get("is_enabled", True):
                if not model or m.get("id") == model or m.get("name") == model:
                    model = m.get("id") or m.get("name")
                    target_item = m
                    break

    # 读取 temperature 和 reasoning_effort
    temperature = target_item.get("temperature", 0.7) if target_item else 0.7
    reasoning_effort = target_item.get("reasoning_effort") if target_item else None

    return LLMService(
        provider=model_config.provider,
        api_key=api_key,
        base_url=model_config.base_url,
        model=model,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )
```

**关键**：当 `model_override` 传入时（如灵感页选择特定模型），从 models 列表中匹配对应 ModelItem 读取参数。当无 model_override 时取第一个启用模型。

### 节点调用链路

LLM 调用链路：`Node → get_llm_from_state() → get_llm_for_user() → get_llm_service_from_config() → LLMService`

1. `get_llm_service_from_config()` 从 models 列表找到目标 ModelItem
2. 读取其 `temperature` 和 `reasoning_effort`
3. 传给 `LLMService` 构造函数
4. 节点调用 `llm.chat()` / `llm.chat_stream()` 时自动使用配置值

**节点代码不需要修改**，temperature/reasoning_effort 透传在基础设施层完成。

## 前端页面设计

### 页面布局

Settings 页面已有左侧导航栏（模型配置/审核设置/Prompt 管理）。选择"模型配置"Tab 后，**右侧内容区**显示双栏布局：

```
┌─────────────────────────────────────────────────┐
│ 全局 Header                                      │
├──────┬──────────────────────────────────────────┤
│ 设置 │ 模型配置 Tab 内容                           │
│ 导航 │ ┌─────────┬──────────────────────────┐   │
│      │ │ 平台列表  │ 配置详情 / 新增表单          │   │
│ 模型  │ │ ★ DS V4 │ [基础信息]  [获取模型]       │   │
│ 配置  │ │ ☆ GPT-4 │ ┌──────────────────────┐ │   │
│      │ │ ☆ Ollama│ │ deepseek-v4          │ │   │
│ 审核  │ │         │ │ 温度: ═══●═══  0.7    │ │   │
│ 设置  │ │ + 添加  │ │ 思考: 关闭 低 中 高 最强│ │   │
│      │ │         │ └──────────────────────┘ │   │
│ 智能体│ │         │ ┌──────────────────────┐ │   │
│      │ │         │ │ deepseek-reasoner    │ │   │
│      │ │         │ │ 温度: ●═══════  0.3    │ │   │
│      │ │         │ │ 思考: 关闭 低 中 ●高 最强│ │   │
│      │ │         │ └──────────────────────┘ │   │
│      │ └─────────┴──────────────────────────┘   │
└──────┴──────────────────────────────────────────┘
```

**左栏（240px）**：平台配置列表
- 每个配置项：名称 + 模型数量 + 健康状态 + 启用开关
- 选中态蓝色高亮 + 左侧蓝色边框
- 底部"添加配置"按钮
- 启用开关（复用 is_enabled）：开启在灵感页模型选择下拉框可见，关闭不可见
- 停用的配置降低透明度

**右栏**：配置详情 / 新增表单
- 基础信息（提供商/名称/API地址/API Key）双列网格布局
- "获取模型"按钮
- 模型卡片列表，每个模型包含：
  - 模型名称 + 移除按钮
  - 温度 Slider（0-2，步长 0.1，默认 0.7）
  - 思考强度 5 档选择（关闭/低/中/高/最强，默认关闭）
- 健康检查 / 删除按钮在右栏顶部

### 获取模型弹窗

点击"获取模型"后弹出独立弹窗：
- 搜索框过滤模型
- 模型列表：已添加的显示绿色背景 + "移除"按钮，未添加的显示"添加"按钮
- 底部显示已选模型数量 + 关闭按钮
- **不显示温度和思考强度**，参数在主页设置

### 新增配置流程

1. 点击左栏"添加配置"→ 右栏切换为新增表单，左栏新增项高亮
2. 填写基础信息（提供商自动填充 API 地址）
3. 点击"获取模型"→ 弹窗选取模型（默认 temperature=0.7, reasoning_effort=none）
4. 在右栏为每个模型调整参数
5. 点击"添加配置"保存 → 左栏列表更新

### 编辑配置流程

1. 点击左栏某个配置 → 右栏显示该配置详情
2. 直接修改字段/参数（inline 编辑，无需单独编辑按钮）
3. 修改后自动保存（或显示"保存"按钮，待定）

## 后端 API 变更

### 无新增端点

现有端点足够，仅需调整 Schema 验证：

- `POST /api/model_configs/` — 创建时 ModelItem 可携带 temperature 和 reasoning_effort
- `PUT /api/model_configs/{id}` — 更新时同上
- `GET /api/model_configs/` — 响应中返回新字段

### build_config_response 调整

1. 旧数据兼容：models JSON 中缺少 temperature/reasoning_effort 时填充默认值
2. single 类型旧数据：当 `model_name` 有值但 `models` 为空时，自动生成单元素 models 列表
3. `provider_type` 仍保留在响应中用于兼容，但前端不再用它做分支判断

### 启用/停用切换

复用 `PUT /api/model_configs/{id}` 端点，传入 `is_enabled` 即可。无需新增端点。

## useSettings Hook 重构

当前 `useSettings.ts` 的模型配置部分为弹窗模式设计（`showConfigDialog`/`editingConfig`/`handleCloseConfigDialog`）。重构为双栏模式后：

**移除**：
- `showConfigDialog` 状态
- `handleAddModel`/`handleEditModel`/`handleCloseConfigDialog` 方法

**保留**：
- `modelConfigs`/`configsLoading`/`loadModelConfigs`
- `handleSaveModel`（改为接收 ModelConfigCreate，支持新增和更新）
- `handleSetDefault`/`handleDeleteModel`/`handleCheckHealth`

**新增**：
- `selectedConfigId` 状态：当前选中的配置 ID
- `handleToggleEnabled` 方法：切换启用/停用
- `handleSelectConfig` 方法：选中某个配置

双栏组件自行管理右栏的编辑状态（基础字段、模型列表的增删改），仅在保存时调用 hook 的 `handleSaveModel`。

## 文件变更清单

### 后端

| 文件 | 变更 |
|------|------|
| `backend/app/schemas/model_config.py` | ModelItem 增加 temperature、reasoning_effort 字段 |
| `backend/app/services/llm.py` | LLMService 构造函数增加 temperature、reasoning_effort；chat/chat_stream 默认使用实例属性 |
| `backend/app/api/model_configs.py` | build_config_response 为旧数据填充默认值，single 类型自动生成 models 列表 |
| `backend/app/utils/llm.py` | get_llm_service_from_config 从 ModelItem 读取 temperature/reasoning_effort 传给 LLMService |

### 前端

| 文件 | 变更 |
|------|------|
| `frontend/src/types/index.ts` | ModelItem 增加 temperature、reasoning_effort；ModelConfigCreate/Update 适配 |
| `frontend/src/components/settings/ModelConfigPanel.tsx` | 重构为双栏布局（左栏列表 + 右栏详情） |
| `frontend/src/components/settings/ModelConfigDialog.tsx` | 移除（功能合并到双栏右栏） |
| `frontend/src/components/settings/ModelConfigCard.tsx` | 移除（功能合并到左栏列表项） |
| `frontend/src/components/settings/ModelConfigItem.tsx` | 移除（功能合并到左栏列表项） |
| `frontend/src/components/settings/AddModelDialog.tsx` | 移除（获取模型弹窗重写） |
| 新增 `ModelConfigSidebar.tsx` | 左栏：配置列表 + 启用开关 |
| 新增 `ModelConfigDetail.tsx` | 右栏：配置详情/新增表单 |
| 新增 `ModelCard.tsx` | 单个模型卡片（温度 Slider + 思考强度选择） |
| 新增 `FetchModelsDialog.tsx` | 获取模型弹窗 |
| `frontend/src/components/settings/hooks/useSettings.ts` | 移除弹窗相关状态，新增 selectedConfigId/handleToggleEnabled |
| `frontend/src/pages/Settings.tsx` | 模型配置 Tab 使用新的 ModelConfigPanel（内含双栏） |

## 风险与兼容性

1. **旧数据兼容**：models JSON 缺少新字段时，后端填充默认值，前端也做防御性读取
2. **single 类型旧数据**：`model_name` 有值但 `models` 为空时，build_config_response 自动生成单元素 models 列表
3. **API 参数兼容**：不支持 reasoning_effort 的 API 收到该参数时通常静默忽略，不会报错。但若某个 API 严格校验参数导致报错，用户可将 reasoning_effort 设为"关闭"（none）避免传参
4. **无数据库迁移**：JSON 列天然支持字段扩展
5. **节点默认值**：现有节点不传 temperature/reasoning_effort 时使用 LLMService 默认值（temperature=0.7, reasoning_effort=None），行为与现有完全一致
6. **provider_type 兼容**：字段保留但前端不再用它做分支判断，后端响应中仍返回以兼容旧版本前端
7. **temperature 参数覆盖**：chat/chat_stream 的 temperature 参数默认改为 None（而非 0.7），使用 `self.temperature` 作为实际默认值。这样节点调用不传参数时使用配置值，显式传参时可覆盖
