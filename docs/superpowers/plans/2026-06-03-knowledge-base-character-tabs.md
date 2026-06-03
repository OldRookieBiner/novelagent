# 知识库角色板块标签页实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将知识库「角色」板块拆分为三个**标签页**（角色设定/关系网络/关系演变），并在写作上下文注入关系演变规划，写完后自动检测并生成演变记录，同步更新信任度。

**Architecture:** 
- 前端：修改 KnowledgeTab.tsx，将 CharactersView 组件改造为标签页容器 + 三个子组件
- 后端展示层：无需新增 API（验证已有 API 覆盖全部需求）
- 后端消费层：在 context_assembly 注入规划上下文，在 post_write_summary 中检测变化并记录，同步 Relation.trust_level

**Tech Stack:** React + TypeScript (前端), LangGraph + SQLAlchemy (后端)

---

## 实施约束（LangGraph 规范）

1. **不新增独立节点**：关系演变检测逻辑直接集成到 `post_write_summary.py` 中，不创建新节点文件
2. **信任度同步**：每次创建 EvolutionRecord 后，必须同步更新 Relation.trust_level
3. **幂等检测**：使用数据库约束或业务逻辑确保同一章节不重复创建记录
4. **遵循现有模式**：使用项目中已有的节点命名、函数签名、错误处理模式

---

## 前置验证：API 覆盖检查

在开始前，验证前端可用的 API：

| 需求 | API | 文件位置 |
|------|-----|----------|
| 角色列表 | GET /projects/{id}/characters | backend/app/api/characters.py |
| 关系列表 | GET /projects/{id}/relations | backend/app/api/characters.py |
| 演变规划 | GET /projects/{id}/relations/{id}/evolution-plans | backend/app/api/characters.py |
| 演变记录 | GET /projects/{id}/relations/{id}/evolution-records | backend/app/api/characters.py |

---

## Task 1: 前端 — 将 CharactersView 改造为标签页容器

**Files:**
- Modify: `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx`
- Create: `frontend/src/components/workbench/knowledge/CharactersListView.tsx`
- Create: `frontend/src/components/workbench/knowledge/RelationsView.tsx`
- Create: `frontend/src/components/workbench/knowledge/EvolutionView.tsx`

- [ ] **Step 1: 分析当前 KnowledgeTab.tsx 中 CharactersView 实现**

运行: 读取 `KnowledgeTab.tsx`，���到 `CharactersView` 组件定义，理解当前渲染逻辑

- [ ] **Step 2: 确认现有 API 客户端**

检查: `frontend/src/lib/characterApi.ts` 中是否已有 `listRelations()`、`listEvolutionPlans()`、`listEvolutionRecords()` 方法

- [ ] **Step 3: 创建 CharactersListView.tsx（角色设定标签页）**

从现有 CharactersView 中提取角色卡片逻辑，保持不变：
```typescript
// 从现有代码提取，保持分组逻辑：主角/反派/配角
// 返回 JSX
```

- [ ] **Step 4: 创建 RelationsView.tsx（关系网络标签页）**

从现有 CharactersView 底部关系列表提取：
```typescript
// 调用 characterApi.listRelations(projectId)
// 渲染关系卡片：角色A — 类型标签 — 角色B + 信任度 + 编辑/删除
// 「+ 新增关系」按钮调用 RelationFormDialog
```

- [ ] **Step 5: 创建 EvolutionView.tsx（关系演变标签页）**

```typescript
// 1. 使用 useState 管理选中的 relationId
// 2. 调用 characterApi.listRelations() 获取所有关系（用于选择器）
// 3. 根据选中关系调用：
//    - characterApi.listEvolutionPlans(relationId)
//    - characterApi.listEvolutionRecords(relationId)
// 4. 渲染两个表格
// 5. 「+ 新增规划」调用新增规划的表单对话框
```

- [ ] **Step 6: 修改 KnowledgeTab.tsx 改造 CharactersView 为标签页容器**

