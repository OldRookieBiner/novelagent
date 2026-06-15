# 上下文机制优化设计

> 日期：2026-06-15
> 范围：架构统一、智能检索、性能优化
> 方案：渐进重构（方案 A）

---

## 1. 背景与问题

NovelAgent 的上下文机制存在三条独立路径，彼此不协调：

1. **`agent_context.py`**（`build_agent_context`）— Agent system prompt 的项目数据加载，阶段感知，逐项预算控制
2. **`context_strategy.py`**（三种策略类）— 章节写作时的前文上下文组装，**仅被 `chapter_quality.py` 品控服务调用，Agent 主路径未集成**
3. **`knowledge_search` 工具** — 语义检索 + DB 降级查询，与预加载数据大量重叠

具体问题：

| # | 问题 | 影响 |
|---|------|------|
| 1 | `context_strategy.py` 未集成到 Agent 主上下文路径 | 三种策略（Full/Hybrid/Summary）仅在 `chapter_quality.py` 品控服务中使用，Agent 主路径的 `build_agent_context` 完全未调用，前文策略形同虚设 |
| 2 | 预加载与检索数据重叠 | `previous_chapter_closing` 与 Full 策略潜在重复（当前两条路径未并行运行，集成后需去重）；角色精简索引预加载 + knowledge_search 返回全量，部分字段重叠 |
| 3 | DB 查询碎片化 | WRITING 阶段 ~20 次 Store 调用（含 `validate_prerequisites` 内部 6+ 次），每次创建独立 DB session；`list_characters` 同一函数内被调用 2 次 |
| 4 | 无跨请求缓存 | 同项目连续对话全量重建上下文 |
| 5 | Token 预算硬编码，与 context_window 脱节 | `agent.py` 调用 `build_agent_context` 时未传 `max_tokens`，默认 12000；而 `get_context_window` 的结果（如 1M）已计算但未用于上下文构建，1M 窗口利用率仅 ~1.2% |
| 6 | 轻量模式阈值硬编码 | `max_tokens <= 5000` 触发，不适配 1M 窗口 |
| 7 | 估算精度偏低 | 中文 2 token/字过于保守 |
| 8 | 精简预加载 + 全量检索，部分字段重叠 | 预加载已做字段裁剪（角色 name+role+motivation、伏笔 content[:60]），但 knowledge_search 降级路径返回全量数据，两者部分字段重叠；1M 窗口下信噪比成为瓶颈 |

---

## 2. 架构设计 — 统一上下文路径

### 2.1 三层架构

```
┌─────────────────────────────────────────┐
│          System Prompt 组装层            │  ← agent.py 调用
│  (phase_label + context_block + warning) │
├─────────────────────────────────────────┤
│       ProjectContextAssembler            │  ← 统一入口，取代 build_agent_context
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ 项目数据层   │  │ 前文策略层        │  │
│  │ (phase感知   │  │ (context_strategy │  │
│  │  精简预加载)  │  │  三种策略)        │  │
│  └─────────────┘  └──────────────────┘  │
├─────────────────────────────────────────┤
│         BudgetAllocator                  │  ← 预算分配器
│  (根据 context_window + phase 分配预算)   │
└─────────────────────────────────────────┘
```

### 2.2 核心变更

**`context_strategy.py` 升级为被真实调用的前文策略层：**
- 保持三种策略接口不变
- `get_context_strategy()` 由 `ProjectContextAssembler` 在 WRITING/REVISION 阶段调用
- 策略选择基于 token 预算动态判断，不使用固定章节数阈值：
  - **Full**：全部已写章节 token 总量 ≤ 前文预算 80% → 放得下就全放
  - **Hybrid**：Full 放不下时自动降级 → 近章全文 + 远章大纲概要
  - **Summary**：Hybrid 也放不下时降级 → 近章全文 + 当前弧摘要 + 前弧摘要
- 用户手动覆盖保留：明确指定 `fulltext` / `hybrid` / `summary` 时按用户选择走

**`agent_context.py` 重构为 `ProjectContextAssembler`：**
- 原有阶段加载逻辑保留为 `_load_phase_data()` 私有方法
- 新增 `_load_previous_context()` 方法，调用 `context_strategy` 组装前文
- 输出统一为 `dict`，包含 `project_data` 和 `previous_text` 两个顶层 key
- 轻量模式阈值改为相对于 `context_window` 动态计算

