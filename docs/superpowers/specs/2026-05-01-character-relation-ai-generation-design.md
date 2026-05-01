# 角色和关系 AI 生成功能设计

**日期**: 2026-05-01
**版本**: v0.8.x（方案 A：最小化集成）
**状态**: 已批准

---

## 一、背景

### 当前状态

| 组件 | 状态 |
|------|------|
| DB 模型（Character, Relation, EvolutionPlan, EvolutionRecord） | ✅ 已完成 |
| Pydantic Schemas（全部 CRUD + AI 请求） | ✅ 已完成 |
| TypeScript 类型定义 | ✅ 已完成 |
| 后端 CRUD API（`/characters`, `/relations`） | ✅ 已完成 |
| 前端手工 CRUD 面板（CharacterPanel, RelationPanel） | ✅ 已完成 |
| 后端 AI 生成端点（`characters/generate`, `relations/generate`） | ❌ 返回 501 |
| Agent Prompts（character_generation, relation_generation） | ❌ 不存在 |
| Agent Nodes（角色生成、关系生成节点） | ❌ 不存在 |
| LangGraph 工作流集成 | ❌ 不存在 |
| 前端 `OutlineProgressDialog` 步骤 2/3 | ❌ 用 setTimeout 假扮 |

### 问题

用户从灵感生成大纲后，前端进度弹窗显示"生成人物"和"生成关系"步骤，但本质是用 `setTimeout` 模拟的假动画，实际没有产出任何角色或关系数据。

### 方案选择

采用**方案 A：最小化 LangGraph 集成**。大纲 Prompt 已产出角色信息（`outline_characters`），parse 后自动创建 Character 实体；仅需额外新增 1 个关系生成节点 + 1 个 LLM 调用。后续可迭代为方案 B（独立角色/关系生成 Prompt + 全字段输出）。

---

## 二、技术设计

### 2.1 LangGraph 工作流图变更

**现有流程**：
```
generate_outline → route_after_outline → wait_confirm | generate_chapter_outlines
```

**新流程**：
```
generate_outline → create_characters_from_outline → route_after_characters → wait_confirm | generate_relations
generate_relations → route_after_relations → wait_confirm | generate_chapter_outlines
```

新增节点：
- `create_characters_from_outline`（同步，无 LLM 调用）
- `generate_relations`（异步，调用 LLM）

新增路由：
- `route_after_characters` — 复用 `wait_for_confirmation`，confirmation_type="characters"
- `route_after_relations` — 复用 `wait_for_confirmation`，confirmation_type="relations"

### 2.2 节点设计

#### `create_characters_from_outline`

**类型**：同步节点，无 LLM 调用
**输入**：`state["outline_characters"]` — 大纲 parse 出的角色列表 `[{name, role, personality, motivation, arc}]`
**处理**：
1. 删除项目中已有角色（避免重复创建）
2. 映射大纲字段到 Character 模型：
   - `name` → `name`
   - `role` → `role`（主角 → 主角, 配角 → 配角, 反派 → 核心反派）
   - `personality` → `personality`
   - `motivation` → `core_motivation`
   - `arc` → `growth_arc`
3. 批量 INSERT 到 `characters` 表
4. 更新 `state["characters"]` 为已创建的角色列表（含 DB id）
5. 设置 `state["stage"] = "characters"`

**输出**：`state["characters"]` 已填充，`stage="characters"`

#### `generate_relations`

**类型**：异步节点，调用 LLM
**输入**：
- `state["characters"]` — 已创建的角色列表（含 id/name/role/personality）
- `state["outline_summary"]` — 大纲概述
- `state["outline_world_setting"]` — 世界观设定

**LLM 调用**：
- System Prompt: `RELATION_GENERATION_PROMPT`（新增，见 2.3）
- 使用 `get_llm_from_state_async` 获取 LLM 服务
- 调用 `llm.chat()` 生成关系列表

**输出解析格式**：
```
- 角色A名 | 角色B名 | 关系类型 | 信任度(0-100) | 描述 | 发展方向
```

**处理**：
1. 解析每行关系数据
2. 根据角色名查找 Character id
3. 批量 INSERT 到 `relations` 表
4. 更新 `state["relations"]` 和 `state["stage"] = "relations"`

### 2.3 Prompt 模板

新增 `RELATION_GENERATION_PROMPT`，存入 `DEFAULT_PROMPTS` 字典，key: `"relation_generation"`。

占位符：
- `{characters_text}` — 格式化的角色列表
- `{world_era}` — 世界观时代背景
- `{outline_summary}` — 大纲概述

