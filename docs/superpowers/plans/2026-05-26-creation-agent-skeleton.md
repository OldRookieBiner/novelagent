# 创作智能体骨架 — 实施计划（阶段1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 Agent 层和数据模型，跑通从创意对话到逐章写作的最小闭环

**Architecture:** 删除旧 `agents/` 目录中除 checkpointer/sse_events/token_budget/context_strategy/constants 外的全部文件，从零重写 LangGraph 工作流。新增 9 个数据模型支撑 novelskills 写作方法论。前端重写工作台布局（三栏+标签页+底栏）。不兼容旧项目数据。

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / LangGraph / React 18 / Vite / shadcn/ui / Zustand / SSE

---

## 文件结构

### 后端保留文件（不改或小改）

- `backend/app/agents/constants.py` — 保留，扩展温度配置
- `backend/app/agents/checkpointer.py` — 保留
- `backend/app/agents/sse_events.py` — 保留，扩展事件类型
- `backend/app/agents/token_budget.py` — 保留
- `backend/app/agents/context_strategy.py` — 保留，后续阶段改造
- `backend/app/agents/nodes/utils.py` — 保留，扩展工具函数

### 后端删除文件

- `backend/app/agents/graph.py` — 重写
- `backend/app/agents/state.py` — 重写
- `backend/app/agents/prompts.py` — 重写
- `backend/app/agents/agent_graph.py` — 删除（阶段2重建）
- `backend/app/agents/agent_tools.py` — 删除（阶段2重建）
- `backend/app/agents/agent_context.py` — 删除（阶段2重建）
- `backend/app/agents/tool_context.py` — 删除（阶段2重建）
- `backend/app/agents/nodes/outline_generation.py` — 重写
- `backend/app/agents/nodes/chapter_generation.py` — 重写
- `backend/app/agents/nodes/review.py` — 重写
- `backend/app/agents/nodes/rewrite.py` — 重写
- `backend/app/agents/nodes/character_generation.py` — 重写
- `backend/app/agents/nodes/relation_generation.py` — 重写
- `backend/app/agents/nodes/volume_arc_planning.py` — 重写
- `backend/app/agents/nodes/arc_outline_generation.py` — 重写
- `backend/app/agents/nodes/chapter_summary.py` — 重写
- `backend/app/agents/nodes/wait_confirm.py` — 重写

### 后端新建文件

```
backend/app/
├── models/
│   ├── world_setting.py          # 世界观模型
│   ├── style_constraints.py      # 风格约束模型
│   ├── plot_structure.py         # PlotBlock + PlotQuestion + Subplot
│   ├── foreshadowing.py          # 伏笔追踪模型
│   ├── timeline.py               # 时间线条目模型
│   ├── style_snapshot.py         # 风格统计快照
│   └── scene_entry.py            # 场景清单模型
├── agents/
│   ├── nodes/
│   │   ├── inspiration_dialogue.py   # 对话式创意孵化
│   │   ├── story_seed.py             # 故事种子生成
│   │   ├── world_setting.py          # 世界观生成
│   │   ├── style_setup.py            # 风格约束设定
│   │   ├── foreshadowing_plan.py     # 伏笔-回收地图规划
│   │   ├── question_chain.py         # 问题链设计
│   │   ├── plot_blocks.py            # 情节块展开
│   │   ├── subplot_network.py        # 支线网络
│   │   ├── rhythm_curve.py           # 预期节奏曲线
│   │   ├── chapter_count_estimate.py # 章节数估算
│   │   ├── context_assembly.py       # 上下文组装（感知）
│   │   ├── chapter_planning.py       # 章节点（决策）
│   │   ├── chapter_writing.py        # 正文生成（执行）
│   │   ├── post_write_update.py      # 写后自检（13项子任务）
│   │   ├── deep_review.py            # 深度审查（每5章）
│   │   ├── structural_review.py      # 结构完整性检查
│   │   ├── character_arc_review.py   # 角色弧与风格一致性
│   │   └── final_polish.py           # 最终润色
│   └── services/
│       └── knowledge_base.py         # 知识库读写服务
├── api/
│   └── knowledge.py                  # 知识库 API
└── schemas/
    └── knowledge.py                  # 知识库 Pydantic schemas
```

### 前端新建/重写文件

