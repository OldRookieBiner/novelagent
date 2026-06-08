# 删除智能体 Prompt 管理功能

**日期**: 2026-06-08  
**状态**: 已批准

## 背景

系统设置中的「智能体 Prompt 管理」功能（设置页 → 智能体 → Prompt 管理）允许用户编辑 7 个旧版 agent prompt 并存入 `system_config` 表。但该功能已完全失效：

- 管理的 7 个 agent_type（`outline_generation`、`chapter_outline_generation` 等）全部是旧版节点，当前工作流图不包含它们
- `prompt_loader.get_system_prompt()` 无人调用，用户编辑保存的 prompt 从未被读取
- 当前工作流 25 个 prompt key 与 API 管理的 7 个 key 零重叠
- 数据链在"消费方"端完全断裂：前端写入 → DB → prompt_loader → **无人来读**

保留此功能会误导用户以为修改有效。

## 方案

干净删除整个 Prompt 管理功能。

### 删除的文件（5 个）

| 文件 | 说明 |
|------|------|
| `backend/app/api/system_prompts.py` | API 路由 |
| `backend/app/services/prompt_loader.py` | Prompt 加载器（无人调用） |
| `backend/app/models/system_config.py` | SystemConfig ORM 模型 |
| `backend/app/schemas/system_prompt.py` | Prompt 管理 Pydantic schemas（AGENT_TYPES、SystemPromptResponse 等） |
| `frontend/src/components/settings/AgentPromptPanel.tsx` | 前端面板组件 |

### 修改的文件

#### 后端（4 个）

1. **`backend/app/main.py`**
   - 移除 `system_prompts_router` 的 import 和路由注册（`prefix="/api/system/prompts"`）

2. **`backend/app/models/__init__.py`**
   - 移除 `SystemConfig` 的 import 和 `__all__` 导出

3. **`backend/app/schemas/__init__.py`**
   - 移除 `from app.schemas.system_prompt import ...` 的整个 import 块（6 个符号）
   - 移除 `__all__` 列表中的 `AGENT_TYPES`、`AgentTypeKey`、`AgentTypeMeta`、`SystemPromptResponse`、`SystemPromptListResponse`、`SystemPromptUpdate`

4. **`backend/app/agents/prompts.py`**
   - 保留 `DEFAULT_PROMPTS` 字典，但移除仅被已删文件引用的兼容别名 `AGENT_INSPIRATION_SYSTEM_PROMPT`
   - `DEFAULT_PROMPTS` 本身被 `review_utils.py`、`rewrite_utils.py`、`agent_tools.py` 直接引用，必须保留

#### 后端 — 死代码清理（1 个）

5. **`backend/app/agents/agent_tools.py`**
   - 移除 `agent_context` 函数中尝试从 DB 加载 `SystemPrompt` 模型的 try/except 块（第 1368-1377 行）
   - 该块引用了不存在的 `app.models.system_prompt.SystemPrompt`，永远走 except 回退到 `DEFAULT_PROMPTS`
   - 改为直接 `from app.agents.prompts import DEFAULT_PROMPTS`，简化逻辑

#### 前端（4 个）

6. **`frontend/src/pages/Settings.tsx`**
   - 移除 `SETTINGS_NAV` 中的「智能体」分组（`agents` 导航项）
   - 移除 `SettingsTab` 联合类型中的 `'agents'`
   - 移除 `AgentPromptPanel` import
   - 移除 `useSettings()` 解构中的 prompt 相关字段
   - 移除 `agents` tab 的 `useEffect` 加载逻辑
   - 移除 `activeTab === 'agents'` 的渲染分支

7. **`frontend/src/components/settings/hooks/useSettings.ts`**
   - 移除 `systemPromptsApi` import
   - 移除 `AGENT_TABS` 常量和 `AgentTab` 类型导出
   - 移除 prompt 相关状态：`prompts`、`promptsLoading`、`selectedAgent`、`editContent`、`savingPrompt`、`resettingPrompt`
   - 移除 prompt 相关方法：`loadPrompts`、`handleSavePrompt`、`handleResetPrompt`
   - 移除 `currentPrompt` 计算和 `selectedAgent` 的 `useEffect`
   - 从 return 对象中移除所有 prompt 相关字段

8. **`frontend/src/lib/api.ts`**
   - 移除 `systemPromptsApi` 对象及其 `list`、`update`、`reset` 方法

9. **`frontend/src/types/index.ts`**
   - 移除 `SystemPrompt`、`SystemPromptListResponse`、`SystemPromptUpdate` 接口

### 测试文件更新（4 个）

10. **`frontend/src/components/settings/hooks/__tests__/useSettings.test.ts`**
    - 移除 `systemPromptsApi` mock

11. **`frontend/src/pages/__tests__/Settings.test.tsx`**
    - 移除 `systemPromptsApi` mock
    - 移除 `Prompt 管理` 断言
    - 移除 mockUseSettings 返回值中的 prompt 相关字段

12. **`frontend/src/pages/__tests__/Login.test.tsx`**
    - 移除 `systemPromptsApi` mock

13. **`frontend/src/pages/__tests__/Home.test.tsx`**
    - 移除 `systemPromptsApi` mock

### 数据库迁移

新建 Alembic migration：删除 `system_config` 表。

保留历史迁移文件（`20260426_system_prompts.py`、`20260502_outline_prompt_v2.py`）不变，它们是历史记录。

## 不做的事

- **不删除 `DEFAULT_PROMPTS` 字典**：被 `review_utils.py`、`rewrite_utils.py`、`agent_tools.py` 直接引用，删除会破坏旧版兼容节点
- **不清理 `review_utils.py` 等文件中的 `DEFAULT_PROMPTS` 引用**：超出本方案范围，后续统一清理
- **不删除旧版迁移文件**：保留迁移历史完整性

## 影响范围

- 用户侧：设置页不再显示「Prompt 管理」入口
- 数据侧：`system_config` 表被删除，其中存储的 prompt 数据丢失（这些数据本来就没被使用，无实际影响）
- 旧版兼容节点：不受影响，它们直接引用 `DEFAULT_PROMPTS` 常量
- 当前工作流：不受影响，从不依赖此功能
- `agent_tools.py`：`agent_context` 函数中加载自定义 prompt 的死代码被移除，直接使用 `DEFAULT_PROMPTS`，行为与现有运行时一致（因为 `SystemPrompt` model 不存在，本来就走 except 回退）
