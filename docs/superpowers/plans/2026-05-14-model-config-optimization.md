# 模型配置页面优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为模型配置页面添加温度和思考强度支持，重构为双栏布局

**Architecture:** 后端在 ModelItem JSON 中新增 temperature/reasoning_effort 字段，LLMService 构造函数透传这些参数，get_llm_service_from_config 从 models 列表读取。前端将弹窗模式重构为双栏页面（左列表 + 右详情），新增 FetchModelsDialog 弹窗和 ModelCard 组件。

**Tech Stack:** FastAPI + Pydantic (后端), React + shadcn/ui + Zustand (前端)

---

## Task 1: 后端 Schema — ModelItem 增加 temperature 和 reasoning_effort

**Files:**
- Modify: `backend/app/schemas/model_config.py`

- [ ] **Step 1: 修改 ModelItem schema**

在 `backend/app/schemas/model_config.py` 中为 `ModelItem` 新增两个字段：

```python
from typing import Literal

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]

class ModelItem(BaseModel):
    """Coding Plan 中的单个模型"""
    id: str
    name: str
    is_enabled: bool = True
    health_status: Optional[str] = None
    temperature: float = 0.7              # 新增：模型温度，范围 0-2
    reasoning_effort: Optional[ReasoningEffort] = None  # 新增：思考强度 none/low/medium/high/xhigh
```

- [ ] **Step 2: 验证 Schema 加载无报错**

Run: `cd /opt/project/novelagent && docker exec novelagent-backend-1 python -c "from app.schemas.model_config import ModelItem; m = ModelItem(id='test', name='test'); print(m.model_dump())"`
Expected: 输出包含 `temperature=0.7` 和 `reasoning_effort=None`

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/model_config.py
git commit -m "feat(schema): add temperature and reasoning_effort to ModelItem"
```

---

## Task 2: 后端 LLMService — 支持 temperature 和 reasoning_effort 透传

**Files:**
- Modify: `backend/app/services/llm.py`
- Create: `backend/tests/test_llm_service_params.py`

- [ ] **Step 1: 编写 LLMService 参数透传测试**

创建 `backend/tests/test_llm_service_params.py`：

```python
"""测试 LLMService temperature 和 reasoning_effort 参数透传"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_chat_uses_instance_temperature_by_default():
    """chat() 不传 temperature 时使用实例的 self.temperature"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.3
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_chat_uses_instance_reasoning_effort():
    """chat() 不传 reasoning_effort 时使用实例的 self.reasoning_effort"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = "high"
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_chat_skips_reasoning_effort_when_none():
    """chat() 在 reasoning_effort 为 None 时不传该参数"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs


@pytest.mark.asyncio
async def test_chat_skips_reasoning_effort_when_none_string():
    """chat() 在 reasoning_effort 为 'none' 时不传该参数"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = "none"
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs


@pytest.mark.asyncio
async def test_chat_allows_temperature_override():
    """chat() 显式传 temperature 时覆盖实例值"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.3
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}], temperature=0.9)

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.9


