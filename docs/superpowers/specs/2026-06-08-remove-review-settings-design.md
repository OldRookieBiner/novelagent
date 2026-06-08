# 清除审核设置死代码

## 背景

旧版 WorkflowOrchestrator 通过用户设置中的审核开关控制章节生成后的审核流程。新版 LangGraph 工作流已将审核逻辑内嵌到 `style_check`、`character_consistency` 等写后自检节点，不再依赖用户设置中的 `review_enabled` / `review_strictness`。

经过进一步分析发现：
- `chapters` 表的 `review_passed` / `review_feedback` / `review_result` 仍有活跃使用（项目进度计算、自由 Agent 审核工具），**不是死代码**
- `user_settings` 表的 `review_enabled` / `review_strictness` 无任何消费者，是真正的死代码

注意：`types/index.ts` 中的 `ReviewResponse` 和 `mapReviewResult` 用于章节审核结果（与 Chapter 类型配合），不是用户设置，**不应删除**。

## 方案

只清理 settings 相关字段（用户审核开关），保留 chapters 表的审核字段。

## 前端清理

### 删除文件

- `components/settings/ReviewConfigPanel.tsx`
- `components/settings/ReviewModeSelect.tsx`

### 修改文件

**`pages/Settings.tsx`**
- 移除"审核设置"tab 内容（`ReviewConfigPanel` 渲染部分）
- 保留 tab 导航结构和 `SettingsTab` 类型定义，为将来扩展预留

**`components/settings/hooks/useSettings.ts`**
- 移除状态：`reviewMode` / `maxRewriteCount`
- 移除 setter：`setReviewMode` / `setMaxRewriteCount`
- 移除函数：`handleSaveReviewSettings`
- 移除加载时读取 `review_enabled` 的逻辑

**`types/index.ts`**
- `UserSettings` 移除 `review_enabled` / `review_strictness`
- `SettingsUpdate` 移除 `review_enabled` / `review_strictness`
- **保留** `ReviewResponse` / `mapReviewResult` / `ReviewIssue`（用于章节审核结果）
- **保留** `Chapter` 中的 `review_passed` / `review_feedback` / `review_result`

**`stores/settingsStore.ts`**
- settings 状态移除 `review_enabled` / `review_strictness`

**测试文件**
- `stores/settingsStore.test.ts` — 移除 `review_enabled` / `review_strictness` 引用
- `components/settings/hooks/__tests__/useSettings.test.ts` — 移除审核字段 mock
- `pages/__tests__/Settings.test.tsx` — 移除审核 tab 相关断言

## 后端清理

### 模型

**`models/settings.py`**
- 移除列：`review_enabled`、`review_strictness`

### Schema

**`schemas/settings.py`**
- `SettingsBase`、`SettingsUpdate`、`SettingsResponse` 移除 `review_enabled` / `review_strictness`

### API

**`api/settings.py`**
- GET 响应不再返回 `review_enabled` / `review_strictness`
- PUT 不再接受和写入这两个字段

**`utils/auth.py`**
- 移除注册默认值 `review_enabled=True` / `review_strictness="standard"`

### Migration

一条 Alembic migration，仅删除 user_settings 表的两列：
- `op.drop_column('user_settings', 'review_enabled')`
- `op.drop_column('user_settings', 'review_strictness')`
- downgrade：添加回空列

## 验证

- 前端：设置页正常打开，tab 导航结构完好，只剩模型配置 tab
- 后端：`pytest` 全量通过
- Docker：重建后端镜像，`/api/settings` GET/PUT 不再返回审核字段
- Migration：`alembic upgrade head` 无报错
- 功能验证：项目进度计算、自由 Agent 审核工具仍正常工作
- 类型检查：`npx tsc --noEmit` 无报错（ReviewResponse 等类型保留）
