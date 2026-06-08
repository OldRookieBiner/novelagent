# 清除审核设置死代码实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一次性清除审核设置相关死代码，包括前端审核 tab、后端 settings 字段、chapters 表字段，以及对应的 Alembic migration。

**Architecture:** 前端移除审核 tab 及相关组件/类型，后端删除 5 个数据库列（Alembic migration），同步清理 schema/API/工具函数中的引用。

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
| `frontend/src/types/index.ts` | 修改：移除审核相关类型 |
| `frontend/src/stores/settingsStore.ts` | 修改：移除审核字段 |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | 检查清理 |
| `frontend/src/pages/__tests__/Settings.test.tsx` | 修改：移除审核断言 |

### 后端（修改 + Migration）

| 文件 | 操作 |
|------|------|
| `backend/app/models/settings.py` | 修改：移除 review_enabled / review_strictness 列 |
| `backend/app/models/chapter.py` | 修改：移除 review_passed / review_feedback / review_result 列 |
| `backend/app/schemas/settings.py` | 修改：移除对应字段 |
| `backend/app/schemas/chapter.py` | 修改：移除对应字段 |
| `backend/app/api/settings.py` | 修改：API 移除审核字段 |
| `backend/app/api/chapters.py` | 修改：API 移除审核字段 |
| `backend/app/utils/auth.py` | 修改：移除注册默认值 |
| `backend/alembic/versions/` | 新增：删除列的 migration |

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
- Test: `frontend/src/pages/__tests__/Settings.test.tsx`

- [ ] **Step 1: 读取当前 Settings.tsx**

```bash
cat /Users/biner/Dev/novelagent/frontend/src/pages/Settings.tsx
```

- [ ] **Step 2: 移除审核 tab 内容，保留 tab 导航结构**

需要做的修改：
1. 移除 `import { Shield }` 如果仅用于审核 tab
2. 移除 tab 列表中的 `{ id: 'review', label: '审核设置', icon: Shield }`
3. 移除 `activeTab === 'review'` 条件分支中的 `<ReviewConfigPanel>` 渲染
4. 如果 `SettingsTab` 类型只用于审核 tab，可保留但移除使用（为将来扩展）

- [ ] **Step 3: 运行测试确认无报错**

```bash
cd /Users/biner/Dev/novelagent/frontend && npm run test:run -- --testPathPattern="Settings"
```

- [ ] **Step 4: 提交**

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

- [ ] **Step 3: 运行测试确认无报错**

```bash
cd /Users/biner/Dev/novelagent/frontend && npm run test:run
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/settings/hooks/useSettings.ts
git commit -m "refactor(frontend): remove review settings from useSettings hook"
```

---

## 任务 4：前端清理 — types/index.ts

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 读取当前 types/index.ts 查找审核相关定义**

```bash
rg "review" /Users/biner/Dev/novelagent/frontend/src/types/index.ts --no-heading -n
```

- [ ] **Step 2: 移除审核相关类型**

需要移除的内容（根据之前分析）：
- `ReviewResponse` 类型定义
- `mapReviewResult` 函数
- `SettingsUpdate` / `SettingsResponse` 中的 `review_enabled` / `review_strictness`
- `Chapter` 类型中的 `review_passed` / `review_feedback` / `review_result`

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd /Users/biner/Dev/novelagent/frontend && npx tsc --noEmit
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "refactor(frontend): remove review types from index.ts"
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

- [ ] **Step 3: 运行测试确认无报错**

```bash
cd /Users/biner/Dev/novelagent/frontend && npm run test:run -- --testPathPattern="settingsStore"
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/stores/settingsStore.ts
git commit -m "refactor(frontend): remove review fields from settingsStore"
```

---

## 任务 6：前端清理 — AIAssistantPanel.tsx

**Files:**
- Modify: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`

- [ ] **Step 1: 检查是否有审核相关引用**

```bash
rg "review" /Users/biner/Dev/novelagent/frontend/src/components/workbench/creation/AIAssistantPanel.tsx --no-heading -n
```

- [ ] **Step 2: 如有引用则清理，无则跳过**

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/workbench/creation/AIAssistantPanel.tsx
git commit -m "refactor(frontend): clean up review references in AIAssistantPanel"
```

---

## 任务 7：后端清理 — models/settings.py 和 models/chapter.py

**Files:**
- Modify: `backend/app/models/settings.py`
- Modify: `backend/app/models/chapter.py`

- [ ] **Step 1: 读取 settings.py 和 chapter.py**

```bash
cat /Users/biner/Dev/novelagent/backend/app/models/settings.py
cat /Users/biner/Dev/novelagent/backend/app/models/chapter.py
```

