# 删除智能体 Prompt 管理功能 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除已失效的 Prompt 管理功能（前端面板 + 后端 API + ORM 模型 + 数据库表），消除对用户的误导。

**Architecture:** 前端设置页移除「智能体 → Prompt 管理」入口及所有相关状态/组件；后端移除 API 路由、prompt_loader 服务、SystemConfig 模型；新建 Alembic 迁移删除 system_config 表。`DEFAULT_PROMPTS` 字典保留（被 review_utils.py 等文件引用）。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、React、TypeScript、Zustand

---

## 文件结构

### 删除
| 文件 | 职责 |
|------|------|
| `backend/app/api/system_prompts.py` | Prompt 管理 API 路由 |
| `backend/app/services/prompt_loader.py` | Prompt 加载/缓存服务（无人调用） |
| `backend/app/models/system_config.py` | SystemConfig ORM 模型 |
| `frontend/src/components/settings/AgentPromptPanel.tsx` | Prompt 编辑面板组件 |

### 修改
| 文件 | 职责 |
|------|------|
| `backend/app/main.py` | 移除路由注册 |
| `backend/app/models/__init__.py` | 移除模型导出 |
| `backend/app/agents/prompts.py` | 移除兼容别名 |
| `frontend/src/pages/Settings.tsx` | 移除 agents tab |
| `frontend/src/components/settings/hooks/useSettings.ts` | 移除 prompt 状态/方法 |
| `frontend/src/lib/api.ts` | 移除 systemPromptsApi |
| `frontend/src/types/index.ts` | 移除 SystemPrompt 类型 |
| `frontend/src/components/settings/hooks/__tests__/useSettings.test.ts` | 移除 mock |
| `frontend/src/pages/__tests__/Settings.test.tsx` | 移除 mock 和断言 |
| `frontend/src/pages/__tests__/Login.test.tsx` | 移除 mock |
| `frontend/src/pages/__tests__/Home.test.tsx` | 移除 mock |

### 新建
| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/20260608_drop_system_config.py` | 删除 system_config 表 |

---

### Task 1: 删除后端 Prompt 管理文件

**Files:**
- Delete: `backend/app/api/system_prompts.py`
- Delete: `backend/app/services/prompt_loader.py`
- Delete: `backend/app/models/system_config.py`
- Modify: `backend/app/main.py:23,139-143`
- Modify: `backend/app/models/__init__.py:10,34`

- [ ] **Step 1: 删除三个后端文件**

```bash
rm backend/app/api/system_prompts.py
rm backend/app/services/prompt_loader.py
rm backend/app/models/system_config.py
```

- [ ] **Step 2: 修改 main.py — 移除 import 和路由注册**

移除第 23 行的 import：
```python
# 删除此行
from app.api.system_prompts import router as system_prompts_router
```

移除第 139-143 行的路由注册：
```python
# 删除此块
app.include_router(
    system_prompts_router, prefix="/api/system/prompts", tags=["system-prompts"]
)
```

- [ ] **Step 3: 修改 models/__init__.py — 移除 SystemConfig 导出**

移除 import 行：
```python
# 删除此行
from app.models.system_config import SystemConfig
```

移除 `__all__` 列表中的：
```python
# 删除此行
    "SystemConfig",
```

- [ ] **Step 4: 验证后端可以正常导入**

```bash
cd backend && python -c "from app.models import *; from app.main import app; print('OK')"
```
Expected: `OK`，无 ImportError

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(api): remove dead prompt management API and SystemConfig model"
```

---

### Task 2: 清理 prompts.py 兼容别名

**Files:**
- Modify: `backend/app/agents/prompts.py:999`

- [ ] **Step 1: 移除 AGENT_INSPIRATION_SYSTEM_PROMPT 别名**

删除第 999 行：
```python
# 删除此行
AGENT_INSPIRATION_SYSTEM_PROMPT = INSPIRATION_DIALOGUE_PROMPT
```

- [ ] **Step 2: 验证无其他文件引用此别名**

```bash
rg "AGENT_INSPIRATION_SYSTEM_PROMPT" backend/
```
Expected: 无结果

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/prompts.py
git commit -m "refactor(workflow): remove AGENT_INSPIRATION_SYSTEM_PROMPT compat alias"
```

---

### Task 3: 新建数据库迁移 — 删除 system_config 表

**Files:**
- Create: `backend/alembic/versions/20260608_drop_system_config.py`

- [ ] **Step 1: 确认当前最新迁移的 revision ID**

```bash
cd backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); s=ScriptDirectory.from_config(c); print(s.get_current_head())"
```
记录输出作为 `down_revision`。

- [ ] **Step 2: 创建迁移文件**

创建 `backend/alembic/versions/20260608_drop_system_config.py`：

```python
"""Drop system_config table

Revision ID: 20260608_drop_system_config
Revises: <上一步输出的 head revision>
Create Date: 2026-06-08

"""

from alembic import op

# revision identifiers
revision = "20260608_drop_system_config"
down_revision = "<上一步输出的 head revision>"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("system_config")


