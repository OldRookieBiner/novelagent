# 清除审核设置死代码实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清除 `user_settings` 表中的死字段（`review_enabled` / `review_strictness`）及前端相关组件，保留 `chapters` 表的审核字段（仍有活跃使用）。

**Architecture:** 前端移除审核 tab 及相关组件/类型，后端仅删除 user_settings 两列的 Alembic migration，同步清理 schema/API/工具函数中的引用。

**Tech Stack:** React + TypeScript, FastAPI + SQLAlchemy + Alembic

---

## 文件结构

### 前端（删除 + 修改）

| 文件 | 操作 |
|------|------|
| `frontend/src/components/settings/ReviewConfigPanel.tsx` | 删除 |
| `frontend/src/components/settings/ReviewModeSelect.tsx` | 删除 |
| `frontend/src/pages/Settings.tsx` | 修改：移除审核 tab 内容，保留 tab 导航 |
| `frontend/src/components/settings/hooks/useSettings.ts` | 修改：移除审核状态和函数 |
| `frontend/src/types/index.ts` | 修改：移除 UserSettings/SettingsUpdate 中的审核字段，保留 ReviewResponse |
| `frontend/src/stores/settingsStore.ts` | 修改：移除审核字段 |
| `frontend/src/stores/settingsStore.test.ts` | 修改：移除审核字段引用 |
| `frontend/src/components/settings/hooks/__tests__/useSettings.test.ts` | 修改：移除审核字段 mock |
| `frontend/src/pages/__tests__/Settings.test.tsx` | 修改：移除审核断言 |

### 后端（仅 settings 相关）

| 文件 | 操作 |
|------|------|
| `backend/app/models/settings.py` | 修改：移除 review_enabled / review_strictness 列 |
| `backend/app/schemas/settings.py` | 修改：移除对应字段 |
| `backend/app/api/settings.py` | 修改：API 移除审核字段 |
| `backend/app/utils/auth.py` | 修改：移除注册默认值 |
| `backend/alembic/versions/` | 新增：只删除 user_settings 两列的 migration |

---

## 任务 1：前端清理 — 删除审核相关组件

**Files:**
- Delete: `frontend/src/components/settings/ReviewConfigPanel.tsx`
- Delete: `frontend/src/components/settings/ReviewModeSelect.tsx`

- [ ] **Step 1: 删除 ReviewConfigPanel.tsx**

```bash
rm /Users/biner/Dev/novelagent/frontend/src/components/settings/ReviewConfigPanel.tsx
```

- [ ] **Step 2: 删除 ReviewModeSelect.tsx**

```bash
rm /Users/biner/Dev/novelagent/frontend/src/components/settings/ReviewModeSelect.tsx
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor(frontend): remove review config components"
```

---

## 任务 2：前端清理 — Settings.tsx

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 读取当前 Settings.tsx**

```bash
cat /Users/biner/Dev/novelagent/frontend/src/pages/Settings.tsx
```

- [ ] **Step 2: 移除审核 tab 内容，保留 tab 导航结构**

需要做的修改：
1. 移除 `import { Shield }` 如果仅用于审核 tab
2. 移除 tab 列表中的 `{ id: 'review', label: '审核设置', icon: Shield }`
3. 移除 `activeTab === 'review'` 条件分支中的 `<ReviewConfigPanel>` 渲染
4. 保留 `SettingsTab` 类型定义（为将来扩展）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "refactor(frontend): remove review tab from Settings page"
```

---

## 任务 3：前端清理 — useSettings.ts

**Files:**
- Modify: `frontend/src/components/settings/hooks/useSettings.ts`

- [ ] **Step 1: 读取当前 useSettings.ts**

```bash
cat /Users/biner/Dev/novelagent/frontend/src/components/settings/hooks/useSettings.ts
```

- [ ] **Step 2: 移除审核相关状态和函数**

移除内容：
- `reviewMode` / `maxRewriteCount` 的 `useState`
- `setReviewMode` / `setMaxRewriteCount`
- `handleSaveReviewSettings` 函数
- `useEffect` 中读取 `review_enabled` 的逻辑
- 返回值中的审核相关字段

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/settings/hooks/useSettings.ts
git commit -m "refactor(frontend): remove review settings from useSettings hook"
```

---

## 任务 4：前端清理 — types/index.ts

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 读取当前 types/index.ts**

```bash
cat /Users/biner/Dev/novelagent/frontend/src/types/index.ts
```

- [ ] **Step 2: 修改类型定义**

**移除（settings 相关）：**
- `UserSettings` 接口中移除 `review_enabled` / `review_strictness`
- `SettingsUpdate` 接口中移除 `review_enabled` / `review_strictness`

