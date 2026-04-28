# 人物设定模块设计文档

## 概述

**版本**：v0.7.0
**日期**：2026-04-28
**分支**：`feature/character-setting-module`

### 目标

1. 新增独立的人物设定功能模块，解决现有大纲中人物设定单薄的问题
2. 新增人物关系规划与演变追踪功能
3. 优化上下文传递机制，提升 AI 生成内容的一致性

### 背景

当前系统的问题：
- 人物设定嵌入大纲，篇幅限制导致人物塑造单薄
- 章节正文生成时，人物信息传递不完整（只传 name + personality + motivation）
- 无法追踪人物关系演变，长篇创作容易出现人物崩坏

---

## 一、篇幅定义

| 篇幅 | 目标字数范围 | 预估章节数 | 一期支持 |
|------|-------------|-----------|---------|
| 短篇 | 1千 - 3万字 | 3-25章 | ✅ |
| 中篇 | 3万 - 15万字 | 25-75章 | ❌ 二期 |
| 长篇 | 15万 - 100万字 | 75-250章 | ❌ 二期 |
| 超长篇 | 100万字以上 | 250章以上 | ❌ 二期 |

---

## 二、数据模型

### 2.1 Character 表（人物设定）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | int | 是 | 主键 |
| project_id | int | 是 | 关联项目 |
| name | string(100) | 是 | 姓名 |
| role | string(50) | 是 | 角色定位：protagonist/antagonist/supporting/minor |
| personality | text | 否 | 性格描述 |
| catchphrase | string(200) | 否 | 口头禅 |
| habit_action | string(200) | 否 | 习惯动作 |
| deep_fear | text | 否 | 深层恐惧/弱点 |
| core_motivation | text | 否 | 核心动机 |
| growth_arc | text | 否 | 成长弧线 |
| appearance | text | 否 | 外貌描写 |
| backstory | text | 否 | 背景故事 |
| signature_item | string(200) | 否 | 标志性物品 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**索引**：`project_id`

### 2.2 CharacterRelation 表（人物关系）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | int | 是 | 主键 |
| project_id | int | 是 | 关联项目 |
| character_a_id | int | 是 | 人物A ID |
| character_b_id | int | 是 | 人物B ID |
| relation_type | string(50) | 是 | 关系类型：trust/hostile/romantic/family/rival/neutral |
| direction | string(20) | 是 | 方向：bidirectional/unidirectional |
| current_status | string(100) | 否 | 当前状态描述 |
| trust_level | int | 否 | 信任度 0-100 |
| description | text | 否 | 关系描述 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**索引**：`project_id`, `character_a_id`, `character_b_id`
**约束**：唯一约束 `(project_id, character_a_id, character_b_id)`

### 2.3 RelationEvolution 表（关系演变规划）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | int | 是 | 主键 |
| relation_id | int | 是 | 关联关系 |
| trigger_chapter | int | 是 | 触发章节（约在第N章） |
| event_description | text | 是 | 事件描述 |
| status_before | string(100) | 否 | 变化前状态 |
| status_after | string(100) | 是 | 变化后状态 |
| trust_before | int | 否 | 变化前信任度 |
| trust_after | int | 否 | 变化后信任度 |
| ai_suggestion | text | 否 | AI 建议 |
| is_triggered | bool | 否 | 是否已触发，默认 false |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |

**索引**：`relation_id`, `trigger_chapter`

### 2.4 RelationHistory 表（关系追溯记录）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | int | 是 | 主键 |
| relation_id | int | 是 | 关联关系 |
| chapter_number | int | 是 | 章节号 |
| content | text | 是 | 发生了什么 |
| status_change | string(200) | 否 | 状态变化 |
| trust_change | int | 否 | 信任度变化 |
| triggered_plan_id | int | 否 | 触发的规划节点 ID |
| created_at | datetime | 是 | 创建时间 |

**索引**：`relation_id`, `chapter_number`

---

## 三、工作流调整

### 3.1 当前工作流

```
灵感收集 → 大纲生成 → 章节大纲 → 章节正文 → 审核
```

### 3.2 调整后工作流