```
frontend/src/
├── components/workbench/
│   ├── WorkbenchLayout.tsx      # 重写：三栏+标签页+底栏
│   ├── TabNavigation.tsx        # 重写：4个标签页
│   ├── ChapterListPanel.tsx     # 新建：左栏章节列表
│   ├── AgentChatPanel.tsx       # 新建：右栏智能体对话
│   ├── ProgressDashboard.tsx    # 新建：底栏进度仪表盘
│   ├── creation/
│   │   ├── ChapterNodePanel.tsx # 新建：章节点确认
│   │   ├── InspirationChat.tsx  # 新建：创意对话区
│   │   └── WritingPanel.tsx     # 改造：增加章节点
│   ├── knowledge/
│   │   ├── KnowledgeTab.tsx     # 新建
│   │   └── WorldSettingView.tsx # 新建
│   ├── structure/
│   │   └── StructureTab.tsx     # 新建
│   └── tracking/
│       └── TrackingTab.tsx      # 新建
└── stores/
    └── workbenchStore.ts        # 重写
```

---

## Task 1: 数据模型 — 核心追踪模型

**Files:**
- Create: `backend/app/models/world_setting.py`
- Create: `backend/app/models/style_constraints.py`
- Create: `backend/app/models/plot_structure.py`
- Create: `backend/app/models/foreshadowing.py`
- Create: `backend/app/models/timeline.py`
- Create: `backend/app/models/style_snapshot.py`
- Create: `backend/app/models/scene_entry.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/project.py`

- [ ] **Step 1:** 创建 `world_setting.py`

WorldSetting: project_id (FK, unique), core_concept (Text), tiered_settings (JSON: {red: [...], yellow: [...], green: [...]}), key_locations (JSON)

- [ ] **Step 2:** 创建 `style_constraints.py`

StyleConstraints: project_id (FK, unique), taboo_words (JSON), forbidden_patterns (JSON), style_anchor (Text, nullable), abstract_rules (JSON)

- [ ] **Step 3:** 创建 `plot_structure.py`

PlotBlock: project_id (FK), title (String), questions_to_answer (JSON), questions_to_raise (JSON), must_happen (JSON), expected_mood (String), chapter_start (Integer), chapter_end (Integer, nullable), completion_summary (Text, nullable)

PlotQuestion: project_id (FK), plot_block_id (FK, nullable), question_text (Text), status (String: pending/answered/closed), raised_in_chapter (Integer), answered_in_chapter (Integer, nullable)

Subplot: project_id (FK), name (String), characters (JSON), current_status (String), raised_in_chapter (Integer), planned_intersection_chapter (Integer, nullable), expected_resolution_chapter (Integer, nullable)

- [ ] **Step 4:** 创建 `foreshadowing.py`

Foreshadowing: project_id (FK), content (Text), level (String: hint/strengthened/revealed), appearance_count (Integer, default=1), status (String: active/pending_reclaim/reclaimed), planted_chapter (Integer), expected_resolve_chapter (Integer, nullable), resolved_chapter (Integer, nullable), related_characters (JSON)

- [ ] **Step 5:** 创建 `timeline.py`

TimelineEntry: project_id (FK), chapter_number (Integer), summary (Text), causal_chain (Text), rhythm_score (Integer), tension_score (Integer), emotion_score (Integer), emotion_tag (String)

- [ ] **Step 6:** 创建 `style_snapshot.py`

StyleSnapshot: project_id (FK), chapter_number (Integer), paragraph_count (Integer), avg_paragraph_length (Float), dialogue_ratio (Float), avg_sentence_length (Float)

- [ ] **Step 7:** 创建 `scene_entry.py`

SceneEntry: project_id (FK), chapter_number (Integer), scene_description (Text), characters_present (JSON)

- [ ] **Step 8:** 更新 `__init__.py` 导入所有新模型，更新 `project.py` 添加 relationships

- [ ] **Step 9:** 生成 Alembic 迁移并验证

Run: `docker exec novelagent-backend-1 alembic revision --autogenerate -m "add creation agent models"`
Run: `docker exec novelagent-backend-1 alembic upgrade head`

- [ ] **Step 10:** 提交

```bash
git add backend/app/models/
git commit -m "feat(models): add creation agent tracking models"
```

---

## Task 2: NovelState 重写

**Files:**
- Rewrite: `backend/app/agents/state.py`

- [ ] **Step 1:** 重写 NovelState

