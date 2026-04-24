# v0.6.3 工作流状态架构重构设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan after reviewing this spec.

## 目标

将工作流状态从 Project 表分离到独立的 WorkflowState 表，解决以下技术债：
1. `stage` 字段命名不一致（数据库 vs LangGraph）
2. `review_mode` 和 `workflow_mode` 语义重叠
3. Legacy 代码未清理
4. 过时 TODO 注释

## 架构变更

### 数据库架构

**新建表：`workflow_states`**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | SERIAL | PK | 主键 |
| project_id | INTEGER | FK | 关联项目 |
| thread_id | VARCHAR(50) | 'main' | 工作流线程（支持多工作流） |
| stage | VARCHAR(30) | 'inspiration' | 工作流阶段 |
| workflow_mode | VARCHAR(20) | 'hybrid' | 工作流模式 |
| max_rewrite_count | INTEGER | 3 | 最大重写次数 |
| current_chapter | INTEGER | 1 | 当前章节 |
| waiting_for_confirmation | BOOLEAN | FALSE | 是否等待确认 |
| confirmation_type | VARCHAR(30) | NULL | 确认类型 |
| created_at | TIMESTAMP | NOW() | 创建时间 |
| updated_at | TIMESTAMP | NOW() | 更新时间 |

**约束：** `UNIQUE(project_id, thread_id)`

**Stage 值统一命名：**
- `inspiration` - 灵感收集
- `outline` - 大纲生成
- `chapter_outlines` - 章节大纲
- `writing` - 章节写作
- `review` - 审核
- `complete` - 完成

**修改表：`projects`**

删除字段：
- `stage`
- `review_mode`
- `workflow_mode`
- `max_rewrite_count`

保留字段：
- `id`, `user_id`, `name`
- `target_words`, `total_words`
- `created_at`, `updated_at`

### 后端架构

**新增 Model：** `backend/app/models/workflow_state.py`

```python
class WorkflowState(Base):
    __tablename__ = "workflow_states"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    thread_id = Column(String(50), default="main")
    stage = Column(String(30), default="inspiration")
    workflow_mode = Column(String(20), default="hybrid")
    max_rewrite_count = Column(Integer, default=3)
    current_chapter = Column(Integer, default=1)
    waiting_for_confirmation = Column(Boolean, default=False)
    confirmation_type = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project", back_populates="workflow_states")
```

**修改 Model：** `backend/app/models/project.py`

- 删除 `stage`, `review_mode`, `workflow_mode`, `max_rewrite_count` 字段
- 添加 `workflow_states = relationship("WorkflowState", back_populates="project", cascade="all, delete-orphan")`

**修改 API：**

| 文件 | 变更 |
|------|------|
| `api/workflow.py` | 从 `workflow_state` 获取状态，删除 stage 映射代码 |
| `api/projects.py` | 返回 `workflow_state` 关联数据 |
| `api/chapters.py` | 使用 `workflow_state.stage` |

**删除 Legacy 代码：**

| 文件 | 删除内容 |
|------|----------|
| `agents/nodes/chapter_generation.py` | `parse_chapter_outlines()`, `generate_chapter_outlines_node()` (legacy 版本) |
| `agents/nodes/chapter_generation.py` | 过时 TODO 注释 |

### 前端架构

**Stage 命名替换（22 处）：**

| 旧值 | 新值 |
|------|------|
| `inspiration_collecting` | `inspiration` |
| `outline_generating` | `outline` |
| `outline_confirming` | `outline` (合并) |
| `chapter_outlines_confirming` | `chapter_outlines` (合并) |
| `chapter_writing` | `writing` |
| `completed` | `complete` |

**修改文件：**

| 文件 | 变更 |
|------|------|
| `pages/ProjectDetail.tsx` | stage 命名替换 |
| `pages/Writing.tsx` | stage 命名替换 |
| `pages/Reading.tsx` | stage 命名替换 |
| `components/common/ProjectCard.tsx` | stage 命名替换 |
| `components/project/StepNavigation.tsx` | stage 命名替换 |
| `components/project/OutlineWorkflow.tsx` | stage 命名替换 |
| `types/index.ts` | 更新 WorkflowStage 类型 |

**API 响应调整：**

```typescript
// 旧结构
interface Project {
  id: number
  stage: string
  workflow_mode: string
  // ...
}

// 新结构
interface Project {
  id: number
  workflow_state?: WorkflowState
  // ...
}

interface WorkflowState {
  id: number
  project_id: number
  thread_id: string
  stage: WorkflowStage
  workflow_mode: WorkflowMode
  current_chapter: number
  waiting_for_confirmation: boolean
  confirmation_type: string | null
}
```

## 迁移策略

### Phase 1: 数据库迁移

**Alembic 迁移脚本：**

1. 创建 `workflow_states` 表
2. 从 `projects` 表迁移数据：
   - 每个 project 创建一条 workflow_state 记录
   - stage 值转换：`inspiration_collecting` → `inspiration` 等
   - workflow_mode 直接迁移
   - max_rewrite_count 直接迁移

### Phase 2: 后端更新

1. 创建 WorkflowState model
2. 修改 Project model
3. 更新所有 API 端点
4. 删除 legacy 代码和 TODO

### Phase 3: 前端更新

1. 更新类型定义
2. 机械替换 stage 命名
3. 更新 API 响应处理

### Phase 4: 清理

1. Alembic 迁移删除 projects 表的旧字段
2. 测试验证

## 测试策略

### 后端测试

- 测试 WorkflowState CRUD
- 测试 Project → WorkflowState 关联
- 测试 LangGraph 节点使用 WorkflowState
- 测试数据库迁移脚本

### 前端测试

- 测试 stage 显示正确
- 测试工作流状态 UI
- 测试 workflowStore 状态管理

### 集成测试

- 测试完整工作流运行
- 测试暂停/恢复功能
- 测试多工作流场景（thread_id 不同）

## 风险评估

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| 数据迁移失败 | 高 | 迁移前备份，迁移脚本先测试 |
| 前端遗漏替换 | 中 | 使用正则全局搜索替换 |
| API 兼容性 | 中 | 保持 API 响应结构向后兼容 |

## 版本规划

**v0.6.3** - 工作流状态架构重构
- 数据库架构变更
- 后端代码重构
- 前端命名统一
- Legacy 代码清理

## 成功标准

1. 所有测试通过
2. 工作流功能正常运行
3. 无 stage 映射转换代码
4. 无 review_mode 字段
5. 无 legacy 代码和过时 TODO