def downgrade():
    # 重建 system_config 表（仅结构，不含初始数据）
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
```

注意：downgrade 中需要 `import sqlalchemy as sa`。如果 Alembic 环境自动渲染，按模板调整。

- [ ] **Step 3: 验证迁移可正常生成**

```bash
cd backend && python -m alembic upgrade head --sql 2>&1 | head -20
```
Expected: 无报错，生成的 SQL 包含 `DROP TABLE system_config`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260608_drop_system_config.py
git commit -m "db(migration): drop system_config table"
```

---

### Task 4: 前端 — 移除类型和 API

**Files:**
- Modify: `frontend/src/types/index.ts:343-360`
- Modify: `frontend/src/lib/api.ts:26-28,438-462`

- [ ] **Step 1: 修改 types/index.ts — 移除 SystemPrompt 类型**

删除第 343-360 行的三个接口和分隔注释：
```typescript
// 删除以下全部内容：
// ==================== System Prompt Types ====================

export interface SystemPrompt {
  agent_type: string;
  agent_name: string;
  description: string;
  prompt_content: string;
  variables: string[];
  variable_descriptions: Record<string, string>;
  updated_at?: string;
}

export interface SystemPromptListResponse {
  prompts: SystemPrompt[];
}

export interface SystemPromptUpdate {
  prompt_content: string;
}
```

- [ ] **Step 2: 修改 api.ts — 移除 import 和 systemPromptsApi**

移除第 26-28 行的 import：
```typescript
// 删除此三行
  SystemPrompt,
  SystemPromptListResponse,
  SystemPromptUpdate,
```

移除第 438-462 行的整个 systemPromptsApi 块（含分隔注释）：
```typescript
// 删除以下全部内容：
// ==================== System Prompts API ====================

export const systemPromptsApi = {
  async list(): Promise<SystemPromptListResponse> {
    return request<SystemPromptListResponse>("/api/system/prompts/");
  },

  async update(
    agentType: string,
    data: SystemPromptUpdate
  ): Promise<SystemPrompt> {
    return request<SystemPrompt>(`/api/system/prompts/${agentType}/`, {
      method: "PUT",
      body: data,
    });
  },

  async reset(agentType: string): Promise<SystemPrompt> {
    return request<SystemPrompt>(`/api/system/prompts/${agentType}/reset/`, {
      method: "POST",
    });
  },
};
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 无类型错误（如果 useSettings.ts 还在引用，会有错误，等 Task 5 修复）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "refactor(frontend): remove SystemPrompt types and systemPromptsApi"
```

---

### Task 5: 前端 — 移除 useSettings hook 中的 prompt 状态

**Files:**
- Modify: `frontend/src/components/settings/hooks/useSettings.ts`

- [ ] **Step 1: 移除 systemPromptsApi import**

将第 2 行：
```typescript
import { settingsApi, systemPromptsApi, modelConfigsApi } from '@/lib/api'
```
改为：
```typescript
import { settingsApi, modelConfigsApi } from '@/lib/api'
```

- [ ] **Step 2: 移除 SystemPrompt 类型 import**

将第 3 行：
```typescript
import type { SettingsUpdate, SystemPrompt, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types'
```
改为：
```typescript
import type { SettingsUpdate, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types'
```

- [ ] **Step 3: 移除 AGENT_TABS 常量和 AgentTab 类型导出**

删除第 7-16 行的全部内容：
```typescript
// 删除以下全部
const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
  { id: 'character_generation', label: '人物生成' },
  { id: 'relation_generation', label: '关系生成' },
  { id: 'review', label: '审核' },
  { id: 'rewrite', label: '重写' },
] as const

type AgentTab = typeof AGENT_TABS[number]['id']

export type { AgentTab, AGENT_TABS as AGENT_TABS_CONST }
export { AGENT_TABS }
```

- [ ] **Step 4: 移除 prompt 相关状态声明**

删除以下状态声明：
```typescript
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [promptsLoading, setPromptsLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentTab>('outline_generation')
  const [editContent, setEditContent] = useState('')
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [resettingPrompt, setResettingPrompt] = useState(false)
```

- [ ] **Step 5: 移除 loadPrompts 方法**

删除整个 `loadPrompts` useCallback：
```typescript
  const loadPrompts = useCallback(async () =>
  {
    setPromptsLoading(true)
    try
    {
      const data = await systemPromptsApi.list()
      setPrompts(data.prompts)
    }
    catch (err)
    {
      console.error('Failed to load system prompts:', err)
      toast.error('加载提示词失败')
    }
    finally
    {
      setPromptsLoading(false)
    }
  }, [])
```

- [ ] **Step 6: 移除 prompts 的 useEffect**

删除整个 useEffect：
```typescript
  useEffect(() =>
  {
    const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)
    if (currentPrompt)
    {
      setEditContent(currentPrompt.prompt_content)
    }
  }, [prompts, selectedAgent])
```

- [ ] **Step 7: 移除 currentPrompt 计算**

删除：
```typescript
  const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)
```

- [ ] **Step 8: 移除 handleSavePrompt 方法**

删除整个 `handleSavePrompt` useCallback。

- [ ] **Step 9: 移除 handleResetPrompt 方法**

删除整个 `handleResetPrompt` useCallback。

