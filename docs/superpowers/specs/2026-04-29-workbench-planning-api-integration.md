# 工作台规划模块 API 对接设计文档

## 概述

**版本**: v0.8.2
**日期**: 2026-04-29
**目标**: 为工作台规划模块对接后端 API，实现灵感采集、人物管理、关系管理的完整功能

### 对接范围

| 模块 | 当前状态 | 目标 |
|------|----------|------|
| 灵感采集 | 仅本地 localStorage 草稿 | 保存到后端 collected_info |
| 人物管理 | 列表、删除可用；新增/编辑显示"开发中" | 完整 CRUD |
| 关系管理 | 列表、删除可用；新增/编辑显示"开发中" | 完整 CRUD |

---

## API 端点汇总

### 灵感采集 API

| 方法 | 端点 | 功能 |
|------|------|------|
| PUT | `/api/projects/{id}/outline/collected-info` | 保存灵感数据到大纲 |

**请求体字段：**
```typescript
{
  genre?: string           // 小说类型
  theme?: string           // 核心主题
  main_characters?: string // 主要人物
  world_setting?: string   // 世界观设定
  style_preference?: string // 风格偏好
  // 灵感表单的额外字段
  targetReader?: string    // 目标读者
  targetWords?: number     // 目标字数
  wordsPerChapter?: string // 每章字数
  narrative?: string       // 叙事视角
  // ... 其他灵感表单字段
}
```

### 人物管理 API

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/projects/{id}/characters` | 获取人物列表 |
| POST | `/api/projects/{id}/characters` | 新增人物 |
| PUT | `/api/projects/{id}/characters/{id}` | 更新人物 |
| DELETE | `/api/projects/{id}/characters/{id}` | 删除人物 |

**Character 类型：**
```typescript
interface Character {
  id: number
  project_id: number
  name: string
  role: string           // 主角/核心反派/重要配角/配角/次要
  personality?: string   // 性格
  core_motivation?: string // 核心动机
  catchphrase?: string   // 口头禅
  background?: string    // 背景故事
  // ... 其他字段
}
```

### 关系管理 API

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/projects/{id}/relations` | 获取关系列表 |
| POST | `/api/projects/{id}/relations` | 新增关系 |
| PUT | `/api/projects/{id}/relations/{id}` | 更新关系 |
| DELETE | `/api/projects/{id}/relations/{id}` | 删除关系 |

**Relation 类型：**
```typescript
interface Relation {
  id: number
  project_id: number
  character_a_id: number
  character_b_id: number
  relation_type: string   // 信任/敌对/感情/合作/利用/陌生
  current_status?: string // 当前状态
  trust_level: number     // 信任度 0-100
}
```

---

## 文件变更规划

### 修改文件

| 文件 | 变更内容 |
|------|----------|
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 添加保存按钮，对接 collectedInfoApi |
| `frontend/src/components/workbench/planning/CharacterPanel.tsx` | 实现新增/编辑弹窗 |
| `frontend/src/components/workbench/planning/RelationPanel.tsx` | 实现新增/编辑弹窗 |

### 新增组件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/workbench/planning/CharacterDialog.tsx` | 人物新增/编辑弹窗 |
| `frontend/src/components/workbench/planning/RelationDialog.tsx` | 关系新增/编辑弹窗 |

---

## 实现策略

### 灵感采集

1. 添加"保存"按钮到页面顶部
2. 保存时将表单数据映射到 `CollectedInfoUpdate` 格式
3. 调用 `collectedInfoApi.update()`
4. 显示保存成功/失败 toast

### 人物管理

1. 新增按钮 → 打开 CharacterDialog（空表单）
2. 编辑按钮 → 打开 CharacterDialog（预填数据）
3. Dialog 提交时调用 `characterApi.create()` 或 `characterApi.update()`
4. 成功后刷新列表

### 关系管理

1. 新增按钮 → 打开 RelationDialog（选择人物、填写关系）
2. 编辑按钮 → 打开 RelationDialog（预填数据）
3. Dialog 提交时调用 `relationApi.create()` 或 `relationApi.update()`
4. 成功后刷新列表

---

## 约束条件

1. **不修改 UI 布局和样式** - 仅添加事件绑定和 API 调用
2. 使用现有的 `characterApi` 和 `relationApi` 客户端
3. 使用 `toast` 显示通知
4. 遵循项目代码风格：中文注释、camelCase 命名、Allman 风格大括号