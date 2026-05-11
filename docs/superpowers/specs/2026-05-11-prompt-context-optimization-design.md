# Prompt 质量与上下文传递优化 — Phase 1 设计文档

## 背景

当前提示词系统存在 3 个 P0 级数据丢失问题，直接导致生成质量下降，以及 1 个 LangGraph 合规问题导致用户自定义 Prompt 不生效。

## 评估得分（优化前）

| 维度 | 得分 |
|------|------|
| Prompt 质量 | 7/10 |
| 上下文传递完整性 | 4/10 |
| Prompt 加载一致性 | 3/10 |
| 上下文利用率 | 5/10 |
| 可维护性 | 4/10 |
| **综合** | **4.6/10** |

---

## 修复项

### Fix 1：关系字段不匹配 — 关系信息在章节生成中完全丢失

**问题：** `format_relations_info()` 读取 `character1/character2/description` 字段，但 `build_initial_state()` 写入的是 `character_a_id/character_b_id/current_status`。字段名不匹配导致所有关系信息为空。

**修改文件：** `backend/app/agents/nodes/utils.py`

**修改方案：**

`format_relations_info()` 增加 ID→名字映射，兼容两种字段命名：

```python
def format_relations_info(state: dict, current_chapter: int) -> str:
    relations = state.get("relations", [])
    if not relations:
        return ""

    # 构建 ID→名字映射（解决关系数据只有 ID 没有名字的问题）
    characters = state.get("characters", [])
    id_to_name = {c.get("id"): c.get("name", "") for c in characters if c.get("id")}

    relations_str = "\n【人物关系】\n"
    for r in relations:
        # 兼容两种字段命名
        name_a = r.get("character1") or id_to_name.get(r.get("character_a_id"), "未知")
        name_b = r.get("character2") or id_to_name.get(r.get("character_b_id"), "未知")
        rel_type = r.get("relationship_type") or r.get("relation_type", "")
        desc = r.get("description") or r.get("current_status", "")

        relations_str += f"- {name_a} 与 {name_b}：{rel_type}"
        if desc:
            relations_str += f"（{desc}）"
        relations_str += "\n"
    return relations_str
```

### Fix 2：每章字数从"范围钳制"改为"最低字数"机制

**问题：**
1. Prompt 模板用 `{target_words}`，但 `.format()` 调用未传入此变量
2. 当前范围钳制（如 2000-2500 字）会强制截断 LLM 认为需要更多篇幅的章节，导致仓促收尾
3. "最低字数"比"范围"更贴合小说写作实际——保底但不封顶

**修改文件：**
- `backend/app/agents/nodes/utils.py` — `parse_words_per_chapter()`
- `backend/app/agents/nodes/chapter_generation.py` — `parse_single_chapter_outline()`、`generate_chapter_content_stream()`、`generate_chapter_content_node()`
- `backend/app/agents/prompts.py` — `GENERATE_CHAPTER_CONTENT_PROMPT`
- `frontend/src/lib/inspiration.ts` — `wordsPerChapter` 选项

**2a. 前端选项改为单一数字：**

```typescript
wordsPerChapter: [
  { value: '2000', label: '2000字起', desc: '短章' },
  { value: '3000', label: '3000字起', desc: '标准·番茄推荐' },
  { value: '4000', label: '4000字起', desc: '中章·七猫推荐' },
  { value: '5000', label: '5000字起', desc: '长章' },
  { value: 'custom', label: '自定义' },
],
```

**2b. 后端解析函数改为返回最低字数：**

```python
def parse_words_per_chapter(collected_info: dict | None) -> tuple[int, str]:
    """解析每章最低字数

    Returns:
        (min_words, display_text)
    """
    DEFAULT_MIN = 3000
    DEFAULT_DISPLAY = "3000字起"

    if not collected_info:
        return DEFAULT_MIN, DEFAULT_DISPLAY

    wpc_str = collected_info.get("wordsPerChapter", "")
    custom_val = collected_info.get("customWordsPerChapter")

    # custom 模式
    if wpc_str == "custom":
        if custom_val and isinstance(custom_val, int) and custom_val > 0:
            return custom_val, f"{custom_val}字起"
        return DEFAULT_MIN, DEFAULT_DISPLAY

    # 纯数字格式（新格式）
    if wpc_str:
        try:
            val = int(wpc_str)
            if val > 0:
                return val, f"{val}字起"
        except (ValueError, TypeError):
            pass

    # 兼容旧数据：range 格式 "2000-2500"，取下限作为最低字数
    if "-" in str(wpc_str):
        try:
            lower = int(str(wpc_str).split("-")[0].strip())
            if lower > 0:
                return lower, f"{lower}字起"
        except (ValueError, IndexError):
            pass

    return DEFAULT_MIN, DEFAULT_DISPLAY
```

**2c. 章节大纲预计字数只保底不封顶：**

`parse_single_chapter_outline()` 签名变更：`words_per_chapter_range: tuple[int, int] | None` → `min_words: int | None`

```python
# parse_single_chapter_outline() 中
# 改前：钳制到 [lower, upper]
if words_per_chapter_range:
    lower, upper = words_per_chapter_range
    if chapter["target_words"] < lower:
        chapter["target_words"] = lower
    elif chapter["target_words"] > upper:
        chapter["target_words"] = upper  # ← 上限钳制

# 改后：只保底，不封顶
if min_words and chapter["target_words"] < min_words:
    chapter["target_words"] = min_words
```

调用方 `generate_single_chapter_outline()` 也需相应更新：用 `parse_words_per_chapter()` 返回的 `min_words` 替代原来的 `words_per_chapter_range`。

**2d. Prompt 模板改为最低字数指令：**