```typescript
// 替换 CharactersView 调用为：
function CharactersViewWrapper({ data, relations, loading, projectId }: Props) {
  const [activeTab, setActiveTab] = useState<'characters' | 'relations' | 'evolution'>('characters')
  
  return (
    <div>
      {/* 标签页栏 */}
      <div className="flex border-b mb-4">
        <button onClick={() => setActiveTab('characters')} 
          className={activeTab === 'characters' ? 'border-b-2 border-blue-600' : ''}>
          角色设定
        </button>
        <button onClick={() => setActiveTab('relations')}
          className={activeTab === 'relations' ? 'border-b-2 border-blue-600' : ''}>
          关系网络
        </button>
        <button onClick={() => setActiveTab('evolution')}
          className={activeTab === 'evolution' ? 'border-b-2 border-blue-600' : ''}>
          关系演变
        </button>
      </div>
      
      {/* 标签页内容 */}
      <div>
        {activeTab === 'characters' && <CharactersListView data={data} loading={loading} />}
        {activeTab === 'relations' && <RelationsView relations={relations} loading={loading} projectId={projectId} />}
        {activeTab === 'evolution' && <EvolutionView relations={relations} projectId={projectId} />}
      </div>
    </div>
  )
}
```

- [ ] **Step 7: 测试前端**

运行: `cd /Users/biner/Dev/novelagent/frontend && npm run dev`
验证: 访问知识库 → 角色，三个标签页切换正常

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/workbench/knowledge/
git commit -m "feat(frontend): 将角色板块改造为三个标签页"
```

---

## Task 2: 后端 — 在写作上下文注入关系演变规划

**Files:**
- Modify: `backend/app/agents/services/knowledge_base.py`
- Modify: `backend/app/agents/agent_context.py`
- Test: `backend/tests/test_agent_context.py`

- [ ] **Step 1: 在 KnowledgeBaseService 添加获取演变规划方法**

在 `knowledge_base.py` 的 KnowledgeBaseService 类中添加：

```python
def get_evolution_plans_triggering_at(self, chapter_number: int) -> list[EvolutionPlan]:
    """获取在指定章节触发的关系演变规划（未触发且trigger_chapter <= chapter_number）"""
    from app.models.character import EvolutionPlan as EvolutionPlanModel
    
    plans = (
        self.db.query(EvolutionPlanModel)
        .filter(
            EvolutionPlanModel.relation.has(project_id=self.project_id),
            EvolutionPlanModel.trigger_chapter <= chapter_number,
            EvolutionPlanModel.is_triggered == False
        )
        .all()
    )
    return plans
```

- [ ] **Step 2: 修改 agent_context.py 的 _load_writing_context 函数**

在 `_load_writing_context` 函数中添加：

```python
# 获取当前章节触发的关系演变规划
if current_chapter_number:
    pending_plans = kb.get_evolution_plans_triggering_at(current_chapter_number)
    if pending_plans:
        evolution_cues = []
        for plan in pending_plans:
            char_a = plan.relation.character_a.name
            char_b = plan.relation.character_b.name
            cue = (
                f"第{plan.trigger_chapter}章，{char_a}和{char_b}的关系将发生变化："
                f"{plan.status_before or '待定'} → {plan.status_after}，"
                f"信任度 {plan.trust_before or 50} → {plan.trust_after or 50}。"
                f"事件：{plan.event_description}"
            )
            evolution_cues.append(cue)
        context["relation_evolution_cues"] = evolution_cues
```

- [ ] **Step 3: 验证现有 LLM prompt 是否需要扩展**

检查: `prompts.py` 或 `chapter_writing.py` 中是否有注入 relation_evolution_cues 的提示词模板

- [ ] **Step 4: 编写测试**

创建/更新 `backend/tests/test_agent_context.py`:

```python
def test_writing_context_includes_evolution_plans(db_session, sample_project):
    """验证写作上下文包含关系演变规划"""
    # 准备：创建角色、关系、演变规划（第5章触发）
    create_characters_and_relation_with_plan(db_session, sample_project, trigger_chapter=5)
    
    # 执行：build_agent_context with current_chapter_number=5
    context = build_agent_context(
        project_id=sample_project.id,
        phase=Phase.WRITING.value,
        current_chapter_number=5
    )
    
    # 验证：context["relation_evolution_cues"] 包含规划信息
    assert "relation_evolution_cues" in context
    assert len(context["relation_evolution_cues"]) == 1
    assert "林默" in context["relation_evolution_cues"][0]