核心变化：
- 阶段控制从旧 stage 枚举改为 phase（incubation/structure/writing/revision）
- 新增 story_seed, inspiration_messages, plot_blocks, plot_questions, subplots
- 新增 post_write_results, last_review_chapter
- confirmation_type 扩展为支持 inspiration_dialogue/story_seed/outline/world_setting/characters/relations/style/foreshadowing_plan/structure/chapter_node/review_failed
- 保留 replace_or_append_chapters reducer
- 删除旧的 collected_info, outline_emotional_curve, arcs, review_mode 等管道式字段

- [ ] **Step 2:** 提交

---

## Task 3: Prompt 模板重写

**Files:**
- Rewrite: `backend/app/agents/prompts.py`

- [ ] **Step 1:** 重写所有 prompt 模板

15 个核心模板：
1. INSPIRATION_DIALOGUE_PROMPT — 创意对话
2. STORY_SEED_PROMPT — 故事种子
3. OUTLINE_GENERATION_PROMPT — 大纲生成（保留现有核心，增加伏笔地图）
4. WORLD_SETTING_PROMPT — 世界观（🔴🟡🟢分级）
5. CHARACTER_GENERATION_PROMPT — 角色（增加知识边界/对话样本）
6. STYLE_SETUP_PROMPT — 风格约束
7. FORESHADOWING_PLAN_PROMPT — 伏笔-回收地图
8. QUESTION_CHAIN_PROMPT — 问题链设计
9. PLOT_BLOCKS_PROMPT — 情节块展开
10. CHAPTER_PLANNING_PROMPT — 章节点
11. CHAPTER_WRITING_PROMPT — 正文生成
12. POST_WRITE_CHECK_PROMPT — 写后自检
13. DEEP_REVIEW_PROMPT — 深度审查
14. STRUCTURAL_REVIEW_PROMPT — 结构完整性
15. CHARACTER_ARC_REVIEW_PROMPT — 角色弧与风格

每个模板使用 `{variable}` 占位符，由节点运行时填充。

- [ ] **Step 2:** 提交

---

## Task 4: 知识库服务层

**Files:**
- Create: `backend/app/agents/services/knowledge_base.py`

- [ ] **Step 1:** 实现 KnowledgeBaseService

核心方法：
- 读取：get_world_setting, get_characters, get_relations, get_style_constraints, get_plot_blocks, get_foreshadowings(status), get_timeline(chapter_range), get_style_snapshots(last_n)
- 写入：create_world_setting, update_world_setting, create_character, create_style_constraints, create_plot_block, create_foreshadowing, update_foreshadowing, create_timeline_entry, create_style_snapshot, create_scene_entry
- 查询：get_pending_foreshadowings, get_overdue_foreshadowings(current_chapter), get_questions_for_chapter, get_current_plot_block(chapter_number)

构造函数接收 db: Session + project_id: int

- [ ] **Step 2:** 提交

---

## Task 5: 创意孵化节点组（8个节点）

**Files:**
- Create: `backend/app/agents/nodes/inspiration_dialogue.py`
- Create: `backend/app/agents/nodes/story_seed.py`
- Create: `backend/app/agents/nodes/world_setting.py`
- Create: `backend/app/agents/nodes/style_setup.py`
- Create: `backend/app/agents/nodes/foreshadowing_plan.py`
- Rewrite: `backend/app/agents/nodes/outline_generation.py`
- Rewrite: `backend/app/agents/nodes/character_generation.py`
- Rewrite: `backend/app/agents/nodes/relation_generation.py`

- [ ] **Step 1:** inspiration_dialogue_node — 多轮对话节点，设置 waiting_for_confirmation=True

- [ ] **Step 2:** story_seed_node — 生成故事种子

- [ ] **Step 3:** outline_generation_node — 重写，增加伏笔地图输出

- [ ] **Step 4:** world_setting_node — 生成🔴🟡🟢分级世界观

- [ ] **Step 5:** character_generation_node — 重写，增加知识边界/对话样本

- [ ] **Step 6:** relation_generation_node — 重写，适配新 state

- [ ] **Step 7:** style_setup_node — 生成风格约束

- [ ] **Step 8:** foreshadowing_plan_node — 规划伏笔-回收地图

- [ ] **Step 9:** 提交

---

## Task 6: 结构设计节点组（5个节点）

**Files:**
- Create: `backend/app/agents/nodes/question_chain.py`
- Create: `backend/app/agents/nodes/plot_blocks.py`
- Create: `backend/app/agents/nodes/subplot_network.py`
- Create: `backend/app/agents/nodes/rhythm_curve.py`
- Create: `backend/app/agents/nodes/chapter_count_estimate.py`