@pytest.mark.asyncio
async def test_chat_stream_uses_instance_params():
    """chat_stream() 同样使用实例 temperature 和 reasoning_effort"""
    from app.services.llm import LLMService

    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content="hi"), finish_reason=None)]
    final = MagicMock()
    final.choices = [MagicMock(delta=MagicMock(content=""), finish_reason="stop")]

    async def mock_stream(*args, **kwargs):
        for c in [chunk, final]:
            yield c

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.5
        service.reasoning_effort = "medium"
        service.client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = []
        async for c in service.chat_stream([{"role": "user", "content": "test"}]):
            result.append(c)

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["reasoning_effort"] == "medium"
        assert "stream" in call_kwargs and call_kwargs["stream"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_llm_service_params.py -v`
Expected: FAIL — `LLMService` 没有 `temperature`/`reasoning_effort` 属性

- [ ] **Step 3: 修改 LLMService 构造函数和方法**

在 `backend/app/services/llm.py` 中：

1. `__init__` 增加 `temperature=0.7` 和 `reasoning_effort=None` 参数，存储为实例属性
2. `chat()` 的 `temperature` 参数默认改为 `None`，使用 `self.temperature` 回退；新增 `reasoning_effort` 参数默认 `None`，使用 `self.reasoning_effort` 回退；当值为 `None` 或 `"none"` 时不传给 API

chat() 实现关键代码：
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

3. `chat_stream()` 同理，kwargs 构建方式一致：

chat_stream() 实现关键代码：
```python
async def chat_stream(
    self, messages: list[dict], temperature: float = None,
    max_tokens: int = 4096, reasoning_effort: str = None
) -> AsyncIterator[str]:
    temp = temperature if temperature is not None else self.temperature
    effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort

    kwargs = {
        "model": self.model,
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if effort and effort != "none":
        kwargs["reasoning_effort"] = effort
    stream = await self.client.chat.completions.create(**kwargs)
```

4. `chat_with_system()` 保持不变（它调用 `self.chat`）

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_llm_service_params.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: 运行现有 LLM 测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_llm_choices_guard.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/llm.py backend/tests/test_llm_service_params.py
git commit -m "feat(llm): support temperature and reasoning_effort in LLMService"
```

---

## Task 3: 后端 get_llm_service_from_config — 从 ModelItem 读取参数

**Files:**
- Modify: `backend/app/services/llm.py` (get_llm_service_from_config 函数)
- Create: `backend/tests/test_llm_from_config_params.py`

- [ ] **Step 1: 编写 get_llm_service_from_config 参数读取测试**

创建 `backend/tests/test_llm_from_config_params.py`：

```python
"""测试 get_llm_service_from_config 从 ModelItem 读取 temperature/reasoning_effort"""
import pytest
from unittest.mock import MagicMock, patch


def _make_config(models=None, model_name=None, provider="custom",
                 base_url="https://api.test.com/v1", api_key_encrypted=None):
    """创建模拟的 ModelConfig 对象"""
    config = MagicMock()
    config.provider = provider
    config.base_url = base_url
    config.model_name = model_name
    config.models = models
    config.api_key_encrypted = api_key_encrypted
    return config


@patch("app.services.llm.decrypt_api_key", return_value="test-key")
def test_reads_temperature_from_model_item(mock_decrypt):
    """从 models 列表中读取 temperature"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.3, "reasoning_effort": None}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.temperature == 0.3


@patch("app.services.llm.decrypt_api_key", return_value="test-key")
def test_reads_reasoning_effort_from_model_item(mock_decrypt):
    """从 models 列表中读取 reasoning_effort"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.7, "reasoning_effort": "high"}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.reasoning_effort == "high"


@patch("app.services.llm.decrypt_api_key", return_value="test-key")
def test_uses_default_when_model_item_missing_fields(mock_decrypt):
    """ModelItem 缺少 temperature/reasoning_effort 时使用默认值"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.temperature == 0.7
    assert service.reasoning_effort is None


@patch("app.services.llm.decrypt_api_key", return_value="test-key")
def test_matches_model_by_override(mock_decrypt):
    """model_override 匹配特定 ModelItem 读取参数"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[
            {"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.7, "reasoning_effort": None},
            {"id": "m2", "name": "model-2", "is_enabled": True, "temperature": 0.3, "reasoning_effort": "high"},
        ],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1, model_override="m2")
    assert service.temperature == 0.3
    assert service.reasoning_effort == "high"
    assert service.model == "m2"


@patch("app.services.llm.decrypt_api_key", return_value="test-key")
def test_fallback_to_model_name_when_no_models(mock_decrypt):
    """无 models 列表时回退到 model_name，使用默认 temperature"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        model_name="fallback-model",
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.model == "fallback-model"
    assert service.temperature == 0.7
    assert service.reasoning_effort is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_llm_from_config_params.py -v`
Expected: FAIL — `get_llm_service_from_config` 不传递 temperature/reasoning_effort

- [ ] **Step 3: 修改 get_llm_service_from_config**

在 `backend/app/services/llm.py` 中修改 `get_llm_service_from_config`：

1. 在确定 model 名称后，从 `model_config.models` 中查找匹配的 ModelItem（同时匹配 `id` 和 `name`，因为 model_override 来自前端的 `model.name`）
2. 读取其 `temperature`（默认 0.7）和 `reasoning_effort`（默认 None）
3. 传给 `LLMService` 构造函数

关键代码：
```python
target_item = None
if model_config.models:
    for m in model_config.models:
        if m.get("is_enabled", True):
            if not model or m.get("id") == model or m.get("name") == model:
                model = m.get("id") or m.get("name")
                target_item = m
                break

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

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_llm_from_config_params.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/llm.py backend/tests/test_llm_from_config_params.py
git commit -m "feat(llm): read temperature/reasoning_effort from ModelItem in get_llm_service_from_config"
```

---

## Task 4: 后端 build_config_response — 旧数据兼容

**Files:**
- Modify: `backend/app/api/model_configs.py`

- [ ] **Step 1: 修改 build_config_response**

在 `backend/app/api/model_configs.py` 的 `build_config_response` 函数中：

1. 透传所有 ModelItem 字段（不再逐字段硬编码），缺失字段填充默认值
2. 当 `model_name` 有值但 `models` 为空时（旧 single 类型数据），自动生成单元素 models 列表

关键代码：
```python
# 处理 models 列表：透传所有字段 + 填充默认值
if c.models:
    models = []
    for m in c.models:
        item = {
            "id": m.get("id"),
            "name": m.get("name"),
            "is_enabled": m.get("is_enabled", True),
            "health_status": m.get("health_status"),
            "temperature": m.get("temperature", 0.7),
            "reasoning_effort": m.get("reasoning_effort"),
        }
        models.append(item)
elif c.model_name:
    # 旧 single 类型数据：从 model_name 生成单元素 models 列表
    models = [{
        "id": c.model_name,
        "name": c.model_name,
        "is_enabled": True,
        "health_status": None,
        "temperature": 0.7,
        "reasoning_effort": None,
    }]
else:
    models = None
```

- [ ] **Step 2: 验证旧数据兼容**

Run: `docker exec novelagent-backend-1 python -c "
from app.api.model_configs import build_config_response
from app.models.model_config import ModelConfig
# 模拟旧数据：只有 model_name，无 models
c = ModelConfig(id=1, user_id=1, name='test', provider='custom', base_url='https://api.test.com', model_name='gpt-4')
r = build_config_response(c)
print('models:', r.models)
assert r.models is not None
assert r.models[0].temperature == 0.7
assert r.models[0].reasoning_effort is None
print('OK: single fallback works')
"`
Expected: `OK: single fallback works`

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/model_configs.py
git commit -m "fix(api): compat old model configs - fill defaults and auto-generate models list"
```

---

## Task 5: 前端类型更新

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 更新 ModelItem 类型**

在 `frontend/src/types/index.ts` 的 `ModelItem` 接口中新增：

```typescript
export interface ModelItem {
  id: string
  name: string
  is_enabled: boolean
  health_status?: string
  temperature: number           // 新增
  reasoning_effort?: string | null  // 新增：none/low/medium/high/xhigh
}
```

- [ ] **Step 2: 更新 ModelConfigCreate 类型**

在 `ModelConfigCreate` 接口中，`models` 字段的 ModelItem 已包含新字段，无需额外修改。

- [ ] **Step 3: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无 ModelItem 相关类型错误（可能有其他无关错误）

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add temperature and reasoning_effort to ModelItem"
```

---

## Task 6: 前端 UI 基础组件 — Slider 和 Switch

**Files:**
- Create: `frontend/src/components/ui/slider.tsx`
- Create: `frontend/src/components/ui/switch.tsx`

- [ ] **Step 1: 安装 shadcn/ui Slider 依赖**

Run: `cd /opt/project/novelagent/frontend && npm install @radix-ui/react-slider`

- [ ] **Step 2: 创建 Slider 组件**

在 `frontend/src/components/ui/slider.tsx` 创建 shadcn/ui 标准 Slider 组件（参考 shadcn 官方模板，使用 Allman 大括号风格）。

- [ ] **Step 3: 安装 shadcn/ui Switch 依赖**

Run: `cd /opt/project/novelagent/frontend && npm install @radix-ui/react-switch`

- [ ] **Step 4: 创建 Switch 组件**

在 `frontend/src/components/ui/switch.tsx` 创建 shadcn/ui 标准 Switch 组件（参考 shadcn 官方模板，使用 Allman 大括号风格）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ui/slider.tsx frontend/src/components/ui/switch.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(ui): add shadcn Slider and Switch components"
```

---

## Task 7: 前端 ModelCard 组件

**Files:**
- Create: `frontend/src/components/settings/ModelCard.tsx`

- [ ] **Step 1: 创建 ModelCard 组件**

创建 `frontend/src/components/settings/ModelCard.tsx`，包含：

- Props: `model: ModelItem`, `onTemperatureChange: (val: number) => void`, `onReasoningEffortChange: (val: string) => void`, `onRemove: () => void`
- 模型名称 + 移除按钮
- 温度 Slider（0-2，步长 0.1，显示当前值）
- 思考强度 5 档选择按钮组（关闭/低/中/高/最强）
- 防御性读取：`model.temperature ?? 0.7`，`model.reasoning_effort ?? 'none'`

思考强度选项定义：
```typescript
const REASONING_EFFORT_OPTIONS = [
  { value: 'none', label: '关闭' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'xhigh', label: '最强' },
] as const
```

- [ ] **Step 2: 验证组件可导入**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | grep -i ModelCard || echo "No ModelCard errors"`
Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/ModelCard.tsx
git commit -m "feat(settings): add ModelCard component with temperature slider and reasoning effort selector"
```

---

## Task 8: 前端 FetchModelsDialog 组件

**Files:**
- Create: `frontend/src/components/settings/FetchModelsDialog.tsx`

- [ ] **Step 1: 创建 FetchModelsDialog 组件**

创建 `frontend/src/components/settings/FetchModelsDialog.tsx`，功能：

- Props: `open: boolean`, `onClose: () => void`, `existingModelIds: string[]`, `onAddModel: (model: {id: string, name: string}) => void`, `onRemoveModel: (modelId: string) => void`
- 搜索框过滤模型名称
- 调用 `modelConfigsApi.fetchModels()` 获取模型列表
- 已添加的模型：绿色背景 + "移除"按钮
- 未添加的模型："添加"按钮
- 底部：已选模型数量 + 关闭按钮
- 点击"添加"时，自动设置默认参数（temperature=0.7, reasoning_effort='none'）

- [ ] **Step 2: 验证组件可导入**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | grep -i FetchModelsDialog || echo "No errors"`
Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/FetchModelsDialog.tsx
git commit -m "feat(settings): add FetchModelsDialog for model selection popup"
```

---

## Task 9: 前端 ModelConfigSidebar 组件

**Files:**
- Create: `frontend/src/components/settings/ModelConfigSidebar.tsx`

- [ ] **Step 1: 创建 ModelConfigSidebar 组件**

创建 `frontend/src/components/settings/ModelConfigSidebar.tsx`，功能：

- Props: `configs: ModelConfig[]`, `selectedId: number | null`, `onSelect: (id: number) => void`, `onToggleEnabled: (id: number, enabled: boolean) => void`, `onAdd: () => void`
- 每个配置项：名称 + 模型数量 + 健康状态小标签 + Switch 启用开关
- 选中态：蓝色背景 + 左侧蓝色边框
- 停用态：opacity-60
- 底部"添加配置"虚线按钮

- [ ] **Step 2: 验证组件可导入**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | grep -i ModelConfigSidebar || echo "No errors"`
Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/ModelConfigSidebar.tsx
git commit -m "feat(settings): add ModelConfigSidebar with enable toggle"
```

---

## Task 10: 前端 ModelConfigDetail 组件

**Files:**
- Create: `frontend/src/components/settings/ModelConfigDetail.tsx`

- [ ] **Step 1: 创建 ModelConfigDetail 组件**

创建 `frontend/src/components/settings/ModelConfigDetail.tsx`，功能：

- Props: `config: ModelConfig | null` (null 为新增模式), `providers: ProviderInfo[]`, `onSave: (data: ModelConfigCreate) => Promise<void>`, `onDelete: () => void`, `onCheckHealth: () => void`, `saving: boolean`
- 编辑模式：显示现有配置的基础信息和模型列表
- 新增模式：空表单
- 基础信息双列网格：提供商/名称/API地址/API Key
- 提供商选择自动填充 API 地址
- "获取模型"按钮 → 打开 FetchModelsDialog
- 模型卡片列表（使用 ModelCard 组件）
- 顶部：健康检查 + 删除按钮（仅编辑模式）
- 底部：保存按钮
- 本地状态管理：providers, 基础字段, models 列表
- 保存时构建 ModelConfigCreate 提交，其中 `provider_type` 固定为 `"single"`（向后兼容，前端不再用它做分支判断）

- [ ] **Step 2: 验证组件可导入**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | grep -i ModelConfigDetail || echo "No errors"`
Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/ModelConfigDetail.tsx
git commit -m "feat(settings): add ModelConfigDetail for right panel config editing"
```

---

## Task 11: 前端 useSettings Hook 重构

**Files:**
- Modify: `frontend/src/components/settings/hooks/useSettings.ts`

- [ ] **Step 1: 重构 useSettings hook**

修改 `frontend/src/components/settings/hooks/useSettings.ts`：

1. 移除：`showConfigDialog`, `editingConfig`, `handleAddModel`, `handleEditModel`, `handleCloseConfigDialog`
2. 新增状态：`selectedConfigId: number | null`
3. 新增方法：`handleToggleEnabled(configId, enabled)` — 调用 `modelConfigsApi.update(configId, { is_enabled: enabled })`
4. 新增方法：`handleSelectConfig(configId)` — 设置 `selectedConfigId`
5. 保留：`modelConfigs`, `configsLoading`, `loadModelConfigs`, `handleSetDefault`, `handleDeleteModel`, `handleCheckHealth`
6. `handleSaveModel` 改为 `handleSaveModel(data: ModelConfigCreate, configId?: number)`：
   - 有 configId 时调 `modelConfigsApi.update(configId, data)` （编辑模式，configId 由 ModelConfigDetail 传入）
   - 无 configId 时调 `modelConfigsApi.create(data)` （新增模式）
   - 原来的 `editingConfig` 判断逻辑移除，改由参数显式传入

关键代码：
```typescript
const handleSaveModel = useCallback(async (data: ModelConfigCreate, configId?: number) =>
{
  setSavingConfig(true)
  try
  {
    if (configId)
    {
      await modelConfigsApi.update(configId, data)
    }
    else
    {
      await modelConfigsApi.create(data)
    }
    await loadModelConfigs()
  }
  finally
  {
    setSavingConfig(false)
  }
}, [loadModelConfigs])
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无 useSettings 相关错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/hooks/useSettings.ts
git commit -m "refactor(settings): refactor useSettings hook for dual-column layout"
```

---

## Task 12: 前端 ModelConfigPanel 重构为双栏布局

**Files:**
- Modify: `frontend/src/components/settings/ModelConfigPanel.tsx`
- Delete: `frontend/src/components/settings/ModelConfigDialog.tsx`
- Delete: `frontend/src/components/settings/ModelConfigCard.tsx`
- Delete: `frontend/src/components/settings/ModelConfigItem.tsx`
- Delete: `frontend/src/components/settings/AddModelDialog.tsx`

- [ ] **Step 1: 重写 ModelConfigPanel**

将 `ModelConfigPanel.tsx` 重写为双栏布局：

- 左栏使用 `ModelConfigSidebar`，传入 configs/selectedId/onSelect/onToggleEnabled/onAdd
- 右栏使用 `ModelConfigDetail`，传入选中配置或 null（新增模式）
- 从 props 接收 useSettings 暴露的状态和方法
- 删除对 ModelConfigDialog/ModelConfigCard/ModelConfigItem/AddModelDialog 的引用

- [ ] **Step 2: 删除旧组件文件**

删除以下文件：
- `frontend/src/components/settings/ModelConfigDialog.tsx`
- `frontend/src/components/settings/ModelConfigCard.tsx`
- `frontend/src/components/settings/ModelConfigItem.tsx`
- `frontend/src/components/settings/AddModelDialog.tsx`

- [ ] **Step 3: 更新 Settings.tsx**

修改 `frontend/src/pages/Settings.tsx`：
- 移除对旧组件的 import
- ModelConfigPanel 的 props 调整为新的接口

- [ ] **Step 4: 验证 TypeScript 编译和构建**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无编译错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/settings/ frontend/src/pages/Settings.tsx
git commit -m "refactor(settings): replace dialog-based model config with dual-column layout"
```

---

## Task 13: 前端 InspirationPanel — 移除 provider_type 分支

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: 修改 InspirationPanel 模型加载逻辑**

Spec 要求"前端不再用 `provider_type` 做分支判断"。当前代码（约 246-275 行）用 `config.provider_type === 'coding_plan'` 决定遍历方式，必须统一为遍历 `config.models`。

替换逻辑：
```typescript
// 旧逻辑（两分支）：
// if (config.provider_type === 'coding_plan') { ... iterate config.models ... }
// else if (config.model_name) { ... single model ... }

// 新逻辑（统一遍历 config.models，回退 model_name）：
if (config.models && config.models.length > 0)
{
  for (const model of config.models)
  {
    if (!model.is_enabled) continue
    options.push({
      modelConfigId: config.id,
      modelName: model.name,
      providerName: providerDisplayName,
      provider: config.provider,
      isDefault: config.is_default,
    })
  }
}
else if (config.model_name)
{
  // 旧数据回退：无 models 但有 model_name
  options.push({
    modelConfigId: config.id,
    modelName: config.model_name,
    providerName: providerDisplayName,
    provider: config.provider,
    isDefault: config.is_default,
  })
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | grep -i InspirationPanel || echo "No errors"`
Expected: 无类型错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "refactor(inspiration): unify model loading logic, remove provider_type branching"
```

---

## Task 14: 构建验证和端到端测试

**Files:**
- No new files

- [ ] **Step 1: 重新构建前端**

Run: `cd /opt/project/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功

- [ ] **Step 2: 重新构建后端**

Run: `docker compose build --no-cache backend && docker compose up -d backend`
Expected: 构建成功

- [ ] **Step 3: 运行后端测试全量**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: 所有测试 PASS

- [ ] **Step 4: 手动验证核心流程**

在浏览器 http://localhost:3001 验证：

1. 设置页 → 模型配置 Tab → 双栏布局正常显示
2. 点击"添加配置" → 右栏新增表单 → 填写基础信息 → 获取模型 → 选取模型
3. 选中模型后调整温度 Slider 和思考强度
4. 保存成功 → 左栏列表更新
5. 切换启用开关 → 停用的配置降低透明度
6. 灵感页模型下拉框仅显示启用的配置

- [ ] **Step 5: 提交最终版本**

```bash
git add -A
git commit -m "chore: model config optimization - build verification"
```

---

## 自审清单

**1. Spec 覆盖度检查：**

| Spec 要求 | 对应 Task |
|-----------|-----------|
| ModelItem 新增 temperature/reasoning_effort | Task 1, Task 5 |
| reasoning_effort 值校验（Literal 类型） | Task 1 |
| LLMService 支持参数透传（含 chat_stream 详细实现） | Task 2 |
| get_llm_service_from_config 从 ModelItem 读取（匹配 id+name） | Task 3 |
| 旧数据兼容（build_config_response 透传字段+回退） | Task 4 |
| 双栏布局 | Task 9, 10, 12 |
| 获取模型弹窗 | Task 8 |
| 模型卡片（温度+思考强度） | Task 7 |
| 启用开关 | Task 9 |
| useSettings 重构（handleSaveModel 显式 configId） | Task 11 |
| 新建配置 provider_type 默认 "single" | Task 10 |
| InspirationPanel 移除 provider_type 分支 | Task 13 |
| 灵感页模型加载统一遍历 config.models | Task 13 |

**2. Placeholder 扫描：** 无 TBD/TODO/placeholder

**3. 类型一致性：** 所有 Task 使用的类型名、方法签名与 Task 1/5 定义的一致

**4. 审查修正记录：**
- [修正1] Task 1: reasoning_effort 使用 Literal 类型约束
- [修正2] Task 2: 补充 chat_stream() 的 kwargs 构建代码
- [修正3] Task 3: 模型匹配同时匹配 id 和 name
- [修正4] Task 4: build_config_response 透传所有字段而非硬编码
- [修正5] Task 10: provider_type 固定为 "single"
- [修正6] Task 11: handleSaveModel 显式传入 configId 参数
- [修正7] Task 13: 从"仅验证"改为"移除 provider_type 分支"