**`agent.py` 调用点适配：**
- `build_agent_context()` → `ProjectContextAssembler.build()`
- `context_block` 的 JSON 组装区分 `project_data` 和 `previous_text`
- system prompt 模板中，前文上下文用独立段落呈现，与项目数据块视觉分离

### 2.3 职责边界

| 模块 | 职责 |
|------|------|
| `context_strategy.py` | 已写章节的前文如何呈现（全文/混合/摘要），不关心项目元数据 |
| `ProjectContextAssembler` | 整个 system prompt 需要哪些数据，协调项目数据 + 前文策略 + 预算 |
| `agent.py` | 把 Assembler 输出填入 prompt 模板，不关心数据来源 |

### 2.4 数据流

```
# 目标
agent.py → ProjectContextAssembler.build(context_window, phase, chapter_number)
         → BudgetAllocator.allocate(context_window, phase)
         → _load_phase_data(budget.project_data_budget)
         → _load_previous_context(budget.previous_text_budget)  # 调用 context_strategy
         → { project_data: {...}, previous_text: "...", budget_used: N }
```

### 2.5 不改变的部分

- `knowledge_search` 工具的接口和行为不变
- `KnowledgeBaseService` 的接口不变
- 前端完全无感知

---

## 3. 智能设计 — 精简预加载 + 精准检索补充

### 3.1 核心原则

1M 窗口下瓶颈从"放不下"变成"噪音太多"。LLM 在超长上下文中注意力衰减，设计目标是**提高信噪比**，而非最大化填充率。

### 3.2 数据三级分类

| 级别 | 含义 | 加载方式 | 典型数据 |
|------|------|---------|---------|
| **Critical** | 当前任务必需，缺失就无法正确执行 | 始终预加载到 system prompt | 当前章节大纲、风格约束、上一章结尾、🔴设定、待回收伏笔 |
| **Important** | 按阶段需要，提供全局视野但非每步都引用 | 阶段感知预加载，精简字段 | 角色索引（name+role+motivation）、情节块列表、世界观数据 |
| **Supplementary** | 按需查询，只在 Agent 判断需要时获取 | knowledge_search 检索 | 角色完整 backstory、关系演变细节、特定章节正文、历史时间线 |

### 3.3 按阶段的具体预加载策略

**INCUBATION — 极简：**
- Critical：大纲标题+章数+摘要（outline_index）、故事种子摘要
- Important：无（此阶段在创建数据，不需要读大量已有数据）
- Supplementary：用户主动提问时通过 knowledge_search 查

**STRUCTURE — 结构视野：**
- Critical：大纲全文（outline）、风格约束
- Important：角色索引（name + role + motivation）、情节块列表、伏笔概览
- Supplementary：角色详情、关系图谱、世界观数据

**WRITING — 精准执行：**
- Critical：大纲全文（outline）、当前章节大纲（全字段）、上一章结尾 500 字、🔴设定、风格约束、待回收/逾期伏笔、当前情节块
- Important：角色索引（name + role + motivation + personality[:100]）、世界观数据（core_concept + red_settings + key_locations）、近 N 章前文（由 context_strategy 决定）
- Supplementary：关系演变规划（当前章触发的除外，属于 Critical）、远章正文、时间线

**REVISION — 全局审查：**
- Critical：大纲全文（outline）、风格约束、🔴设定
- Important：角色索引、伏笔概览、时间线近 20 章、情节块、支线状态、待决情节问题（pending）、风格快照（最近 10 条）
- Supplementary：角色完整档案、跨卷追踪数据

### 3.4 检索增强策略

**问题：** `build_agent_context` 预加载精简版数据，`knowledge_search` 降级路径返回全量数据，两者部分字段重叠。

**改进：**

1. **预加载声明机制** — `ProjectContextAssembler` 构建完 context 后，生成 `_loaded_keys` 列表（如 `["world_setting", "characters_index", "style_constraints"]`），存入 `tool_context` 的 ContextVar