- [ ] **Step 1:** question_chain_design_node — 龙头凤尾 + 问题链

- [ ] **Step 2:** plot_blocks_node — 情节块展开

- [ ] **Step 3:** subplot_network_node — 支线网络

- [ ] **Step 4:** rhythm_curve_node — 预期节奏曲线

- [ ] **Step 5:** chapter_count_estimate_node — 章节数估算

- [ ] **Step 6:** 提交

---

## Task 7: 写作节点组（核心，5个节点）

**Files:**
- Create: `backend/app/agents/nodes/context_assembly.py`
- Create: `backend/app/agents/nodes/chapter_planning.py`
- Rewrite: `backend/app/agents/nodes/chapter_generation.py` → `chapter_writing.py`
- Create: `backend/app/agents/nodes/post_write_update.py`
- Create: `backend/app/agents/nodes/deep_review.py`

- [ ] **Step 1:** context_assembly_node（感知）

从 KnowledgeBaseService 加载：当前情节块目标 + 风格约束 + 待回收伏笔 + 问题链。阶段3集成语义检索前，暂用 DB 全量读取（降级模式）。

- [ ] **Step 2:** chapter_planning_node（决策）

输出章节点（因果链/钩子/场景规划/涉及角色设定伏笔），设置 waiting_for_confirmation=True。

- [ ] **Step 3:** chapter_writing_node（执行）

基于章节点+上下文+风格约束写正文。保留现有流式生成逻辑，增加风格约束注入。

- [ ] **Step 4:** post_write_update_node（自检——13项子任务）

核心方法 _run_post_write_updates()，内部 12 个子函数：
1. _check_character_consistency — 角色一致性（行为/对话/知识边界）
2. _update_timeline — 追加时间线
3. _update_foreshadowing — 更新伏笔表（暗示→强化→揭示）
4. _update_plot_questions — 更新问题链
5. _update_dynamic_settings — 更新动态设定
6. _check_style_taboo — 禁忌词快查
7. _update_style_stats — 风格统计
8. _update_subplots — 更新支线网络
9. _extract_dialogue_samples — 对话样本提取
10. _update_scene_list — 更新场景清单
11. _compress_timeline — 时间线压缩
12. _mark_for_indexing — 标记待索引内容

结果汇总写入 state["post_write_results"]

- [ ] **Step 5:** deep_review_node（每5章触发）

检查维度：情节一致性/伏笔追踪/节奏分析/设定违反/风格漂移/POV审查

- [ ] **Step 6:** 提交

---

## Task 8: 修订节点组（3个节点）

**Files:**
- Create: `backend/app/agents/nodes/structural_review.py`
- Create: `backend/app/agents/nodes/character_arc_review.py`
- Create: `backend/app/agents/nodes/final_polish.py`

- [ ] **Step 1:** structural_review_node — 伏笔闭环/问题链闭环/时间线一致性/支线闭环

- [ ] **Step 2:** character_arc_review_node — 角色弧验证+逐章风格检查+开场钩子闭环

- [ ] **Step 3:** final_polish_node — 修改章节+更新追踪文件+可选设定百科

- [ ] **Step 4:** 提交

---

## Task 9: StateGraph 重写

**Files:**
- Rewrite: `backend/app/agents/graph.py`

- [ ] **Step 1:** 重写 create_novel_graph()

工作流图：

```
入口 → inspiration_dialogue → story_seed → outline_generation
→ world_setting → character_generation → relation_generation
→ style_setup → foreshadowing_plan
→ (用户确认知识库)
→ question_chain → plot_blocks → subplot_network → rhythm_curve → chapter_count_estimate
→ (用户确认结构)
→ context_assembly → chapter_planning → (用户确认章节点) → chapter_writing
→ post_write_update → (条件: 每5章→deep_review) → context_assembly (下一章)
或 → structural_review → character_arc_review → final_polish → END
```

- [ ] **Step 2:** 实现条件路由函数

route_after_inspiration, route_after_knowledge, route_after_structure, route_after_post_write, route_after_deep_review

- [ ] **Step 3:** 更新 sse_events.py 适配新阶段和节点名称

- [ ] **Step 4:** 提交

---

## Task 10: Workflow API 适配

**Files:**
- Rewrite: `backend/app/api/workflow.py`
- Create: `backend/app/api/knowledge.py`
- Create: `backend/app/schemas/knowledge.py`