- [ ] **Step 2: settings.py 移除 review_enabled / review_strictness 列**

```python
# 移除这两行：
review_enabled = Column(Boolean, default=True)
review_strictness = Column(String(20), default="standard")
```

- [ ] **Step 3: chapter.py 移除 review_passed / review_feedback / review_result 列**

```python
# 移除这三行：
review_passed = Column(Boolean, default=False)
review_feedback = Column(Text, nullable=True)
review_result = Column(JSON, nullable=True)
```

- [ ] **Step 4: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/settings.py backend/app/models/chapter.py
git commit -m "refactor(backend): remove review columns from models"
```

---

## 任务 8：后端清理 — schemas

**Files:**
- Modify: `backend/app/schemas/settings.py`
- Modify: `backend/app/schemas/chapter.py`

- [ ] **Step 1: 读取并修改 settings.py schema**

移除 `SettingsBase`、`SettingsUpdate`、`SettingsResponse` 中的 `review_enabled` / `review_strictness`

- [ ] **Step 2: 读取并修改 chapter.py schema**

移除 `ChapterResponse` / `ChapterCreate` 等 schema 中的 `review_passed` / `review_feedback` / `review_result`

- [ ] **Step 3: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/schemas/settings.py backend/app/schemas/chapter.py
git commit -m "refactor(backend): remove review fields from schemas"
```

---

## 任务 9：后端清理 — API

**Files:**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/api/chapters.py`
- Modify: `backend/app/utils/auth.py`

- [ ] **Step 1: settings.py API 清理**

- GET `/api/settings` 响应不再包含 `review_enabled` / `review_strictness`
- PUT `/api/settings` 不再接受这两个字段
- 默认创建逻辑（注册用户）不再设置这两个字段

- [ ] **Step 2: chapters.py API 清理**

- CRUD 响应不再返回 `review_passed` / `review_feedback` / `review_result`

- [ ] **Step 3: auth.py 清理**

- 移除注册用户时的默认值 `review_enabled=True` / `review_strictness="standard"`

- [ ] **Step 4: 运行测试确认无报错**

```bash
docker exec novelagent-backend-1 pytest -v
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/settings.py backend/app/api/chapters.py backend/app/utils/auth.py
git commit -m "refactor(backend): remove review fields from API endpoints"
```

---

## 任务 10：后端清理 — Alembic Migration

**Files:**
- Create: `backend/alembic/versions/xxxx_remove_review_settings.py`

- [ ] **Step 1: 创建 migration 文件**

```bash
docker exec novelagent-backend-1 alembic revision -m "remove review settings and chapter fields"
```

- [ ] **Step 2: 编辑 migration 文件**

在 `upgrade()` 中添加：
```python
op.drop_column('user_settings', 'review_enabled')
op.drop_column('user_settings', 'review_strictness')
op.drop_column('chapters', 'review_passed')
op.drop_column('chapters', 'review_feedback')
op.drop_column('chapters', 'review_result')
```

`downgrade()` 只加回空列（不回填数据）：
```python
op.add_column('user_settings', sa.Column('review_enabled', sa.Boolean(), nullable=True))
op.add_column('user_settings', sa.Column('review_strictness', sa.String(20), nullable=True))
op.add_column('chapters', sa.Column('review_passed', sa.Boolean(), nullable=True))
op.add_column('chapters', sa.Column('review_feedback', sa.Text(), nullable=True))
op.add_column('chapters', sa.Column('review_result', sa.JSON(), nullable=True))
```

- [ ] **Step 3: 运行 migration 验证**

```bash
docker exec novelagent-backend-1 alembic upgrade head
```

- [ ] **Step 4: 提交**

```bash
git add backend/alembic/versions/
git commit -m "db(migration): remove review fields from user_settings and chapters tables"
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

- [ ] **Step 3: 整体提交**

```bash
git status
git add -A
git commit -m "refactor: remove dead review settings code (frontend + backend + migration)"
```

---

## 自检清单

- [ ] Spec 覆盖：前端删除 2 文件 + 修改 5 文件，后端删除 5 列 + migration
- [ ] Placeholder：无 TBD/TODO，所有步骤含实际代码
- [ ] 类型一致性：前后端字段名对应（settings: review_enabled/strictness, chapters: review_passed/feedback/result）
- [ ] 无遗漏：ReviewConfigPanel.tsx, ReviewModeSelect.tsx, Settings.tsx, useSettings.ts, types/index.ts, settingsStore.ts, AIAssistantPanel.tsx, Settings.test.tsx, models/settings.py, models/chapter.py, schemas/settings.py, schemas/chapter.py, api/settings.py, api/chapters.py, utils/auth.py, migration
