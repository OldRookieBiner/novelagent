# 清除审核设置死代码

## 背景

旧版 WorkflowOrchestrator 通过用户设置中的审核开关控制章节生成后的审核流程。新版 LangGraph 工作流已将审核逻辑内嵌到 `style_check`、`character_consistency` 等写后自检节点，不再依赖用户设置中的 `review_enabled` / `review_strictness`。章节模型上的 `review_passed` / `review_feedback` / `review_result` 同样无消费者。

## 方案

一次性全清：一个 PR，一条 Alembic migration，删除所有死字段及相关前端组件。

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
- `SettingsUpdate` / `SettingsResponse` 移除 `review_enabled` / `review_strictness`
- `Chapter` 类型移除 `review_passed` / `review_feedback` / `review_result`
- 删除 `ReviewResponse` 类型和 `mapReviewResult` 函数

**`stores/settingsStore.ts`**
- settings 状态移除 `review_enabled` / `review_strictness`

**`components/workbench/creation/AIAssistantPanel.tsx`**
- 清理审核相关类型/逻辑引用

**`pages/__tests__/Settings.test.tsx`**
- 移除审核 tab 相关断言

## 后端清理

### 模型

**`models/settings.py`**
- 移除列：`review_enabled`、`review_strictness`

**`models/chapter.py`**
- 移除列：`review_passed`、`review_feedback`、`review_result`

### Schema

**`schemas/settings.py`**
- `SettingsBase`、`SettingsUpdate`、`SettingsResponse` 移除 `review_enabled` / `review_strictness`

**`schemas/chapter.py`**
- 移除 `review_passed` / `review_feedback` / `review_result` 相关字段

### API

**`api/settings.py`**
- GET 响应不再返回 `review_enabled` / `review_strictness`
- PUT 不再接受和写入这两个字段
- 默认创建（新用户注册）不再设置这两个字段

**`api/chapters.py`**
- CRUD 序列化移除 `review_passed` / `review_feedback` / `review_result`

**`utils/auth.py`**
- 移除注册默认值 `review_enabled=True` / `review_strictness="standard"`

### Migration

一条 Alembic migration：
- `op.drop_column('user_settings', 'review_enabled')`
- `op.drop_column('user_settings', 'review_strictness')`
- `op.drop_column('chapters', 'review_passed')`
- `op.drop_column('chapters', 'review_feedback')`
- `op.drop_column('chapters', 'review_result')`
- downgrade：添加回空列（不回填数据，这些字段无消费者）

## 验证

- 前端：设置页正常打开，tab 导航结构完好，只剩模型配置 tab
- 后端：`pytest` 全量通过
- Docker：重建后端镜像，`/api/settings` GET/PUT 不再返回审核字段
- Migration：`alembic upgrade head` 无报错
