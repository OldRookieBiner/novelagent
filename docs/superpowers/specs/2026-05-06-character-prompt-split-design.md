# 大纲与人物 Prompt 拆分设计

**日期：** 2026-05-06
**版本：** v0.9.0
**类型：** Feature

---

## 背景

当前大纲生成 prompt（`outline_generation`）要求 AI 在一个响应中同时输出大纲、人物设定、世界观、情节节点、情感曲线、伏笔地图共六大板块。`parse_outline()` 用正则从文本中提取 `outline_characters` 列表，`create_characters_from_outline_node` 不调 LLM，仅做字段映射。

**核心问题：** 同一个 prompt 既要大纲又要人物，AI 输出不稳定。在大约 30% 的测试中，AI 跳过人物设定段落或输出格式偏差，导致 `char=0`，进而人物页面为空、关系生成为空。

**解决方向：** 将人物生成从大纲 prompt 中完全拆分出来，使每个 prompt 只专注一件事。

---

## 方案概要

**方案 B（完全拆分）**：大纲 prompt 移除人物设定板块，`create_characters_from_outline_node` 增加独立 LLM 调用，使用专用 `character_generation` prompt 根据大纲生成人物。这是唯一的人物来源，无回退逻辑。

---

## 架构设计

### 改造前数据流

```
outline_generation_node
  │  一个 prompt: 大纲+人物+世界观+情节+情感+伏笔
  │  parse_outline() → outline_characters (正则，不稳定)
  ▼
create_characters_from_outline_node
  │  无 LLM 调用，纯字段映射
  │  state["characters"] ← [{name, role, ...}] (无 id)
  ▼
persist_character_generation (SSE handler)
  │  DB INSERT → flush → c["id"] = char.id
  ▼
generate_relations_node
  │  从 DB 查角色 (含 id)，调 LLM 生成关系
  ▼
persist_relation_generation
```

### 改造后数据流

```
outline_generation_node
  │  一个 prompt: 大纲+世界观+情节+情感+伏笔 (移除人物板块)
  │  parse_outline() → 不再提取 outline_characters
  ▼
create_characters_from_outline_node
  │  独立 LLM 调用: character_generation prompt
  │  输入: outline_summary + world_era
  │  输出: 严格格式的人物列表
  │  state["characters"] ← LLM 解析结果
  ▼
persist_character_generation (SSE handler)
  │  DB INSERT → flush → c["id"] = char.id (逻辑不变)
  ▼
generate_relations_node
  │  从 DB 查角色 (含 id)，调 LLM 生成关系 (不变)
  ▼
persist_relation_generation
```

### 关键设计决策

**为什么不用回退策略？**
- 保留回退意味着大纲 prompt 依然要写人物板块，prompt 依然不专注
- 两套提取路径增加维护复杂度
- 回退恰好触发在 LLM 也失败的时候——此时正则大概率也拿不到好数据
- 独立的、更专注的人物 prompt 比"顺带写人物"的大纲 prompt 更稳定

**大纲 prompt 保留什么？**
移除"三、人物设定"板块，保留其他五大板块（标题、概述、世界观、情节节点、情感曲线、伏笔地图）。

**人物 prompt 用什么字段生成？**
输入大纲摘要 `outline_summary` 和世界观时代背景 `world_era`。这两个信息足够让 AI 推断出合理的人物阵容。

---

## 修改清单

### 1. `backend/app/agents/prompts.py` — Prompt 定义

**新增 `CHARACTER_GENERATION_PROMPT`：**

```python
CHARACTER_GENERATION_PROMPT = """你是一个资深小说角色设计师..."""

输入变量：
- `{outline_summary}` — 大纲概述
- `{world_era}` — 世界观时代背景

输出格式（严格）：
- 主角：姓名 | 性格 | 核心动机 | 成长弧线
- 核心反派：姓名 | 性格 | 核心动机 | 成长弧线
- 重要配角：姓名 | 性格 | 核心动机 | 成长弧线
（输出 4-6 个角色）
```

**修改 `OUTLINE_GENERATION_PROMPT`：**
- 移除"三、人物设定"板块及其所有子内容（角色格式、规则、子字段等）
- 移除"人物设定要用具体事件/行为体现"注意事项
- 调整板块编号：三→世界观、四→情节节点、五→情感曲线、六→伏笔地图

**更新 `DEFAULT_PROMPTS`：**
- 新增 `"character_generation": CHARACTER_GENERATION_PROMPT`

### 2. `backend/app/agents/nodes/character_generation.py` — 节点增加 LLM 调用