- [ ] **Step 1:** 重写 workflow.py — 适配新 NovelState 和 graph

- [ ] **Step 2:** 实现 knowledge.py — 知识库 CRUD API (world_setting, style_constraints, plot_blocks, foreshadowings, timeline, style_snapshots)

- [ ] **Step 3:** 实现 schemas/knowledge.py — Pydantic schemas

- [ ] **Step 4:** 在 main.py 注册新路由

- [ ] **Step 5:** 提交

---

## Task 11: 前端 — 工作台布局重写

**Files:**
- Rewrite: `frontend/src/components/workbench/WorkbenchLayout.tsx`
- Rewrite: `frontend/src/components/workbench/TabNavigation.tsx`
- Create: `frontend/src/components/workbench/ChapterListPanel.tsx`
- Create: `frontend/src/components/workbench/AgentChatPanel.tsx`
- Create: `frontend/src/components/workbench/ProgressDashboard.tsx`
- Rewrite: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1:** 重写 workbenchStore.ts — 新状态（activeTab/selectedChapter/phase 等）

- [ ] **Step 2:** 重写 WorkbenchLayout.tsx — 三栏+标签页+底栏布局

- [ ] **Step 3:** 重写 TabNavigation.tsx — 4个标签页（写作/知识库/结构/追踪）

- [ ] **Step 4:** 实现 ChapterListPanel.tsx — 按情节块分组的章节列表

- [ ] **Step 5:** 实现 AgentChatPanel.tsx — 右栏智能体对话（复用现有 AICompanionSidebar 逻辑）

- [ ] **Step 6:** 实现 ProgressDashboard.tsx — 底栏进度仪表盘

- [ ] **Step 7:** 提交

---

## Task 12: 前端 — 写作标签页

**Files:**
- Create: `frontend/src/components/workbench/creation/ChapterNodePanel.tsx`
- Create: `frontend/src/components/workbench/creation/InspirationChat.tsx`
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1:** InspirationChat.tsx — 创意对话组件（SSE流式+输入框）

- [ ] **Step 2:** ChapterNodePanel.tsx — 章节点确认卡片

- [ ] **Step 3:** 改造 WritingPanel.tsx — 正文上方插入 ChapterNodePanel

- [ ] **Step 4:** 提交

---

## Task 13: 前端 — 其他标签页骨架

**Files:**
- Create: `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx`
- Create: `frontend/src/components/workbench/knowledge/WorldSettingView.tsx`
- Create: `frontend/src/components/workbench/structure/StructureTab.tsx`
- Create: `frontend/src/components/workbench/tracking/TrackingTab.tsx`
- Extend: `frontend/src/lib/api.ts`

- [ ] **Step 1:** 扩展 api.ts — 添加知识库 API 调用函数

- [ ] **Step 2:** KnowledgeTab + WorldSettingView — 知识库浏览骨架

- [ ] **Step 3:** StructureTab — 结构标签页骨架

- [ ] **Step 4:** TrackingTab — 追踪标签页骨架

- [ ] **Step 5:** 提交

---

## Task 14: 端到端集成测试

**Files:**
- Create: `backend/tests/test_creation_agent.py`

- [ ] **Step 1:** 测试创意孵化→写作完整流程

- [ ] **Step 2:** 测试写后自检 13 项输出

- [ ] **Step 3:** 测试前端工作台渲染和交互

- [ ] **Step 4:** 提交

---

## 依赖关系

```
Task 1 (数据模型) → Task 2 (NovelState) → Task 4 (知识库服务) → Task 3 (Prompt)
  → Task 5 (创意孵化节点) → Task 6 (结构节点) → Task 7 (写作节点) → Task 8 (修订节点)
  → Task 9 (StateGraph) → Task 10 (Workflow API)

Task 1 → Task 11 (前端布局) → Task 12 (写作标签页) → Task 13 (其他标签页)

Task 10 + Task 12 → Task 14 (集成测试)
```

## 交付标准

阶段 1 完成后，系统能够：

1. 通过对话式创意孵化开始一个新项目
2. 自动生成知识库（世界观/角色/风格/伏笔地图）
3. 通过逆向规划设计结构（问题链/情节块/节奏曲线）
4. 逐章写作：上下文组装→章节点确认→正文生成→13项写后自检
5. 每5章触发深度审查
6. 全部章节完成后执行三轮修订
7. 前端工作台完整可用（三栏+标签页+底栏）
