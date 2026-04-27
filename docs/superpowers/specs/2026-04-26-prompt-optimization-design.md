# Prompt 模板系统级配置设计

**日期：** 2026-04-26

## 背景

当前系统存在两套提示词配置（全局提示词、项目级自定义），但均未被 LangGraph 节点实际使用：
- API 层正常，数据库存储正常，前端 UI 正常
- LangGraph 节点直接导入硬编码的默认提示词，绕过了用户配置

## 目标

简化智能体提示词配置功能，移除未实际使用的用户级全局提示词和项目级自定义，仅保留系统级配置。

---

## 设计决策

### 1. 功能范围

| 项目 | 决定 |
|-----|------|
| 提示词级别 | 仅系统级（所有用户、所有项目共用） |
| 用户级 | 暂不支持，后续扩展 |
| 项目级 | 暂不支持，后续扩展 |

### 2. 数据存储

**新建 `system_config` 表：**
```sql
CREATE TABLE system_config (
    key VARCHAR PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**删除现有表：**
- `agent_prompts`
- `project_agent_prompts`

### 3. API 设计

```
GET  /api/system/prompts              # 获取所有提示词列表
PUT  /api/system/prompts/{type}       # 更新单个提示词
POST /api/system/prompts/{type}/reset # 重置为默认值
```

### 4. 前端 UI

- 顶部标签切换 5 种 Agent 类型
- 大编辑区直接编辑
- 底部显示更新时间 + 操作按钮

### 5. LangGraph 节点集成

每个节点从 `system_config` 表读取提示词，移除硬编码的默认提示词导入。

---

## Agent 类型定义

| type | name | variables |
|------|------|-----------|
| outline_generation | 大纲生成 | inspiration_template, chapter_count |
| chapter_outline_generation | 章节大纲生成 | outline, plot_points, chapter_count, chapter_number, previous_chapter_info |
| chapter_content_generation | 正文生成 | chapter_outline, previous_ending, genre, main_characters, world_setting, style_preference |
| review | 审核 | strictness, chapter_outline, chapter_content, genre, main_characters, style_preference |
| rewrite | 重写 | chapter_outline, review_feedback, original_content, genre, main_characters, world_setting |

---

## 待实施任务

1. 删除 `agent_prompts` 和 `project_agent_prompts` 模型及表
2. 删除相关 API 路由（`/api/agent-prompts`, `/api/projects/{id}/agent-prompts`）
3. 新建 `system_config` 模��及表
4. 创建新 API 路由 `/api/system/prompts`
5. 更新前端设置页面（移除项目级自定义）
6. 修改 LangGraph 节点从数据库读取提示词
7. 集成验证

---

## 实施顺序

1. 数据库迁移（删除旧表，新建 system_config）
2. 后端模型 + API
3. 前端 UI
4. LangGraph 节点集成
5. 端到端测试