```python
async def create_characters_from_outline_node(state: NovelState) -> NovelState:
    outline_summary = state.get("outline_summary", "")
    world_era = (state.get("outline_world_setting") or {}).get("era", "未指定")

    # 获取 LLM
    llm = await get_llm_from_state_async(state)

    # 获取 prompt
    db = SessionLocal()
    try:
        prompt = get_system_prompt(db, "character_generation").format(
            outline_summary=outline_summary,
            world_era=world_era,
        )
    finally:
        db.close()

    # 调 LLM
    response = await llm.chat([{"role": "user", "content": prompt}])

    # 解析
    characters = parse_character_generation_response(response)

    new_state: NovelState = {
        **state,
        "characters": characters,
        "stage": STAGE_CHARACTERS,
    }
    return new_state
```

**新增 `parse_character_generation_response()`：**
- 独立的解析器，不修改现有 `parse_outline()` 或 `_parse_characters_section()`
- 解析格式：`- 角色定位：姓名 | 性格 | 核心动机 | 成长弧线`
- 使用 `_map_role()` 归一化角色定位
- 返回 `[{name, role, personality, core_motivation, growth_arc}]`

**保留 `extract_characters_from_outline()`：**
- 该函数仍被 `api/characters.py` 的 `/characters/generate` 端点使用
- 但其输入 `outline_characters` 将不再由大纲 prompt 产生（迁移过渡期保留兼容）

### 3. `backend/app/agents/nodes/outline_generation.py` — 大纲 prompt 简化

修改 `OUTLINE_GENERATION_PROMPT` 模板（在 `prompts.py` 中），移除人物设定板块：

```
移除前板块序号：
  一、标题  二、概述  三、人物设定  四、世界观  五、情节节点  六、情感曲线  七、伏笔地图

移除后板块序号：
  一、标题  二、概述  三、世界观  四、情节节点  五、情感曲线  六、伏笔地图
```

`parse_outline()` 中的 `_parse_characters_section()` 保留不删（兼容旧数据），但新的大纲响应不再包含人物设定段落。

### 4. `backend/app/schemas/system_prompt.py` — Agent type 注册

```python
"character_generation": {
    "name": "人物生成",
    "description": "根据小说大纲自动生成人物设定，包含主角、反派、配角",
    "variables": ["outline_summary", "world_era"],
    "variable_descriptions": {
        "outline_summary": "小说大纲的概述内容",
        "world_era": "故事世界观的年代设定",
    },
},
```

新增 `"character_generation"` 到 `AgentTypeKey` 类型。

### 5. `backend/app/api/system_prompts.py` — Prompt key 注册

```python
PROMPT_KEY_MAP = {
    ...
    "character_generation": "prompt_character_generation",
}
```

### 6. `backend/app/api/workflow.py` — 无需修改

`NODE_PERSIST_MAP` 中的 `create_characters_from_outline_node` → `persist_character_generation` 映射不变，persist 逻辑本身不变。`build_initial_state()` 中也无需改动。

### 7. `backend/app/utils/workflow_persistence.py` — 删除冗余注释

`persist_character_generation` 中的 `c["id"] = char.id` 写回逻辑保留不变。由于 relation_generation_node 已改为从 DB 查角色（v0.8.1 修复），该写回实际不再被依赖，但保留无妨。

---

## API 兼容性

| API 端点 | 影响 |
|----------|------|
| `POST /api/projects/{id}/workflow/run` | 无变化，SSE 事件格式不变 |
| `GET /api/projects/{id}/characters` | 无变化 |
| `POST /api/projects/{id}/characters/generate` | 保留 `extract_characters_from_outline`，仍可手动触发生成 |
| `PUT /api/system_prompts/character_generation` | 新增端点，可自定义人物生成 prompt |
| `WebSocket / SSE 事件` | node_start/node_done/chunk 事件格式不变 |

---

## 测试计划

| 测试 | 内容 |
|------|------|
| 单元测试 | `parse_character_generation_response()` 解析正确性 |
| 单元测试 | `create_characters_from_outline_node` 状态更新正确性 |
| 集成测试 | 完整工作流：大纲→人物→关系→持久化 |
| 回归测试 | `docker exec novelagent-backend-1 pytest -v` 全部通过 |
| 手工测试 | 灵感页点击"开始规划"，验证人物列表完整、关系正常 |

---

## 风险评估

| 风险 | 严重程度 | 缓解措施 |
|------|----------|----------|
| LLM 调用失败导致人物为空 | 低 | 独立 prompt 更专注，稳定性高于"顺带写人物" |
| 大纲 prompt 简化后质量下降 | 低 | 移除人物板块减少 prompt 复杂度，大纲质量应提升 |
| 旧项目数据兼容 | 低 | `parse_outline()` 保留 `_parse_characters_section()`，旧大纲仍有 `outline.characters` 字段 |
| 额外 LLM 调用增加延迟 | 低 | 单次调用约 2-5 秒，仅在规划阶段执行一次 |
| prompt 迁移 | 低 | 前端设置页自动注册 `character_generation`，用户可自定义 |