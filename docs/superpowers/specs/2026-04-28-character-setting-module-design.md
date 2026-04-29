# 人物设定模块设计文档

## 概述

**版本**: v0.7.0
**日期**: 2026-04-28
**分支**: feature/character-setting-module

### 目标

1. 新增独立的人物设定功能模块，解决当前人物设定嵌入大纲导致内容单薄的问题
2. 新增人物关系规划与追溯功能，提升长篇写作的人物一致性
3. 优化上下文传递机制，按篇幅差异化传递内容

### 篇幅划分

| 篇幅 | 目标字数范围 | 预估章节数 |
|------|-------------|-----------|
| 短篇 | 1万 - 3万字 | 3-25章 |
| 中篇 | 3万 - 15万字 | 25-75章 |
| 长篇 | 15万 - 100万字 | 75-250章 |
| 超长篇 | 100万字以上 | 250章以上 |

**一期实现范围**: 短篇（中长篇预留接口）

---

## 功能设计

### 1. 人物设定模块

#### 1.1 人物字段设计

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 姓名 |
| role | string | ✅ | 角色定位（主角/核心反派/重要配角/配角） |
| personality | text | ❌ | 性格描述 |
| catchphrase | string | ❌ | 口头禅 |
| habit_action | string | ❌ | 习惯动作 |
| deep_fear | text | ❌ | 深层恐惧/弱点 |
| core_motivation | text | ❌ | 核心动机 |
| growth_arc | text | ❌ | 成长弧线 |
| appearance | text | ❌ | 外貌描写 |
| backstory | text | ❌ | 背景故事 |
| signature_item | text | ❌ | 标志性物品/装备 |

#### 1.2 人物生成方式

**混合模式**:
- 用户可手动填写表单
- 用户可请求 AI 生成/优化某个人物
- 用户可请求 AI 批量生成人物

#### 1.3 AI 生成人物 Prompt 要点

- 根据大纲初稿和灵感信息生成人物
- 确保人物与故事主题、世界观契合
- 人物设定需包含完整的性格、动机、成长弧线

### 2. 人物关系模块

#### 2.1 关系字段设计

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| character_a_id | int | ✅ | 人物A ID |
| character_b_id | int | ✅ | 人物B ID |
| relation_type | string | ✅ | 关系类型（信任/敌对/感情/合作/利用/陌生） |
| direction | string | ✅ | 方向（双向/单向A→B/单向B→A） |
| current_status | string | ✅ | 当前状态描述 |
| trust_level | int | ✅ | 信任度 0-100 |

#### 2.2 关系演变规划字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| relation_id | int | ✅ | 关联关系 ID |
| trigger_chapter | int | ✅ | 触发章节（大约） |
| event_description | text | ✅ | 事件描述 |
| status_before | string | ✅ | 变化前状态 |
| status_after | string | ✅ | 变化后状态 |
| trust_before | int | ✅ | 变化前信任度 |
| trust_after | int | ✅ | 变化后信任度 |
| is_triggered | bool | ❌ | 是否已触发（默认 false） |

#### 2.3 关系追溯记录字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| relation_id | int | ✅ | 关联关系 ID |
| chapter_number | int | ✅ | 章节号 |
| content | text | ✅ | 发生了什么 |
| status_change | string | ❌ | 状态变化 |
| trust_change | int | ❌ | 信任度变化 |
| triggered_plan_id | int | ❌ | 触发的规划节点 ID |

### 3. 工作流调整

#### 3.1 新工作流

```
灵感收集 → 大纲初稿 → AI生成人物 → 人工审核人物 → AI生成关系规划 → 人工审核关系 → 大纲完善 → 章节大纲 → 章节正文 → 审核
```

#### 3.2 LangGraph 新增节点

| 节点 | 说明 |
|------|------|
| generate_characters_node | 根据大纲初稿生成人物 |
| generate_relations_node | 根据人物生成关系规划 |
| refine_outline_node | 根据人物完善大纲 |
| extract_evolution_node | 写作后自动提取关系变化 |

#### 3.3 工作流阶段新增

```python
# 新增阶段常量
STAGE_CHARACTERS = "characters"        # 人物设定
STAGE_RELATIONS = "relations"          # 关系规划
```

### 4. 上下文传递机制

#### 4.1 NovelState 新增字段

```python
class NovelState(TypedDict):
    # ... 现有字段

    # 新增人物相关
    characters: list[dict]              # 全部人物设定
    relations: list[dict]               # 全部关系
    evolution_plans: list[dict]         # 关系演变规划
    evolution_records: list[dict]       # 关系演变追溯

    # 篇幅信息
    novel_length: str                   # short/medium/long/extra_long
```

#### 4.2 短篇上下文传递内容

章节正文生成时传递：
- 当前章节大纲（完整）
- 已写章节正文（全部，短篇最多25章）
- 小说大纲（标题、概述、情节节点）
- **完整人物设定**（全部字段）
- **关系列表**（当前状态）
- **当前关系演变节点**（附近章节的规划）
- 世界观设定
- 风格偏好