```
灵感收集 → 大纲初稿 → 人物设定 → 关系规划 → 大纲完善 → 章节大纲 → 章节正文 → 审核 → 演变提取
```

### 3.3 LangGraph 新增节点

| 节点 | 功能 | 触发时机 |
|------|------|----------|
| `generate_characters_node` | AI 批量生成人物 | 大纲初稿审核后 |
| `generate_relations_node` | AI 生成关系规划 | 人物设定审核后 |
| `refine_outline_node` | 根据人物完善大纲 | 关系规划审核后 |
| `extract_evolution_node` | 写作后提取演变 | 章节审核通过后 |

### 3.4 NovelState 新增字段

```python
class NovelState(TypedDict):
    # ... 现有字段保持不变

    # 新增：人物相关
    characters: list[dict]              # 人物列表
    relations: list[dict]               # 关系列表
    evolution_plans: list[dict]         # 演变规划
    relation_history: list[dict]        # 演变追溯

    # 新增：篇幅
    novel_length: str                   # short/medium/long/epic
```

---

## 四、上下文传递（短篇）

### 4.1 章节正文生成时传递

| 内容 | 来源 | 传递方式 |
|------|------|----------|
| 完整大纲 | NovelState.outline_* | 直接传入 Prompt |
| 全部已写章节 | NovelState.written_chapters | 全文传入（短篇章节数少） |
| 全部人物设定 | NovelState.characters | 格式化为人物档案 |
| 全部关系列表 | NovelState.relations | 格式化为关系网络 |
| 当前演变节点 | NovelState.evolution_plans | 过滤当前章节 ±2 章的节点 |
| 世界观 | NovelState.outline_world_setting | 直接传入 |
| 风格偏好 | NovelState.collected_info | 直接传入 |

### 4.2 Prompt 模板更新

章节正文 Prompt 新增：

```
## 人物档案
{characters_formatted}

## 人物关系网络
{relations_formatted}

## 当前章节的关系演变提示
{active_evolution_nodes}
```

---

## 五、前端设计

### 5.1 入口位置

项目详情页新增 Tab：「人物设定」

位置：灵感 → **人物设定** → 大纲 → 章节大纲 → 写作

### 5.2 页面结构

**单一页面，步骤条引导：**

```
步骤1: 大纲初稿 → 步骤2: 人物设定 → 步骤3: 关系规划 → 步骤4: 大纲完善
```

每个步骤：
- 显示 AI 生成结果
- 提供审核确认按钮
- 可选：编辑/重新生成

### 5.3 交互流程

1. 用户点击「人物设定」Tab
2. 显示步骤条，从步骤 2（人物设定）开始
3. AI 自动生成人物卡片
4. 用户审核，可选编辑或要求重新生成
5. 确认后进入下一步（关系规划）
6. 重复审核流程
7. 全部确认后，返回大纲页面继续后续流程

---

## 六、API 端点

### 6.1 人物 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/characters` | 获取人物列表 |
| POST | `/api/projects/{id}/characters` | 创建人物 |
| PUT | `/api/projects/{id}/characters/{cid}` | 更新人物 |
| DELETE | `/api/projects/{id}/characters/{cid}` | 删除人物 |
| POST | `/api/projects/{id}/characters/generate` | AI 批量生成人物 |
| POST | `/api/projects/{id}/characters/{cid}/optimize` | AI 优化单个人物 |

### 6.2 关系 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/relations` | 获取关系列表 |
| POST | `/api/projects/{id}/relations` | 创建关系 |
| PUT | `/api/projects/{id}/relations/{rid}` | 更新关系 |
| DELETE | `/api/projects/{id}/relations/{rid}` | 删除关系 |
| POST | `/api/projects/{id}/relations/generate` | AI 生成关系规划 |

### 6.3 演变 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/relations/{rid}/evolution` | 获取演变规划 |
| POST | `/api/projects/{id}/relations/{rid}/evolution` | 添加演变节点 |
| PUT | `/api/projects/{id}/relations/{rid}/evolution/{eid}` | 更新演变节点 |
| DELETE | `/api/projects/{id}/relations/{rid}/evolution/{eid}` | 删除演变节点 |
| GET | `/api/projects/{id}/relations/{rid}/history` | 获取演变历史 |