**保留（chapters 相关，不是死代码）：**
- `ReviewResponse` 接口
- `mapReviewResult` 函数
- `ReviewIssue` 接口
- `Chapter` 中的 `review_passed` / `review_feedback` / `review_result`

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "refactor(frontend): remove review settings fields from types"
```

---

## 任务 5：前端清理 — settingsStore.ts

**Files:**
- Modify: `frontend/src/stores/settingsStore.ts`

- [ ] **Step 1: 读取 settingsStore.ts**

```bash
cat /Users/biner/Dev/novelagent/frontend/src/stores/settingsStore.ts
```

- [ ] **Step 2: 移除审核相关字段**

从 state 中移除 `review_enabled` / `review_strictness`

- [ ] **Step 3: 提交**

```bash
git add frontend/src/stores/settingsStore.ts
git commit -m "refactor(frontend): remove review fields from settingsStore"
```

---

## 任务 6：前端清理 — 测试文件

**Files:**
- Modify: `frontend/src/stores/settingsStore.test.ts`
- Modify: `frontend/src/components/settings/hooks/__tests__/useSettings.test.ts`
- Modify: `frontend/src/pages/__tests__/Settings.test.tsx`

- [ ] **Step 1: settingsStore.test.ts**

移除 mock ��据中的 `review_enabled` / `review_strictness`

- [ ] **Step 2: useSettings.test.ts**

移除 mock 返回值中的 `review_enabled` / `review_strictness`

- [ ] **Step 3: Settings.test.tsx**

移除审核 tab 相关断言

- [ ] **Step 4: 运行测试确认无报错**

```bash
cd /Users/biner/Dev/novelagent/frontend && npm run test:run
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/stores/settingsStore.test.ts frontend/src/components/settings/hooks/__tests__/useSettings.test.ts frontend/src/pages/__tests__/Settings.test.tsx
git commit -m "test(frontend): remove review settings from test files"
```

---

## 任务 7：后端清理 — models/settings.py

**Files:**
- Modify: `backend/app/models/settings.py`

- [ ] **Step 1: 读取 settings.py**

```bash
cat /Users/biner/Dev/novelagent/backend/app/models/settings.py
```

- [ ] **Step 2: 移除 review_enabled / review_strictness 列**

```python
# 移除这两行：
review_enabled = Column(Boolean, default=True)
review_strictness = Column(String(20), default="standard")
```

- [ ] **Step 3: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/settings.py
git commit -m "refactor(backend): remove review_enabled and review_strictness columns"
```

---

## 任务 8：后端清理 — schemas/settings.py

**Files:**
- Modify: `backend/app/schemas/settings.py`

- [ ] **Step 1: 读取并修改 settings.py schema**

移除 `SettingsBase`、`SettingsUpdate`、`SettingsResponse` 中的 `review_enabled` / `review_strictness`

- [ ] **Step 2: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/settings.py
git commit -m "refactor(backend): remove review fields from settings schema"
```

---

## 任务 9：后端清理 — API settings.py

**Files:**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/utils/auth.py`

- [ ] **Step 1: settings.py API 清理**

- GET `/api/settings` 响应不再包含 `review_enabled` / `review_strictness`
- PUT `/api/settings` 不再接受这两个字段

- [ ] **Step 2: auth.py 清理**

- 移除注册用户时的默认值 `review_enabled=True` / `review_strictness="standard"`

- [ ] **Step 3: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/settings.py backend/app/utils/auth.py
git commit -m "refactor(backend): remove review fields from API and auth"
```

---

## 任务 10：后端清理 — Alembic Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_remove_review_settings.py`

- [ ] **Step 1: 创建 migration 文件**

```bash
docker exec novelagent-backend-1 alembic revision -m "remove review_enabled and review_strictness from user_settings"
```

- [ ] **Step 2: 编辑 migration 文件**

在 `upgrade()` 中添加：
```python
op.drop_column('user_settings', 'review_enabled')
op.drop_column('user_settings', 'review_strictness')
```

`downgrade()` 只加回空列：
```python
op.add_column('user_settings', sa.Column('review_enabled', sa.Boolean(), nullable=True))
op.add_column('user_settings', sa.Column('review_strictness', sa.String(20), nullable=True))
```

- [ ] **Step 3: 运行 migration 验证**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/
git commit -m "db(migration): remove review_enabled and review_strictness from user_settings"
```

---

## 任务 11：最终验证

- [ ] **Step 1: 前端构建**

```bash
cd /Users/biner/Dev/novelagent/frontend && npm run build
```

- [ ] **Step 2: 后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 3: 类型检查**

```bash
cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit
```

- [ ] **Step 4: 功能验证**

- 项目详情 API 返回的 `completed_chapters` 仍正常（依赖 chapters.review_passed）
- 自由 Agent 的 `review_chapter` 工具仍正常工作

- [ ] **Step 5: 整体提交**

```bash
git status
git add -A
git commit -m "refactor: remove dead review settings code (frontend + backend + migration)"
```

---

## 自检清单

- [ ] Spec 覆盖：前端删除 2 文件 + 修改 8 文件，后端删除 user_settings 两列 + migration
- [ ] Placeholder：无 TBD/TODO，所有步骤含实际代码
- [ ] 类型一致性：仅清理 settings 相关字段，chapters 表字段和 ReviewResponse 类型保留不变
- [ ] 无遗漏：ReviewConfigPanel.tsx, ReviewModeSelect.tsx, Settings.tsx, useSettings.ts, types/index.ts, settingsStore.ts, settingsStore.test.ts, useSettings.test.ts, Settings.test.tsx, models/settings.py, schemas/settings.py, api/settings.py, utils/auth.py, migration
- [ ] 活跃功能保护：项目进度计算（api/projects.py）、自由 Agent 审核工具（agent_tools.py）使用的 chapters 表字段未被触及
- [ ] ReviewResponse 保留：types/index.ts 中的 ReviewResponse / mapReviewResult / ReviewIssue 保留（用于章节审核结果）
- [ ] 测试覆盖：所有测试文件中移除对已删除字段的引用