2. **knowledge_search 仅用于去重判断，不截断检索结果** — `_loaded_keys` 的唯一用途是让 `knowledge_search` 在返回结果中附加提示信息，告知 Agent 该数据的精简版已在上下文中。**knowledge_search 始终返回完整结果**，不因已预加载而拒绝或截断输出。原因：
   - knowledge_search 的核心价值是为 Agent 补充详情（如角色完整 backstory、特定章节正文），如果拒绝输出就违背了工具本意
   - Agent 能自行判断上下文中已有信息，无需工具代为过滤
   - 预加载是精简版（如角色 name+role+motivation），检索返回完整版，两者粒度不同，不算真正重复

3. **深层检索入口** — Supplementary 级别数据（角色完整 backstory、某章正文），knowledge_search 返回完整内容。预加载只放了精简版，天然互补

### 3.5 前文策略与检索的协作

- **Full 策略**：直接放全文，最简单也最准确
- **Hybrid 策略**：近章全文 + 远章大纲概要。远章如果 Agent 需要回顾细节，通过 `knowledge_search(query="第X章", target="timeline")` 获取
- **Summary 策略**：近章全文 + 弧摘要。同理，Agent 可通过检索补充

前文策略只负责"自动注入的部分"，Agent 仍有主动检索能力，两者互补而非替代。

### 3.6 去重规则

| 场景 | 处理方式 |
|------|---------|
| `previous_chapter_closing` 与 Full 策略重叠 | 前文策略为 Full 时，不单独加载 `previous_chapter_closing`（已被前文包含） |
| 角色索引与 knowledge_search 查角色 | knowledge_search 始终返回完整结果，在返回中附加提示"角色基础信息已在项目上下文中"供 Agent 参考，不截断不拒绝 |
| 风格约束重复出现 | 预加载放一次，knowledge_search 返回时附加提示"已在项目上下文中"，不截断输出 |

---

## 4. 性能设计 — 减少查询、引入缓存、优化预算分配

### 4.1 DB 批量读取

**现状：** WRITING 阶段 ~20 次 Store 调用（16 次显式 kb 调用 + `validate_prerequisites` 内部 6+ 次），每次创建独立 DB session；`list_characters` 同一函数内被调用 2 次。

**改进：** `ProjectContextAssembler` 使用单次 session 批量读取，然后在内存中按 phase + budget 裁剪。

在 `KnowledgeBaseService` 上新增 `batch_read_for_context()` 方法，与现有 `batch_read_for_index()` 的区别：
- 包含章节正文和章节大纲（index 版本不含，太长）
- 包含上一章结尾片段
- 包含变更记录
- 不包含场景清单（index 版本需要）

```
# 目标数据流
raw_data = kb.batch_read_for_context()          # 1 次 DB session
project_data = _phase_filter(raw_data, phase, budget)  # 内存操作
```

### 4.2 跨请求缓存

同一项目短时间内多次 Agent 请求时，世界观、角色、大纲等数据变化频率很低。

| 属性 | 规则 |
|------|------|
| 缓存层 | 进程内 LRU cache，key = `(project_id, data_type, version_tag)` |
| version_tag | 每种数据类型维护递增版本号，写入操作时 +1，读取时比较。通过 `_BaseStore._bump_version(data_type)` 统一入口管理，所有 Store 的写操作（create/update/delete）调用此方法触发版本递增，确保不遗漏 |
| 缓存范围 | 世界观、角色索引、风格约束、大纲（变化频率低）。章节正文和伏笔状态不缓存 |
| TTL | 60 秒自动过期 |
| 失效 | 写入类工具执行后，主动使对应 data_type 缓存失效 |
| 实现 | Python `functools.lru_cache` + version_tag，无需 Redis（单实例 Docker 部署） |

### 4.3 预算自适应分配 — BudgetAllocator

**分配规则：**

```
输入: context_window, phase, current_chapter_number
输出: { project_data_budget, previous_text_budget, history_budget, output_budget, safety_margin }

第一步：扣除固定项
  output_budget   = min(context_window × 5%, 50000)
  safety_margin   = context_window × 10%
  system_prompt   = context_window × 2%

  剩余可用 = context_window - output_budget - safety_margin - system_prompt

第二步：按阶段分配剩余
  INCUBATION: history 60% / previous  0% / project_data 40%
  STRUCTURE:  history 40% / previous  0% / project_data 60%
  WRITING:    history 10% / previous 70% / project_data 20%
  REVISION:   history 20% / previous 40% / project_data 40%

  注意：以上为默认比例，定义在 `constants.py` 的 `PHASE_BUDGET_RATIOS` 中，
  可通过配置调整而非硬编码在 BudgetAllocator 类内。
```