---

## 七、数据库迁移

### 7.1 迁移文件

`alembic/versions/xxx_add_character_tables.py`

```python
def upgrade():
    # 1. 创建 characters 表
    op.create_table(
        'characters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        # ... 其他字段
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_characters_project_id', 'characters', ['project_id'])

    # 2. 创建 character_relations 表
    # 3. 创建 relation_evolutions 表
    # 4. 创建 relation_histories 表

def downgrade():
    op.drop_table('relation_histories')
    op.drop_table('relation_evolutions')
    op.drop_table('character_relations')
    op.drop_table('characters')
```

### 7.2 现有数据兼容

- 现有 Outline 表中的 `characters` 字段保留，作为备份
- 迁移时不需要从现有数据导入（AI 重新生成）

---

## 八、实现优先级

### Phase 1：核心功能（一期）

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 数据库表创建 | 4 个新表 |
| P0 | Character CRUD API | 基础增删改查 |
| P0 | CharacterRelation CRUD API | 基础增删改查 |
| P0 | RelationEvolution CRUD API | 基础增删改查 |
| P0 | NovelState 扩展 | 新增字段 |
| P0 | 人物设定页面 | 列表+详情编辑 |
| P0 | AI 生成人物 | 批量生成 |
| P0 | AI 生成关系 | 批量生成 |
| P0 | 上下文传递更新 | 章节正文生成 |

### Phase 2：完善功能（二期）

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P1 | 关系追溯自动提取 | 写作后 AI 提取 |
| P1 | 中篇上下文传递 | 分层传递机制 |
| P1 | 图形化关系图谱 | 可视化展示 |
| P1 | 超长篇渐进式人物 | 写作中添加人物 |

---

## 九、技术约束

### 9.1 禁止事项

- ❌ 不使用 RAG（短篇直接传递）
- ❌ 不修改现有核心表的字段类型
- ❌ 不破坏现有 API 的向后兼容性

### 9.2 必须遵守

- ✅ 新节点遵循 LangGraph 签名 `(state) -> state`
- ✅ 新增数据放入 NovelState，复用现有状态管理
- ✅ 数据库表设计遵循现有风格
- ✅ 前端组件复用 shadcn/ui

---

## 十、验收标准

### 10.1 功能验收

- [ ] 可以创建/编辑/删除人物
- [ ] AI 可以批量生成人物
- [ ] 可以创建/编辑/删除关系
- [ ] AI 可以生成关系规划
- [ ] 章节正文生成时正确传递人物上下文
- [ ] 工作流步骤条正常工作

### 10.2 质量验收

- [ ] 后端测试覆盖核心逻辑
- [ ] 前端测试覆盖关键组件
- [ ] 数据库迁移可回滚
- [ ] 无现有效能退化

---

## 附录：Prompt 模板

### A. 人物生成 Prompt

```
你是一位资深的小说人物设计师。根据以下大纲信息，为小说设计 {count} 个人物。

## 大纲信息
标题：{title}
概述：{summary}
核心主题：{theme}

## 输出要求
为每个人物输出以下信息：
- 姓名
- 角色定位（主角/核心反派/重要配角/次要配角）
- 性格（用具体行为描述，避免抽象形容词）
- 口头禅
- 习惯动作
- 深层恐惧/弱点
- 核心动机
- 成长弧线
- 外貌描写
- 背景故事
- 标志性物品

请确保人物之间有潜在的关系张力，适合后续展开关系网络。
```

### B. 关系生成 Prompt

```
你是一位擅长编织人物关系的小说策划师。根据以下人物设定，设计人物之间的关系网络。

## 人物列表
{characters}

## 输出要求
为每对有关系的人物输出：
- 人物A、人物B
- 关系类型（信任/敌对/感情/亲情/竞争/中立）
- 方向（双向/单向）
- 当前状态
- 信任度（0-100）
- 关系描述
- 演变规划（3-5个关键转折点，标注大约在第几章发生）

确保关系网络有张力，能够推动情节发展。
```