输出要求：
- 每个角色对生成一条关系
- 格式：`- 角色A | 角色B | 关系类型 | 信任度 | 描述 | 发展方向`
- 关系类型：盟友/敌对/师徒/爱慕/亲情/利用/竞争
- 信任度：0-100 整数

### 2.4 前端改动

#### `OutlineProgressDialog.tsx`

改为对接 LangGraph SSE 流（`POST /workflow/run`），替代当前直接调用 `outlineApi.createStream`。

**SSE 事件映射**：

| SSE 事件 | node_name | 进度条行为 |
|----------|-----------|-----------|
| `node_start` | generate_outline | Step 1 → active |
| `node_done` | generate_outline | Step 1 → done, Step 2 → active |
| `node_done` | create_characters_from_outline | Step 2 → done, Step 3 → active |
| `node_done` | generate_relations | Step 3 → done, 完成状态 |
| `waiting` | generate_outline | 暂停，"等待确认大纲" |
| `waiting` | create_characters_from_outline | 暂停，"等待确认角色" |
| `waiting` | generate_relations | 暂停，"等待确认关系" |
| `chunk` | generate_outline | 实时流式显示大纲文本 |
| `error` | any | 错误状态，显示重试按钮 |

**确认流程**：弹出"等待确认"提示后，用户点击"查看并确认"跳转到对应面板（大纲/角色/关系），在那里确认后从工作台继续。

#### `useProjectData.ts`

无需改动。角色和关系数据已在加载项目时通过 `characterApi.list` / `relationApi.list` 获取。

### 2.5 文件变更

**新增文件**：
| 文件 | 作用 |
|------|------|
| `backend/app/agents/nodes/character_generation.py` | `create_characters_from_outline` 同步节点 + `extract_characters_from_outline` 辅助函数 |
| `backend/app/agents/nodes/relation_generation.py` | `generate_relations` 节点 + `parse_relations_response` 解析函数 |

**修改文件**：
| 文件 | 改动 |
|------|------|
| `backend/app/agents/prompts.py` | 新增 `RELATION_GENERATION_PROMPT`，`DEFAULT_PROMPTS` 中新增 key |
| `backend/app/agents/graph.py` | 新增 2 节点 + 编辑边 + 新增 2 路由函数 |
| `backend/app/agents/nodes/__init__.py` | 导出新节点 |
| `backend/app/api/characters.py` | 替换 3 个 `501` stub 为代理调用（`characters/generate` 调用 `create_characters_from_outline`，`relations/generate` 调用 `generate_relations`） |
| `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 从 `outlineApi.createStream` 切换到 `workflowApi.runWorkflow` |

---

## 三、数据流

```
用户点击"确认灵感，生成大纲"
  ↓
InspirationPanel.handleConfirm()
  → collectedInfoApi.update() 保存灵感数据
  ↓
OutlineProgressDialog 打开
  → workflowApi.runWorkflow(projectId, callbacks)
  ↓
LangGraph: generate_outline 节点
  → LLM 生成大纲文本 → parse_outline 解析
  → 更新 state (outline_title/outline_summary/outline_characters/...)
  → 保存到 DB (outline 表 + 检查点)
  ↓
LangGraph: create_characters_from_outline 节点
  → 从 state.outline_characters 提取角色
  → 批量 INSERT 到 characters 表
  → 更新 state.characters
  ↓ (条件路由: route_after_characters)
  │  hybrid/step_by_step → wait_confirm (等待用户确认)
  │  auto → 继续
  ↓
LangGraph: generate_relations 节点
  → LLM 生成关系文本 → parse_relations_response 解析
  → 批量 INSERT 到 relations 表
  → 更新 state.relations
  ↓ (条件路由: route_after_relations)
  │  hybrid/step_by_step → wait_confirm
  │  auto → 继续到 generate_chapter_outlines
  ↓
完成 → OutlineProgressDialog 显示 3 步全部 done
```

---

## 四、错误处理

1. **角色提取失败**：`outline_characters` 为空时，节点返回警告但不中断工作流（skip 角色生成，继续到关系生成）
2. **关系生成 LLM 失败**：SSE 发送 error 事件，前端进度弹窗显示重试按钮
3. **DB 写入失败**：回滚事务，记录日志，返回错误

---

## 五、测试要点

1. 大纲生成后 `outline_characters` 正确解析 → 角色成功创建到 DB
2. 角色创建后 `state.characters` 包含 DB id
3. 关系生成 Prompt 正确填入角色列表和世界观
4. 关系解析器正确解析 `- A | B | type | trust | desc | dev` 格式
5. 前端进度弹窗正确映射 SSE 事件到 3 步进度
6. hybrid 模式下角色/关系节点暂停等待确认
7. auto 模式下角色/关系节点自动继续