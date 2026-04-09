# AI 智能体管理功能设计文档

## 概述

### 功能定位

允许用户管理 AI 智能体的 Prompts，支持全局默认配置和项目级别覆盖。

### 目标用户

需要对 AI 生成行为进行精细控制的小说创作者。

### 版本规划

| 版本 | 功能 |
|------|------|
| v0.3.0 | 智能体 Prompt 管理（本文档） |
| v0.3.1 | 版本历史、预览测试（后续迭代） |

---

## 功能设计

### 核心功能

1. **全局 Prompts 管理** - 配置所有项目默认使用的 Prompts
2. **项目 Prompts 覆盖** - 为特定项目单独配置 Prompts
3. **Prompt 编辑器** - 页面内展开式编辑，支持变量提示和重置默认

### 智能体列表

| 智能体类型 | agent_type | 说明 |
|------------|------------|------|
| 信息收集 | info_collection | 对话式收集小说创作信息 |
| 大纲生成 | outline_generation | 根据信息生成小说大纲 |
| 章节数建议 | chapter_count_suggestion | 根据大纲建议章节数 |
| 章节纲生成 | chapter_outline_generation | 生成每个章节的详细大纲 |
| 章节正文生成 | chapter_content_generation | 根据章节纲写正文 |
| 审核 | review | 审核章节质量 |
| 重写 | rewrite | 根据审核反馈重写章节 |

### 可用变量

每个智能体的 Prompt 可使用以下变量（以 `{variable}` 格式）：

**通用变量（所有智能体可用）：**
- `{genre}` - 题材类型
- `{theme}` - 核心主题
- `{main_characters}` - 主角设定
- `{world_setting}` - 世界设定
- `{style_preference}` - 风格偏好

**各智能体特有变量：**

| 智能体 | 特有变量 |
|--------|----------|
| 信息收集 | `{collected_info}` - 已收集的所有信息 |
| 大纲生成 | `{collected_info}` - 已收集的所有信息 |
| 章节数建议 | `{outline}` - 小说大纲内容 |
| 章节纲生成 | `{outline}` - 小说大纲内容, `{chapter_count}` - 章节数量 |
| 章节正文生成 | `{chapter_outline}` - 当前章节的大纲, `{previous_ending}` - 上一章结尾内容 |
| 审核 | `{chapter_content}` - 章节正文, `{chapter_outline}` - 章节大纲, `{strictness}` - 审核严格度 |
| 重写 | `{chapter_outline}` - 章节大纲, `{review_feedback}` - 审核反馈, `{original_content}` - 原章节内容 |

---

## 界面设计

### Settings 页面扩展

在现有 Settings 页面左侧导航新增"智能体管理"标签页。

```
Settings
├── 模型配置
├── 审核设置
└── 智能体管理  ← 新增
```

### 智能体管理页面布局

```
┌─────────────────────────────────────────────────────────┐
│ 设置                                                    │
├──────────────┬──────────────────────────────────────────┤
│ 模型配置     │ 智能体管理                               │
│ 审核设置     │ ┌──────────────────────────────────────┐ │
│ 智能体管理 ← │ │ 全局默认 Prompts                     │ │
│              │ │ 所有项目默认使用                      │ │
│              │ │ ┌────────────────────────────────┐   │ │
│              │ │ │ 信息收集智能体          [编辑] │   │ │
│              │ │ │ 用于对话式收集小说创作信息      │   │ │
│              │ │ └────────────────────────────────┘   │ │
│              │ │ ┌────────────────────────────────┐   │ │
│              │ │ │ 大纲生成智能体          [编辑] │   │ │
│              │ │ │ 根据收集的信息生成小说大纲      │   │ │
│              │ │ └────────────────────────────────┘   │ │
│              │ │ ... 更多智能体                       │ │
│              │ └──────────────────────────────────────┘ │
│              │                                          │
│              │ ┌──────────────────────────────────────┐ │
│              │ │ 项目自定义 Prompts                   │ │
│              │ │ 覆盖特定项目的智能体配置              │ │
│              │ │ ┌────────────────────────────────┐   │ │
│              │ │ │ 悬疑小说实验                    │   │ │
│              │ │ │ 已自定义 2 个智能体    [管理]   │   │ │
│              │ │ └────────────────────────────────┘   │ │
│              │ │ ┌────────────────────────────────┐   │ │
│              │ │ │ 科幻冒险          [+ 自定义]   │   │ │
│              │ │ └────────────────────────────────┘   │ │
│              │ └──────────────────────────────────────┘ │
└──────────────┴──────────────────────────────────────────┘
```

### Prompt 编辑交互