- [ ] **Step 10: 从 return 对象中移除 prompt 相关字段**

从 return 对象中删除：
```typescript
    // 系统提示词
    prompts,
    promptsLoading,
    loadPrompts,
    selectedAgent,
    setSelectedAgent,
    editContent,
    setEditContent,
    currentPrompt,
    savingPrompt,
    resettingPrompt,
    handleSavePrompt,
    handleResetPrompt,
```

- [ ] **Step 11: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 可能有 Settings.tsx 的错误（等 Task 6 修复）

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/settings/hooks/useSettings.ts
git commit -m "refactor(frontend): remove prompt management state from useSettings hook"
```

---

### Task 6: 前端 — 移除 Settings 页面的 agents tab

**Files:**
- Delete: `frontend/src/components/settings/AgentPromptPanel.tsx`
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 删除 AgentPromptPanel 组件**

```bash
rm frontend/src/components/settings/AgentPromptPanel.tsx
```

- [ ] **Step 2: 修改 Settings.tsx — 移除 agents 导航组**

将 `SETTINGS_NAV` 从：
```typescript
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
```
改为：
```typescript
const SETTINGS_NAV = [
  {
    group: '配置',
    items: [
      { id: 'model' as const, label: '模型配置', icon: Monitor },
      { id: 'review' as const, label: '审核设置', icon: Shield },
    ],
  },
]
```

- [ ] **Step 3: 移除 SettingsTab 类型中的 'agents'**

从：
```typescript
type SettingsTab = 'model' | 'review' | 'agents'
```
改为：
```typescript
type SettingsTab = 'model' | 'review'
```

- [ ] **Step 4: 移除 Bot 图标 import**

从 import 行中移除 `Bot`：
```typescript
import { Monitor, Shield, Bot, ArrowLeft } from 'lucide-react'
```
改为：
```typescript
import { Monitor, Shield, ArrowLeft } from 'lucide-react'
```

- [ ] **Step 5: 移除 AgentPromptPanel import**

删除：
```typescript
import AgentPromptPanel from '@/components/settings/AgentPromptPanel'
```

- [ ] **Step 6: 从 useSettings 解构中移除 prompt 相关字段**

从解构中移除：
```typescript
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
```

- [ ] **Step 7: 移除 agents tab 的 useEffect**

删除整个 useEffect：
```typescript
  useEffect(() =>
  {
    if (activeTab === 'agents')
    {
      loadPrompts()
    }
  }, [activeTab, loadPrompts])
```

- [ ] **Step 8: 移除 agents tab 的渲染分支**

删除：
```typescript
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
```

- [ ] **Step 9: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 无错误

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(frontend): remove Prompt management tab from Settings page"
```

---

### Task 7: 前端 — 更新测试文件

**Files:**
- Modify: `frontend/src/components/settings/hooks/__tests__/useSettings.test.ts`
- Modify: `frontend/src/pages/__tests__/Settings.test.tsx`
- Modify: `frontend/src/pages/__tests__/Login.test.tsx`
- Modify: `frontend/src/pages/__tests__/Home.test.tsx`

- [ ] **Step 1: 更新 useSettings.test.ts — 移除 systemPromptsApi mock**

从 `vi.mock('@/lib/api', ...)` 中删除：
```typescript
  systemPromptsApi: {
    list: vi.fn().mockResolvedValue({ prompts: [] }),
  },
```

- [ ] **Step 2: 更新 Settings.test.tsx — 移除 systemPromptsApi mock 和 prompt 断言**

从 `vi.mock('@/lib/api', ...)` 中删除：
```typescript
  systemPromptsApi: { list: vi.fn() },
```

从 `mockUseSettings` 返回值中删除所有 prompt 相关字段：
```typescript
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
```

删除断言：
```typescript
  expect(screen.getByText('Prompt 管理')).toBeInTheDocument()
```

- [ ] **Step 3: 更新 Login.test.tsx — 移除 systemPromptsApi mock**

删除：
```typescript
  systemPromptsApi: {},
```

- [ ] **Step 4: 更新 Home.test.tsx — 移除 systemPromptsApi mock**

删除：
```typescript
  systemPromptsApi: {},
```

- [ ] **Step 5: 运行前端测试**

```bash
cd frontend && npm run test:run
```
Expected: 所有测试通过

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "test(frontend): remove systemPromptsApi mocks from test files"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 前端 TypeScript 编译检查**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 无错误

- [ ] **Step 2: 前端测试**

```bash
cd frontend && npm run test:run
```
Expected: 全部通过

- [ ] **Step 3: 后端导入检查**

```bash
cd backend && python -c "from app.main import app; from app.models import *; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: 全局搜索确认无残留引用**

```bash
rg "systemPromptsApi|SystemPrompt|system_prompts|prompt_loader|SystemConfig" frontend/src/ backend/app/ --type py --type ts --type tsx
```
Expected: 无结果（`DEFAULT_PROMPTS` 在 prompts.py 中的定义除外）

- [ ] **Step 5: 最终 Commit（如有遗漏修复）**

```bash
git add -A
git commit -m "chore: cleanup prompt management removal"
```