**1M 窗口 WRITING 示例（第 30 章）：**

```
总窗口: 1,000,000

扣除固定项:
  output       = 50,000
  safety       = 100,000
  system       = 20,000
  剩余         = 830,000

WRITING 分配:
  history      = 83,000
  previous     = 581,000   ← 约 80 万字前文
  project_data = 166,000
```

**128K 窗口 WRITING 示例（第 30 章）：**

```
总窗口: 128,000

扣除固定项:
  output       = 6,400
  safety       = 12,800
  system       = 2,560
  剩余         = 106,240

WRITING 分配:
  history      = 10,624
  previous     = 74,368    ← 放不下 29 章全文 → 自动降级 Hybrid
  project_data = 21,248
```

**预算不够用时：**
1. 先用 `project_data_budget` 加载 Critical 数据
2. 有余量再加 Important 数据
3. `previous_budget` 交给 `context_strategy`，由策略决定放全文还是概要
4. 如果 Critical 数据就超了 `project_data_budget`，自动压缩（角色只保留 name+role，砍掉 personality）
5. 极端情况：project_data 压到最精简仍超预算，才触发轻量模式

### 4.4 Token 估算精度提升

基于 DeepSeek V4 分词器参数，保守系数 1.2：

```python
# 现状
中文: 2.0 token/字
英文: 0.5 token/char

# 目标
中文: 0.6 × 1.2 = 0.72 token/字
英文: 0.3 × 1.2 = 0.36 token/char
非空文本最少返回 1
```

配合 safety_margin 的 10%，总余量约 22%，足够覆盖估算误差。

**注意：** DeepSeek V4 标称 1M 上下文窗口，但实际有效上下文可能受 KV cache 限制和注意力衰减影响低于标称值。BudgetAllocator 应以用户配置的 `context_window` 为准（`get_context_window` 返回值），而非假设模型一定能利用全部标称窗口。safety_margin 的 10% + 估算系数的保守性（1.2 倍）已为此留出缓冲。

### 4.5 性能优化量化预期

| 指标 | 现状 | 优化后 |
|------|------|--------|
| WRITING 阶段 DB 连接数 | ~20 次 | 1-2 次 |
| 同项目连续请求 DB 查询量 | 100% | 首次 100%，后续 ~30% |
| 1M 模型下前文可用预算 | 固定 12K | 动态 ~581K |
| 预算利用率（1M 模型） | ~1.2% | 预期 50-70% |

---

## 5. 变更清单

### 5.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/agents/budget_allocator.py` | BudgetAllocator 类 |
| `backend/app/agents/context_cache.py` | 跨请求 LRU 缓存 + version_tag 管理 |

### 5.2 重构文件

| 文件 | 变更 |
|------|------|
| `backend/app/agents/agent_context.py` | 重构为 `ProjectContextAssembler`，整合 `context_strategy` 调用，新增 `_load_previous_context()` |
| `backend/app/agents/context_strategy.py` | 策略选择改为基于 token 预算动态判断，删除固定章节数阈值 |
| `backend/app/agents/token_budget.py` | `estimate_tokens` 系数改为 0.72/0.36 |
| `backend/app/agents/tool_context.py` | 新增 `_loaded_keys` ContextVar |
| `backend/app/agents/tools/perception/knowledge_search.py` | 感知 `_loaded_keys`，在返回结果中附加"已在项目上下文中"提示，不截断不拒绝输出 |
| `backend/app/agents/services/knowledge_base.py` | 新增 `batch_read_for_context()` 方法 |
| `backend/app/api/agent.py` | 调用点从 `build_agent_context` 迁移到 `ProjectContextAssembler.build()`，适配新输出结构 |

### 5.3 不变文件

| 文件 | 原因 |
|------|------|
| `backend/app/agents/agent_graph.py` | Agent 图定义不变 |
| `backend/app/agents/prompts.py` | Prompt 模板不变（system prompt 格式微调在 agent.py 中处理） |
| `backend/app/agents/initialization.py` | 初始化流程独立，不涉及上下文组装 |
| `backend/app/agents/services/retrieval.py` | 语义检索服务接口不变 |
| 前端所有文件 | 上下文机制是后端内部优化，前端无感知 |