**默认状态：**
```
┌────────────────────────────────────────────────────────┐
│ 信息收集智能体                                  [编辑] │
│ 用于对话式收集小说创作信息                              │
│ 你是一个专业的小说创作助手，正在帮助用户收集创作小说... │
└────────────────────────────────────────────────────────┘
```

**展开编辑状态：**
```
┌────────────────────────────────────────────────────────┐
│ 信息收集智能体 (编辑中)                                 │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 你是一个专业的小说创作助手，正在帮助用户收集创作小说  │ │
│ │ 所需的信息。                                        │ │
│ │                                                    │ │
│ │ 你的任务是：                                        │ │
│ │ 1. 分析用户输入，提取有用的信息                     │ │
│ │ 2. 判断信息是否充足...                              │ │
│ │                                                    │ │
│ └────────────────────────────────────────────────────┘ │
│ 可用变量: {collected_info}                              │
│                                                        │
│ [取消] [重置默认] [保存]                                │
└────────────────────────────────────────────────────────┘
```

### 项目自定义流程

**点击项目的"+ 自定义"后：**
```
┌────────────────────────────────────────────────────────┐
│ 科幻冒险 - 智能体配置                                   │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 信息收集智能体              [使用全局 ✓]            │ │
│ │ 大纲生成智能体              [为此项目自定义]        │ │
│ │ 章节数建议智能体            [使用全局 ✓]            │ │
│ │ 章节纲生成智能体            [使用全局 ✓]            │ │
│ │ 章节正文生成智能体          [使用全局 ✓]            │ │
│ │ 审核智能体                  [使用全局 ✓]            │ │
│ │ 重写智能体                  [使用全局 ✓]            │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

**点击"为此项目自定义"后：**
```
┌────────────────────────────────────────────────────────┐
│ 大纲生成智能体 (本项目自定义)                           │
│ ┌────────────────────────────────────────────────────┐ │
│ │ [textarea - 编辑自定义 prompt]                      │ │
│ └────────────────────────────────────────────────────┘ │
│ 可用变量: {genre} {theme} {main_characters}...          │
│                                                        │
│ [取消] [保存] [恢复使用全局]                            │
└────────────────────────────────────────────────────────┘
```

---

## 数据库设计

### 新增表

#### agent_prompts（全局 Prompts）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| user_id | INTEGER | 外键，关联 users |
| agent_type | VARCHAR(50) | 智能体类型 |
| prompt_content | TEXT | Prompt 内容 |
| updated_at | TIMESTAMP | 更新时间 |

约束：`UNIQUE(user_id, agent_type)`

#### project_agent_prompts（项目自定义 Prompts）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键 |
| project_id | INTEGER | 外键，关联 projects |
| agent_type | VARCHAR(50) | 智能体类型 |
| prompt_content | TEXT | 自定义 Prompt 内容 |
| updated_at | TIMESTAMP | 更新时间 |

约束：`UNIQUE(project_id, agent_type)`

### 默认数据

系统初始化时，为每个用户创建默认的全局 Prompts（从 `prompts.py` 中的硬编码值复制）。

---

## API 设计

### 全局 Prompts

```
GET /api/agent-prompts
```
获取当前用户的所有全局 Prompts。

响应：
```json
{
  "prompts": [
    {
      "agent_type": "info_collection",
      "agent_name": "信息收集智能体",
      "prompt_content": "...",
      "variables": ["collected_info"],
      "is_default": false,
      "updated_at": "2026-04-09T10:00:00Z"
    },
    ...
  ]
}
```

```
PUT /api/agent-prompts/:type
```
更新某个全局 Prompt。

请求体：
```json
{
  "prompt_content": "新的 prompt 内容..."
}
```

```
POST /api/agent-prompts/:type/reset
```
重置某个全局 Prompt 为系统默认值。

### 项目自定义 Prompts

```
GET /api/projects/:id/agent-prompts
```
获取项目的 Prompts 配置状态（哪些使用了全局，哪些自定义了）。

响应：
```json
{
  "project_id": 1,
  "project_name": "科幻冒险",
  "agents": [
    {
      "agent_type": "info_collection",
      "agent_name": "信息收集智能体",
      "use_custom": false,
      "custom_content": null
    },
    {
      "agent_type": "outline_generation",
      "agent_name": "大纲生成智能体",
      "use_custom": true,
      "custom_content": "自定义的 prompt..."
    },
    ...
  ]
}
```

```
PUT /api/projects/:id/agent-prompts/:type
```
设置项目自定义 Prompt。

请求体：
```json
{
  "prompt_content": "项目自定义的 prompt..."
}
```

```
DELETE /api/projects/:id/agent-prompts/:type
```
删除项目自定义 Prompt，恢复使用全局默认。

### 获取有效 Prompt（内部 API）

```
GET /api/projects/:id/agent-prompts/:type/effective
```
获取项目实际使用的 Prompt（优先返回项目自定义，否则返回全局默认）。

响应：
```json
{
  "source": "custom",  // "custom" 或 "global"
  "prompt_content": "..."
}
```

---

## 后端实现

### 新增文件

```
backend/app/
├── models/
│   └── agent_prompt.py      # 新增：数据模型
├── schemas/
│   └── agent_prompt.py      # 新增：Pydantic schemas
├── api/
│   └── agent_prompts.py     # 新增：API 路由
└── services/
    └── prompt_service.py    # 新增：Prompt 服务（获取有效 prompt）
