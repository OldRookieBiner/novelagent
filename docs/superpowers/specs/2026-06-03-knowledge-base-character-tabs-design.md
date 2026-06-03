# 知识库角色板块标签页设计方案

## 背景

知识库原有「角色」板块仅展示角色信息和简单的关系列表，存在以下问题：
1. 关系数据（Relation）展示简单，仅作为角色页面底部的附庸
2. 关系演变数据（EvolutionPlan、EvolutionRecord）后端已有模型，但前端完全未展示
3. 关系演变数据未被写作节点消费，无法提升生文质量

## 目标

1. 将「角色」板块拆分为三个**标签页**（不是新增侧边栏），提升关系和演变数据的可见性
2. 让写作节点能够读取关系演变规划，在写章节前注入上下文
3. 写完章节后自动检测关系变化，生成演变记录并同步信任度

## 决策结果

| 问题 | 选项 | 决策 |
|------|------|------|
| 消费层：关系演变数据是否需要在写作时提供给 LLM？ | A: 不需要 / B: 需要 | **B** |
| 演变记录的来源 | A: 写完章节后自动生成 / B: 手动添加 | **A** |
| UI 方案 | A: 新增侧边栏导航项 / B: 角色板块内分标签页 | **B** |

## 设计方案

### UI 结构：知识库左侧导航 + 角色板块内标签页

```
知识库侧边栏（7项，不增加）:
├── 故事种子
├── 大纲
├── 世界观
├── 风格约束
├── 角色 ← 点击进入角色板块
├── 伏笔地图
└── 时间线

角色板块内容区（3个标签页）:
├── [角色设定] ─── 当前角色卡片列表（不变）
├── [关系网络] ─── 关系卡片列表
└── [关系演变] ─── 选择关系后展示规划+记录
```

### 标签页 1：角色设定（保持不变）

- 角色卡片列表，按主角/核心反派/重要配角/配角分组
- 每张卡片显示：姓名、性格、核心动机、成长弧线

### 标签页 2：关系网络

- 关系卡片列表，每行显示：
  - 角色A — 关系类型标签 — 角色B
  - 关系类型颜色：信任(绿)、敌对(红)、感情(粉)、合作(蓝)
  - 信任度数值 (0-100)、方向
  - 「编辑」「删除」按钮
- 右上角「+ 新增关系」按钮

### 标签页 3：关系演变

- 顶部 Pill 按钮关系选择器
- 演变规划表格（未来计划）：��节、事件、状态变化、信任度变化、状态标签
- 演变记录表格（已发生）：章节、事件、状态变化、信任度变化
- 右上角「+ 新增规划」按钮

## 后端架构

### API 验证（现有 API 已支持）

| 需求 | API | 状态 |
|------|-----|------|
| 角色列表 | GET /projects/{id}/characters | ✅ 已有 |
| 关系列表 | GET /projects/{id}/relations | ✅ 已有 |
| 关系详情（含人物信息） | GET /projects/{id}/relations/{id} | ✅ 已有 |
| 演变规划列表 | GET /projects/{id}/relations/{id}/evolution-plans | ✅ 已有 |
| 演变记录列表 | GET /projects/{id}/relations/{id}/evolution-records | ✅ 已有 |
| 新增演变规划 | POST /projects/{id}/relations/{id}/evolution-plans | ✅ 已有 |

### 消费层设计（LangGraph 节点）

#### 1. 上下文注入（写入前）

在 `context_assembly` 节点中：

```python
# 获取当前章节应该触发的关系演变规划
pending_plans = kb.get_evolution_plans_triggering_at(chapter_number)
if pending_plans:
    # 注入到 LLM 上下文
    context["relation_evolution_cues"] = [
        f"第{plan.trigger_chapter}章，{plan.relation.character_a.name}和{plan.relation.character_b.name}的关系将发生变化："
        f"{plan.status_before} → {plan.status_after}，信任度 {plan.trust_before} → {plan.trust_after}。"
        f"事件：{plan.event_description}"
        for plan in pending_plans
    ]
```

#### 2. 自动检测（写入后）

在 `post_write_summary` 节点中新增逻辑（或拆分为 `relation_evolution_tracker` 节点）：

```python
async def detect_and_record_evolution(kb, chapter_content, chapter_number, project_id):
    """检测本章是否发生人物关系变化，自动生成 EvolutionRecord"""
    
    # 1. 获取本章涉及的关系
    relations = kb.get_relations_in_chapter(chapter_content)
    
    for relation in relations:
        # 2. 调用 LLM 分析是否发生了关系变化
        changes = await analyze_evolution(chapter_content, relation)
        
        if changes["has_evolution"]:
            # 3. 创建 EvolutionRecord
            record = kb.create_evolution_record(
                relation_id=relation.id,
                chapter_number=chapter_number,
                content=changes["event"],
                status_change=changes["status_change"],
                trust_change=changes["trust_change"]
            )
            
            # 4. 标记对应的 EvolutionPlan 为已触发
            kb.mark_plan_triggered(relation.id, chapter_number)
            
            # 5. 同步更新 Relation 的 trust_level
            kb.update_relation_trust_level(relation.id, changes["new_trust_level"])
```

### LangGraph 工作流集成

```
WRITING 阶段节点顺序：
... → context_assembly → chapter_planning → chapter_writing → post_write_summary → ...
                              ↑                                         ↑
                              │                                         │
                              │         在 context_assembly 注入        │
                              │    pending_evolution_plans 到上下文      │
                              │                                         │
                              │         在 post_write_summary 检测      │
                              │    关系变化并创建 EvolutionRecord       │
```

### 关键约束

1. **信任度一致性**：每次创建 EvolutionRecord 后，必须同步更新 Relation.trust_level
2. **规划触发标记**：当 EvolutionPlan 被触发（章节达到 trigger_chapter），标记 is_triggered=True
3. **幂等性**：同一个章节只能触发一次演变检测，防止重复创建记录

## 实施范围

### 前端
- 修改 `KnowledgeTab.tsx` 中的 `CharactersView` 函数为标签页容器
- 新增：`CharactersListView.tsx`��`RelationsView.tsx`、`EvolutionView.tsx`
- **不需要修改 KnowledgeSection 类型**（不是新增侧边栏项）

### 后端展示层
- 无需新增 API

### 后端消费层
1. 修改 `knowledge_base.py`：新增 `get_evolution_plans_triggering_at`、`create_evolution_record`、`update_relation_trust_level`
2. 修改 `context_assembly.py` 或 `agent_context.py`：注入 pending_evolution_plans
3. 修改 `post_write_summary.py`：添加关系演变检测逻辑