---

## 6. 实施顺序

渐进重构，每步可独立验证：

1. **Step 1**：Token 估算系数更新（`token_budget.py`）— 最独立，可立即测试
2. **Step 2**：BudgetAllocator 实现 — 纯新增模块，无副作用
3. **Step 3**：跨请求缓存 — 新增 `context_cache.py`，不改现有逻辑
4. **Step 4**：`batch_read_for_context()` — 在 KnowledgeBaseService 上新增方法
5. **Step 5**：`context_strategy.py` 策略选择改为动态 — 保持接口不变
6. **Step 6**：`ProjectContextAssembler` 重构 — 整合 Step 2-5 的能力，替换 `build_agent_context`
7. **Step 7**：`agent.py` 调用点迁移 — 适配新输出结构
8. **Step 8**：knowledge_search 感知 `_loaded_keys` — 消除检索重复
9. **Step 9**：去重规则实现 — `previous_chapter_closing` 等去重逻辑
10. **Step 10**：端到端测试 — 各阶段、各策略、各窗口大小的完整验证

---

## 7. 测试策略

- **单元测试**：每个 Step 对应新增/修改的模块都有独立测试
  - `test_budget_allocator.py` — 各阶段、各窗口大小的预算分配
  - `test_context_strategy.py` — 动态策略选择、边界条件
  - `test_context_cache.py` — 缓存命中/失效/TTL
  - `test_token_budget.py` — 新估算系数验证
- **集成测试**：Step 7 完成后，完整 Agent 请求的上下文组装验证
- **回归测试**：现有 `test_agent_tools.py`、`test_context_strategy.py` 必须通过

---

## 8. 审查修正记录

> 日期：2026-06-16
> 范围：对照源码审查 spec 和 plan 的正确性，修复所有发现的问题

### 8.1 发现的问题及修正

| # | 问题 | 严重度 | 修正 |
|---|------|--------|------|
| R1 | `batch_read_for_context` 中 `outline_store` 的方法名应为 `_read_chapter_outlines_with_session`，plan 中错误写为 `_read_all_outlines_with_session` | HIGH | 修正 plan 中方法名 |
| R2 | `chapter_store.py` 没有 `_read_all_with_session` 方法（Chapter 模型没有 `project_id` 列，需通过 ChapterOutline JOIN 查询），plan 直接引用了不存在的方法 | HIGH | plan Task 4 Step 2 需新增此方法，且查询逻辑需 JOIN ChapterOutline |
| R3 | `change_store.py` 没有 `_read_all_with_session` 方法 | MEDIUM | plan Task 4 Step 2 需新增此方法 |
| R4 | `batch_read_for_context` 用 `hasattr` 静默降级 — 违反"不打补丁"原则 | MEDIUM | 移除 `hasattr`，改为 Task 4 保证方法存在后直接调用，缺少则抛异常 |
| R5 | `_load_writing_data` 缺失 4 个 WRITING 阶段数据：`recent_decisions`、`questions_for_chapter`、`recent_timeline`、`relation_evolution_cues` | HIGH | 补充缺失字段到 plan Task 7 `_load_writing_data` |
| R6 | `_load_writing_data` 仍调用 `self.kb.validate_prerequisites()` — 破坏批量读取的 DB 连接数优化（~6+ 次独立 session） | HIGH | `validate_prerequisites` 应接收 `raw_data` 参数，从批量数据中校验而非再次查 DB |
| R7 | `build_agent_context` 向后兼容包装器用 `max_tokens * 8` 魔数映射 `context_window` | HIGH | 改为接受显式 `context_window` 参数，从 `get_context_window()` 取值传入 |
| R8 | ContextCache 定义了全局单例但 plan 的 `ProjectContextAssembler` 未实际使用 | MEDIUM | 在 `_load_phase_data` 中接入缓存：先查缓存，miss 时走 batch_read 后写缓存 |
| R9 | `_bump_version` 在 `session()` 块之后调用，commit 失败时仍递增版本号 | LOW | 移到 session 块内部，commit 之后再 bump（在 try/finally 中处理） |
| R10 | `BudgetTracker` 不验证 project_data + previous_text 总量是否超 context_window | MEDIUM | 在 `build()` 返回前增加总量检查，超限时自动压缩 Important 数据 |
| R11 | `_load_writing_data` 伏笔逻辑错误：`status="overdue"` 不是有效状态，overdue 是从 `expected_resolve_chapter < current_chapter` 计算得出 | HIGH | 修正伏笔过滤逻辑：pending = `status="pending_reclaim"`，overdue = `status in ("active", "pending_reclaim") and expected_resolve_chapter < chapter_number` |
| R12 | `_load_with_cache` 即使全部缓存命中也走 batch_read_for_context | MEDIUM | 始终走 batch_read（需不可缓存数据如 chapters/timeline），但缓存命中数据覆盖 batch_read 结果 |