```

### 修改文件

1. **prompts.py** - 保留默认 Prompt 常量，作为系统默认值
2. **llm.py** - 修改 LLM 服务，从数据库获取 prompt 而非硬编码
3. **database.py** - 添加新模型导入

### Prompt 获取逻辑

```python
def get_effective_prompt(
    db: Session,
    user_id: int,
    project_id: int,
    agent_type: str
) -> str:
    """
    获取项目实际使用的 Prompt
    优先级：项目自定义 > 全局默认 > 系统默认
    """
    # 1. 查找项目自定义
    custom = db.query(ProjectAgentPrompt).filter(
        ProjectAgentPrompt.project_id == project_id,
        ProjectAgentPrompt.agent_type == agent_type
    ).first()
    if custom:
        return custom.prompt_content

    # 2. 查找全局默认
    global_prompt = db.query(AgentPrompt).filter(
        AgentPrompt.user_id == user_id,
        AgentPrompt.agent_type == agent_type
    ).first()
    if global_prompt:
        return global_prompt.prompt_content

    # 3. 返回系统默认
    return DEFAULT_PROMPTS.get(agent_type, "")
```

---

## 前端实现

### 新增文件

```
frontend/src/
├── components/settings/
│   └── AgentPromptEditor.tsx    # 新增：Prompt 编辑器组件
├── pages/
│   └── Settings.tsx             # 修改：添加智能体管理标签页
├── stores/
│   └── agentPromptStore.ts      # 新增：状态管理
└── lib/
    └── api.ts                   # 修改：添加 API 调用
```

### 组件设计

**AgentPromptEditor.tsx**
```typescript
interface AgentPromptEditorProps {
  agentType: string
  agentName: string
  promptContent: string
  variables: string[]
  isEditable: boolean
  onSave: (content: string) => void
  onReset?: () => void
}
```

---

## 数据迁移

### Alembic 迁移脚本

```python
# alembic/versions/003_add_agent_prompts.py

def upgrade():
    # 创建 agent_prompts 表
    op.create_table(
        'agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'agent_type')
    )

    # 创建 project_agent_prompts 表
    op.create_table(
        'project_agent_prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_type', sa.String(50), nullable=False),
        sa.Column('prompt_content', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'agent_type')
    )

def downgrade():
    op.drop_table('project_agent_prompts')
    op.drop_table('agent_prompts')
```

### 初始数据迁移

在用户首次访问智能体管理页面时，检查是否已有全局 Prompts，若无则从系统默认值创建。

---

## 验收标准

### 功能验收

1. ✅ 用户可在 Settings 页面看到"智能体管理"标签页
2. ✅ 用户可查看所有智能体的全局默认 Prompts
3. ✅ 用户可编辑任意智能体的全局 Prompt
4. ✅ 编辑时显示可用的变量提示
5. ✅ 用户可重置任意智能体的 Prompt 为系统默认
6. ✅ 用户可查看项目列表及其 Prompts 配置状态
7. ✅ 用户可为特定项目设置自定义 Prompt
8. ✅ 项目自定义 Prompt 优先于全局 Prompt 生效
9. ✅ 用户可删除项目自定义 Prompt，恢复使用全局
10. ✅ 修改 Prompt 后，实际的 AI 生成行为随之改变

### 技术验收

1. ✅ 数据库迁移正常执行
2. ✅ API 接口正常工作
3. ✅ 前端组件正常渲染和交互
4. ✅ 现有功能不受影响（向后兼容）

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| Prompt 写错导致 AI 行为异常 | 提供"重置默认"功能，用户可一键恢复 |
| 变量名写错 | 编辑器显示可用变量列表，未来可加语法检查 |
| 长 Prompt 编辑体验 | textarea 自适应高度，支持滚动 |
| 迁移时数据丢失 | 先检测用户是否存在 Prompts，按需初始化 |

---

## 后续迭代

| 版本 | 功能 |
|------|------|
| v0.3.1 | Prompt 版本历史，可回滚 |
| v0.3.2 | Prompt 预览测试功能 |
| v0.4.0 | 自定义智能体（创建新的智能体类型） |