#### 4.3 中长篇预留（二期）

- 中篇：传递最近 10-15 章正文 + 关系摘要
- 长篇：需要 RAG 检索相关人物和关系

---

## 数据库设计

### 新增表

#### characters 表

```sql
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    personality TEXT,
    catchphrase VARCHAR(200),
    habit_action VARCHAR(200),
    deep_fear TEXT,
    core_motivation TEXT,
    growth_arc TEXT,
    appearance TEXT,
    backstory TEXT,
    signature_item TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_characters_project ON characters(project_id);
```

#### relations 表

```sql
CREATE TABLE relations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    character_a_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    character_b_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL DEFAULT '双向',
    current_status TEXT,
    trust_level INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_a_id, character_b_id)
);

CREATE INDEX idx_relations_project ON relations(project_id);
CREATE INDEX idx_relations_character_a ON relations(character_a_id);
CREATE INDEX idx_relations_character_b ON relations(character_b_id);
```

#### evolution_plans 表

```sql
CREATE TABLE evolution_plans (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
    trigger_chapter INTEGER NOT NULL,
    event_description TEXT NOT NULL,
    status_before TEXT,
    status_after TEXT NOT NULL,
    trust_before INTEGER,
    trust_after INTEGER,
    is_triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evolution_plans_relation ON evolution_plans(relation_id);
CREATE INDEX idx_evolution_plans_chapter ON evolution_plans(trigger_chapter);
```

#### evolution_records 表

```sql
CREATE TABLE evolution_records (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    status_change TEXT,
    trust_change INTEGER,
    triggered_plan_id INTEGER REFERENCES evolution_plans(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evolution_records_relation ON evolution_records(relation_id);
CREATE INDEX idx_evolution_records_chapter ON evolution_records(chapter_number);
```

### 修改表

#### projects 表

```sql
ALTER TABLE projects ADD COLUMN novel_length VARCHAR(20) DEFAULT 'short';
```

---

## API 设计

### 新增 API 端点

#### 人物 API

```
GET    /api/projects/{id}/characters           # 获取人物列表
POST   /api/projects/{id}/characters           # 创建人物
GET    /api/projects/{id}/characters/{charId}  # 获取人物详情
PUT    /api/projects/{id}/characters/{charId}  # 更新人物
DELETE /api/projects/{id}/characters/{charId}  # 删除人物
POST   /api/projects/{id}/characters/generate  # AI 批量生成人物
POST   /api/projects/{id}/characters/{charId}/optimize  # AI 优化单个人物
```

#### 关系 API

```
GET    /api/projects/{id}/relations           # 获取关系列表
POST   /api/projects/{id}/relations           # 创建关系
PUT    /api/projects/{id}/relations/{relId}   # 更新关系
DELETE /api/projects/{id}/relations/{relId}   # 删除关系
POST   /api/projects/{id}/relations/generate  # AI 生成关系规划
```

#### 演变 API

```
GET    /api/projects/{id}/relations/{relId}/evolution/plans   # 获取演变规划
POST   /api/projects/{id}/relations/{relId}/evolution/plans   # 创建演变规划
PUT    /api/projects/{id}/evolution/plans/{planId}            # 更新演变规划
DELETE /api/projects/{id}/evolution/plans/{planId}            # 删除演变规划

GET    /api/projects/{id}/relations/{relId}/evolution/records # 获取演变记录
```

---

## 前端设计

### 页面结构

**人物设定页面** (一个页面完成所有操作):
- 人物卡片列表
- 人物详情编辑侧边栏
- 关系列表（嵌套在人物页面）
- 关系演变详情（模态框或侧边栏）

### 新增路由

```typescript
/project/:id/characters  // 人物设定页面
```

### 步骤导航调整

```typescript
const STEPS = [
  { key: 'inspiration', label: '灵感采集' },
  { key: 'outline', label: '大纲' },
  { key: 'characters', label: '人物设定' },  // 新增
  { key: 'relations', label: '关系规划' },   // 新增
  { key: 'chapter_outlines', label: '章节大纲' },
  { key: 'writing', label: '写作' },
]
```

---

## 实现优先级

### 一期（必须完成）

1. 数据库表创建与迁移
2. 后端 API 实现
3. LangGraph 节点调整
4. 前端人物设定页面
5. 前端关系规划页面
6. 上下文传递逻辑
7. 短篇篇幅支持

### 二期（可选）

1. 中长篇上下文传递优化
2. RAG 检索支持
3. 图形化关系图谱

---

## 风险与注意事项

1. **分支开发**: 所有代码在 `feature/character-setting-module` 分支，未经允许不提交到主干
2. **向后兼容**: 现有项目不受影响，新功能为可选
3. **技术债控制**: 复用现有 LangGraph 结构，不引入新的状态管理
4. **数据迁移**: 需提供迁移脚本，现有 Outline 中的 characters 数据可迁移到新表