```
# 改前
- 本章目标字数：{target_words} 字
...
字数约 {target_words} 字。

# 改后
- 本章最低字数：{min_words} 字（建议不超过 {suggested_max} 字，完整性优先）
...
字数不低于 {min_words} 字，情节完整比字数更重要。
```

**2e. max_tokens 按最低字数的 2 倍计算：**

```python
# generate_chapter_content_stream / generate_chapter_content_node
min_words, _ = parse_words_per_chapter(info)
suggested_max = int(min_words * 1.5)

# 优先用章节大纲的 target_words（已保底），回退到用户设定的最低字数
target_words = chapter_outline.get("target_words") or min_words

prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
    chapter_outline=outline_str,
    previous_ending=previous_ending,
    genre=info.get("novelType", "未指定"),
    main_characters=combined_characters_str,
    world_setting=world_str,
    style_preference=info.get("stylePreference", "未指定"),
    min_words=min_words,
    suggested_max=suggested_max,
)

# max_tokens 按最低字数的 2 倍计算，给充足空间
max_tokens = _calc_max_tokens(min_words * 2)
```

**向后兼容：** 旧项目已保存的 `wordsPerChapter: "2000-2500"` 格式，`parse_words_per_chapter` 取下限作为最低字数。无需数据库迁移。

### Fix 3：章节大纲生成缺少人物/世界观/情感曲线上下文

**问题：** `generate_single_chapter_outline()` 只传入 outline、plot_points、chapter_count、chapter_number，缺少 characters、world_setting、emotional_curve。LLM 在不知道角色和世界观的情况下生成章节大纲，情节节点可能无法正确对应角色弧线。

**修改文件：**
- `backend/app/agents/nodes/chapter_generation.py` — `generate_single_chapter_outline()`
- `backend/app/agents/prompts.py` — `GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT`

**3a. 节点函数补充上下文：**

```python
# generate_single_chapter_outline() 中补充
chars_str = format_characters_info(state)
world_str = format_world_setting(state)
emotional_curve = state.get("outline_emotional_curve", "")

prompt = GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT.format(
    outline=outline,
    plot_points=plot_points_str,
    chapter_count=chapter_count,
    chapter_number=chapter_number,
    previous_chapters_info=previous_info,
    characters=chars_str,            # ← 新增
    world_setting=world_str,         # ← 新增
    emotional_curve=emotional_curve, # ← 新增
)
```

**3b. Prompt 模板增加对应区域：**

在 `## 小说整体大纲` 和 `## 当前进度` 之间增加：

```
## 人物设定
{characters}

## 世界观
{world_setting}

## 情感曲线
{emotional_curve}
```

### Fix 4：chapter_generation Prompt 加载改为 state["_prompts"]（LangGraph 合规）

**问题：** `chapter_generation.py` 硬编码 `from prompts import GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT`，不走 `get_system_prompt()` 也不走 `state["_prompts"]`，用户在设置页面修改 Prompt 不生效。违反 LangGraph 架构约束。

**修改文件：** `backend/app/agents/nodes/chapter_generation.py`

**修改方案：** 与 `character_generation.py`、`relation_generation.py` 保持一致，优先从 `state["_prompts"]` 获取，回退到 `DEFAULT_PROMPTS`：

```python
# generate_single_chapter_outline() 中
prompts = state.get("_prompts", {})

if prompts and "chapter_outline_generation" in prompts:
    prompt_template = prompts["chapter_outline_generation"]
else:
    from app.agents.prompts import DEFAULT_PROMPTS
    prompt_template = DEFAULT_PROMPTS.get("chapter_outline_generation", "")

prompt = prompt_template.format(
    outline=outline,
    plot_points=plot_points_str,
    chapter_count=chapter_count,
    chapter_number=chapter_number,
    previous_chapters_info=previous_info,
    characters=chars_str,
    world_setting=world_str,
    emotional_curve=emotional_curve,
)
```

同样，章节正文生成也需改为从 `state["_prompts"]` 加载 `chapter_content_generation`。

---

## 不在 Phase 1 范围的内容

| 项目 | 原因 | 归属 |
|------|------|------|
| rewrite 节点 Prompt 加载统一 | 不影响生成质量，属 P1 | Phase 2 |
| 禁用词表抽取为共享常量 | 不影响生成质量，属 P2 可维护性 | Phase 2 |
| System Message 机制 | 架构变动较大 | Phase 3 |
| 前文摘要（3-5 章概要） | 需设计摘要生成机制 | Phase 3 |
| Prompt 格式与解析正则强绑定 | 需重新设计解析器 | Phase 3 |

---

## 影响范围

| 文件 | 改动类型 | 风险 |
|------|---------|------|
| `backend/app/agents/nodes/utils.py` | 修改 `format_relations_info`、`parse_words_per_chapter` | 低：纯函数，有测试 |
| `backend/app/agents/nodes/chapter_generation.py` | 修改 3 个函数 | 中：核心生成逻辑 |
| `backend/app/agents/prompts.py` | 修改 2 个模板，增加占位变量 | 低：仅模板文本 |
| `frontend/src/lib/inspiration.ts` | 修改选项列表 | 低：纯配置 |
| `backend/app/agents/nodes/review.py` | 无改动（review 的 parse_review_result 中有 `AI味程度` 正则，需确认与模板匹配） | — |

## 验证方案

1. 运行现有测试：`docker exec novelagent-backend-1 pytest -v`
2. 手动测试：创建新项目 → 选择每章字数 → 生成大纲 → 生成章节 → 检查：
   - 章节正文中人物关系信息是否出现
   - 章节字数是否不低于用户设定的最低值
   - 章节大纲是否包含人物设定和世界观信息
3. 向后兼容测试：使用旧格式 `wordsPerChapter: "2000-2500"` 的项目，确认章节数正确