```

- [ ] **Step 5: 运行测试**

运行: `docker exec novelagent-backend-1 pytest backend/tests/test_agent_context.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/agent_context.py backend/app/agents/services/knowledge_base.py backend/tests/
git commit -m "feat(backend): 在写作上下文注入关系演变规划"
```

---

## Task 3: 后端 — 自动检测并生成演变记录，同步信任度

**Files:**
- Modify: `backend/app/agents/services/knowledge_base.py`
- Modify: `backend/app/agents/nodes/post_write_summary.py`
- Test: `backend/tests/test_relation_evolution.py`

- [ ] **Step 1: 在 KnowledgeBaseService 添加信任度更新方法**

```python
def update_relation_trust_level(self, relation_id: int, new_trust_level: int) -> Relation:
    """更新关系的信任度"""
    from app.models.character import Relation as RelationModel
    
    relation = (
        self.db.query(RelationModel)
        .filter(RelationModel.id == relation_id)
        .first()
    )
    if relation:
        relation.trust_level = max(0, min(100, new_trust_level))
        self.db.commit()
        self.db.refresh(relation)
    return relation

def mark_evolution_plan_triggered(self, relation_id: int, chapter_number: int) -> list[EvolutionPlan]:
    """标记指定章节的演变规划为已触发"""
    from app.models.character import EvolutionPlan as EvolutionPlanModel
    
    plans = (
        self.db.query(EvolutionPlanModel)
        .filter(
            EvolutionPlanModel.relation_id == relation_id,
            EvolutionPlanModel.trigger_chapter == chapter_number,
            EvolutionPlanModel.is_triggered == False
        )
        .all()
    )
    for plan in plans:
        plan.is_triggered = True
    self.db.commit()
    return plans
```

- [ ] **Step 2: 在 post_write_summary.py 添加关系演变检测逻辑**

在 `post_write_summary_node` 函数末尾添加：

```python
async def detect_and_record_evolution(
    kb: KnowledgeBaseService,
    chapter_content: str,
    chapter_number: int,
    project_id: int
):
    """检测本章是否发生人物关系变化，自动生成 EvolutionRecord"""
    
    # 1. 获取本章涉及的角色
    characters_in_chapter = extract_characters_from_content(chapter_content)
    if not characters_in_chapter:
        return
    
    # 2. 获取这些角色涉及的所有关系
    relations = kb.get_relations_involved_characters(characters_in_chapter)
    
    # 3. 对每个关系调用 LLM 分析是否发生了关系变化
    for relation in relations:
        changes = await analyze_relation_evolution(
            chapter_content,
            relation,
            kb
        )
        
        if changes.get("has_evolution"):
            # 4. 创建 EvolutionRecord
            record = kb.create_evolution_record(
                relation_id=relation.id,
                chapter_number=chapter_number,
                content=changes["event"],
                status_change=changes.get("status_change"),
                trust_change=changes.get("trust_change")
            )
            
            # 5. 标记对应的 EvolutionPlan 为已触发
            kb.mark_evolution_plan_triggered(relation.id, chapter_number)
            
            # 6. 同步更新 Relation 的 trust_level
            new_trust = changes.get("new_trust_level", relation.trust_level)
            kb.update_relation_trust_level(relation.id, new_trust)


async def analyze_relation_evolution(
    chapter_content: str,
    relation,
    kb: KnowledgeBaseService
) -> dict:
    """调用 LLM 分析章节内容是否导致关系变化"""
    # 构建 prompt 调用 LLM
    # 返回: {has_evolution: bool, event: str, status_change: str, trust_change: int, new_trust_level: int}
    pass