### 8.2 修正详述

**R6: validate_prerequisites 从批量数据校验**

当前 `validate_prerequisites` 在 `KnowledgeBaseService` 上，内部调用 6+ 个 Store 方法（每个创建独立 session）。重构后应提供两种模式：

1. `validate_prerequisites_from_raw(raw_data, chapter_number)` — 从批量读取结果校验，不创建新 session
2. `validate_prerequisites(chapter_number)` — 原有方法保持不变，供非批量路径调用

`ProjectContextAssembler._load_writing_data` 使用模式 1，从 `raw_data` 提取校验所需的各项数据。

**R7: 向后兼容包装器修正**

`chapter_quality.py` 不调用 `build_agent_context`（它直接用 `KnowledgeBaseService` + `context_strategy`），所以向后兼容的调用方只有 `agent.py`。但 `agent.py` 在 Task 8 会被迁移到 `ProjectContextAssembler`，因此 `build_agent_context` 的向后兼容包装器只需要满足一个要求：**在 Task 7 和 Task 8 之间（过渡期）不 break**。

最佳方案：`build_agent_context` 接受 `context_window` 参数，默认值从 `get_context_window()` 获取（不再用 `max_tokens * 8` 魔数）。`max_tokens` 参数保留但标记为 deprecated。

**R8: ContextCache 接入**

在 `ProjectContextAssembler.build()` 中：
1. 对可缓存数据类型（world_setting, characters, style_constraints, outline），先查 `context_cache.get()`
2. 缓存 miss 时走 `batch_read_for_context()`，然后对可缓存类型写入 `context_cache.set()`
3. version_tag 通过 `_BaseStore.get_version()` 获取

**R10: 总量超窗口保护**

在 `build()` 返回前：
```python
total = estimate_tokens(json.dumps(project_data)) + estimate_tokens(previous_text)
if total > context_window - allocation.output_budget - allocation.safety_margin:
    # 自动压缩：从 Important 数据开始裁剪
    ...
```

---

### 8.3 第二轮审查修正（N1-N4）

| # | 问题 | 严重度 | 修正 |
|---|------|--------|------|
| N1 | `_load_revision_data` 缺失 `plot_questions`（pending）、`subplots`（non-abandoned）、`style_snapshots`（最近 10 条）— 源码有 8 字段，plan 只有 5 字段 | HIGH | 补充 3 个缺失字段到 plan Task 7 `_load_revision_data`，与源码 `_load_revision_context` 对齐 |
| N2 | `_load_structure_data`、`_load_writing_data`、`_load_revision_data` 缺失 `outline` 加载 — 源码 `build_agent_context` 始终在阶段分发前加载完整 `outline` | HIGH | 在每个 `_load_*_data` 方法开头加载 `outline`（INCUBATION 仍为精简版 `outline_index`；其余阶段加载完整 `outline`）；§3.3 各阶段 Critical 项补充"大纲" |
| N3 | `_load_incubation_data` 加载精简 `outline_index` 而源码加载完整 `outline` — 设计差异，非 bug | INFO | 保持设计意图：INCUBATION 极简模式只需索引，与 spec §3.3 一致 |
| N4 | `batch_read_for_context` 返回 `style_snapshots: []` 空列表，REVISION 阶段无法获取风格快照 | MEDIUM | 新增 `StyleStore._read_snapshots_with_session(db, last_n=10)` 方法，`batch_read_for_context` 调用该方法返回真实数据 |