```

- [ ] **Step 3: 在 post_write_summary_node 中调用检测逻辑**

在函数末尾（章节内容已写入后）添加调用：

```python
# 在返回 state 之前
await detect_and_record_evolution(
    kb=kb,
    chapter_content=chapter.get("content", ""),
    chapter_number=current_chapter,
    project_id=state["project_id"]
)
```

- [ ] **Step 4: 添加幂等检查**

在 `create_evolution_record` 中添加检查：

```python
def create_evolution_record(self, relation_id: int, chapter_number: int, **kwargs) -> EvolutionRecord:
    """创建演变记录，幂等检查：同一章节同一关系只创建一条"""
    from app.models.character import EvolutionRecord as EvolutionRecordModel
    
    existing = (
        self.db.query(EvolutionRecordModel)
        .filter(
            EvolutionRecordModel.relation_id == relation_id,
            EvolutionRecordModel.chapter_number == chapter_number
        )
        .first()
    )
    if existing:
        return existing  # 已存在，返回现有记录
    
    record = EvolutionRecordModel(
        relation_id=relation_id,
        chapter_number=chapter_number,
        **kwargs
    )
    self.db.add(record)
    self.db.commit()
    self.db.refresh(record)
    return record
```

- [ ] **Step 5: 编写测试**

创建 `backend/tests/test_relation_evolution.py`:

```python
@pytest.mark.asyncio
async def test_detect_trust_level_change_and_sync(db_session, sample_project):
    """验证关系演变检测和信任度同步"""
    # 准备：创建角色、关系（信任度 72）
    relation = create_relation(db_session, sample_project, trust_level=72)
    
    # 模拟章节内容：林默发现苏寒欺骗了他，信任崩塌
    chapter_content = "林默难以置信地看着苏寒，原来一切都是骗局..."
    
    # 执行：detect_and_record_evolution
    await detect_and_record_evolution(
        kb=KnowledgeBaseService(sample_project.id),
        chapter_content=chapter_content,
        chapter_number=5,
        project_id=sample_project.id
    )
    
    # 验证：创建了 EvolutionRecord，trust_level 已更新
    record = db_session.query(EvolutionRecord).filter(
        EvolutionRecord.relation_id == relation.id,
        EvolutionRecord.chapter_number == 5
    ).first()
    assert record is not None
    assert record.trust_change == -27
    
    # 验证信任度已同步
    db_session.refresh(relation)
    assert relation.trust_level == 45
```

- [ ] **Step 6: 运行测试**

运行: `docker exec novelagent-backend-1 pytest backend/tests/test_relation_evolution.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/services/knowledge_base.py backend/app/agents/nodes/post_write_summary.py backend/tests/
git commit -m "feat(backend): 自动检测关系变化并生成演变记录，同步信任度"
```

---

## Task 4: 端到端验证

- [ ] **Step 1: 启动服务**

```bash
cd /Users/biner/Dev/novelagent && docker compose up -d
```

- [ ] **Step 2: 通过 API 创建测试数据**

```bash
# 1. 创建项目
curl -X POST http://localhost:8000/api/projects -H "Content-Type: application/json" \
  -d '{"name": "测试项目", "user_id": 1}'

# 2. 创建角色：林默（主角）、苏寒（反派）
# 3. 创建关系：林默-苏寒，信任，信任度 72
# 4. 创建演变规划：第 5 章信任度降至 45
```

- [ ] **Step 3: 验证前端标签页**

访问 http://localhost:3001 → 项目 → 知识库 → 角色
- 标签页 1：显示角色
- 标签页 2：显示关系
- 标签页 3：选择关系，显示演变规划

- [ ] **Step 4: 触发工作流写第 5 章**

调用工作流 API 写第 5 章

- [ ] **Step 5: 验证演变记录自动生成**

```bash
# 检查 EvolutionRecord 是否创建
curl http://localhost:8000/api/projects/1/relations/1/evolution-records

# 检查 Relation trust_level 是否已更新
curl http://localhost:8000/api/projects/1/relations/1
```

- [ ] **Step 6: 最终 Commit**

```bash
git add .
git commit -m "feat: 完成知识库角色板块标签页及关系演变消费层"
```
