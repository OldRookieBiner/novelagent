# Prompt 与上下文传递优化 Phase 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 3 个 P0 级数据丢失问题（关系字段不匹配、字数变量缺失、章节大纲缺上下文）和 1 个 LangGraph 合规问题（Prompt 加载不一致）。

**Architecture:** 纯函数修复为主，不改架构。Fix 1/2/3 修复数据流断点，Fix 4 统一 Prompt 加载方式。每项修复独立可测。

**Tech Stack:** Python 3.11+ / FastAPI / LangGraph / React 18 + TypeScript

---

## File Structure

| File | Change | Responsibility |
|------|--------|---------------|
| `backend/app/agents/nodes/utils.py` | Modify | Fix 1: format_relations_info 兼容两种字段命名；Fix 2: parse_words_per_chapter 改为返回 (min_words, display) |
| `backend/app/agents/nodes/chapter_generation.py` | Modify | Fix 2: 字数机制改为最低字数；Fix 3: 章节大纲补全上下文；Fix 4: Prompt 加载改为 state["_prompts"] |
| `backend/app/agents/prompts.py` | Modify | Fix 2: GENERATE_CHAPTER_CONTENT_PROMPT 改为 {min_words}/{suggested_max}；Fix 3: GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT 增加 characters/world_setting/emotional_curve |
| `frontend/src/lib/inspiration.ts` | Modify | Fix 2: wordsPerChapter 选项改为单一数字 |
| `backend/tests/test_nodes_utils.py` | Modify | 更新 parse_words_per_chapter 测试适配新返回值；增加 format_relations_info ID→名字映射测试 |

---

### Task 1: Fix format_relations_info — 兼容两种字段命名

**Files:**
- Modify: `backend/app/agents/nodes/utils.py:53-65`
- Modify: `backend/tests/test_nodes_utils.py:146-215`

- [ ] **Step 1: 写失败测试 — 验证 ID→名字映射**

在 `test_nodes_utils.py` 的 `TestFormatRelationsInfo` 类中增加测试：

```python
def test_relations_with_id_based_fields(self):
    """关系数据使用 character_a_id/character_b_id/relation_type/current_status 时应正确解析"""
    state = {
        "characters": [
            {"id": 1, "name": "林风", "role": "主角"},
            {"id": 2, "name": "苏瑶", "role": "女主"},
        ],
        "relations": [
            {
                "character_a_id": 1,
                "character_b_id": 2,
                "relation_type": "师徒",
                "current_status": "青梅竹马",
            }
        ],
    }
    result = format_relations_info(state, 1)

    assert "【人物关系】" in result
    assert "林风 与 苏瑶：师徒（青梅竹马）" in result

def test_relations_mixed_field_formats(self):
    """两种字段命名混合时，有 character1/character2 优先使用"""
    state = {
        "characters": [
            {"id": 1, "name": "林风"},
        ],
        "relations": [
            {
                "character1": "张三",
                "character2": "李四",
                "relationship_type": "敌对",
                "character_a_id": 1,
                "character_b_id": 2,
                "relation_type": "合作",
                "description": "表面合作",
                "current_status": "暗中对抗",
            }
        ],
    }
    result = format_relations_info(state, 1)

    # character1/character2 优先于 ID 映射
    assert "张三 与 李四：敌对（表面合作）" in result

def test_relations_id_fields_without_characters(self):
    """关系数据只有 ID 但 characters 为空时，应显示未知"""
    state = {
        "characters": [],
        "relations": [
            {
                "character_a_id": 1,
                "character_b_id": 2,
                "relation_type": "敌对",
                "current_status": "不共戴天",
            }
        ],
    }
    result = format_relations_info(state, 1)

    assert "未知 与 未知：敌对（不共戴天）" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestFormatRelationsInfo -v`
Expected: 新测试 FAIL（character_a_id 字段无法解析出名字）

- [ ] **Step 3: 实现 format_relations_info 修复**

替换 `backend/app/agents/nodes/utils.py` 中的 `format_relations_info` 函数：

```python
def format_relations_info(state: dict, current_chapter: int) -> str:
    """格式化人物关系为提示词用字符串

    兼容两种字段命名：
    - 旧格式：character1/character2/relationship_type/description
    - 新格式：character_a_id/character_b_id/relation_type/current_status
    """
    relations = state.get("relations", [])
    if not relations:
        return ""

    # 构建 ID→名字映射（解决关系数据只有 ID 没有名字的问题）
    characters = state.get("characters", [])
    id_to_name = {c.get("id"): c.get("name", "") for c in characters if c.get("id")}

    relations_str = "\n【人物关系】\n"
    for r in relations:
        # 兼容两种字段命名：旧格式优先
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

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestFormatRelationsInfo -v`
Expected: 所有测试 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/utils.py backend/tests/test_nodes_utils.py
git commit -m "fix(workflow): format_relations_info compatibility with ID-based relation fields"
```

---

### Task 2: Fix parse_words_per_chapter — 改为返回最低字数

**Files:**
- Modify: `backend/app/agents/nodes/utils.py:113-167`
- Modify: `backend/tests/test_nodes_utils.py:343-399`

- [ ] **Step 1: 写失败测试 — 验证新返回格式**

替换 `test_nodes_utils.py` 中 `TestParseWordsPerChapter` 类的所有测试：

```python
class TestParseWordsPerChapter:
    """测试解析每章最低字数"""

    def test_range_format_backward_compat(self):
        """旧 range 格式应取下限作为最低字数"""
        min_words, display = parse_words_per_chapter({"wordsPerChapter": "2000-2500"})
        assert min_words == 2000
        assert display == "2000字起"

    def test_new_single_number_format(self):
        """新格式：纯数字应为最低字数"""
        min_words, display = parse_words_per_chapter({"wordsPerChapter": "3000"})
        assert min_words == 3000
        assert display == "3000字起"

    def test_custom_format(self):
        """自定义字数应直接作为最低字数"""
        min_words, display = parse_words_per_chapter({
            "wordsPerChapter": "custom",
            "customWordsPerChapter": 3000
        })
        assert min_words == 3000
        assert display == "3000字起"

    def test_custom_without_value(self):
        """自定义模式但无值时应使用默认值"""
        min_words, display = parse_words_per_chapter({
            "wordsPerChapter": "custom"
        })
        assert min_words == 3000
        assert "字" in display

    def test_empty_words_per_chapter(self):
        """空值应使用默认值"""
        min_words, display = parse_words_per_chapter({})
        assert min_words == 3000

    def test_invalid_format(self):
        """无效字符串应使用默认值"""
        min_words, display = parse_words_per_chapter({"wordsPerChapter": "abc"})
        assert min_words == 3000

    def test_none_collected_info(self):
        """None 输入应使用默认值"""
        min_words, display = parse_words_per_chapter(None)
        assert min_words == 3000
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestParseWordsPerChapter -v`
Expected: FAIL（旧函数返回 3 元组）

- [ ] **Step 3: 实现 parse_words_per_chapter 修复**

替换 `backend/app/agents/nodes/utils.py` 中的 `parse_words_per_chapter` 函数：

```python
def parse_words_per_chapter(collected_info: dict | None) -> tuple[int, str]:
    """解析每章最低字数

    新格式返回 (min_words, display_text)，不再返回上下限区间。
    兼容旧 range 格式 "2000-2500"，取下限作为最低字数。

    Args:
        collected_info: 灵感采集信息字典

    Returns:
        (最低字数, 显示文本)
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

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestParseWordsPerChapter -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/utils.py backend/tests/test_nodes_utils.py
git commit -m "refactor(utils): parse_words_per_chapter returns min_words instead of range"
```

---

### Task 3: Fix chapter_generation — 适配最低字数机制

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py:78-222`
- Modify: `backend/app/agents/nodes/chapter_generation.py:295-356`
- Modify: `backend/app/agents/nodes/chapter_generation.py:375-493`

- [ ] **Step 1: 修改 parse_single_chapter_outline 签名 — 只保底不封顶**

只修改函数签名、docstring 和尾部钳制逻辑，中间解析代码（第 105-168 行 Extract title 到 Extract ending）不变：

1. 第 81 行 `words_per_chapter_range: tuple[int, int] | None = None` → `min_words: int | None = None`
2. 第 88 行 docstring `words_per_chapter_range: 每章字数区间 (下限, 上限)，用于钳制 target_words` → `min_words: 每章最低字数，用于保底 target_words`
3. 第 170-176 行替换钳制逻辑：

```python
    # 只保底，不封顶：确保 target_words 不低于用户设定的最低字数
    if min_words and chapter["target_words"] < min_words:
        chapter["target_words"] = min_words
```

- [ ] **Step 2: 修改 generate_single_chapter_outline — 使用新返回值**

```python
async def generate_single_chapter_outline(
    state: NovelState,
    chapter_number: int,
    llm: LLMService,
    previous_chapters: list[dict] = None
) -> dict:
    """Generate a single chapter outline"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    plot_points_str = "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)]) if plot_points else "无"

    chapter_count = state.get("chapter_count", 10)

    # 获取每章最低字数
    collected_info = state.get("collected_info", {})
    min_words, _ = parse_words_per_chapter(collected_info)

    # Build previous chapters info for context
    previous_info = ""
    if previous_chapters and len(previous_chapters) > 0:
        # Only show last 3 chapters for context
        recent = previous_chapters[-3:]
        previous_info = "前几章概要：\n" + "\n".join([
            f"- 第{c['chapter_number']}章《{c.get('title', '')}》：{c.get('plot', '')[:50]}..."
            for c in recent
        ])

    prompt = GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT.format(
        outline=outline,
        plot_points=plot_points_str,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
    )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    return parse_single_chapter_outline(response, chapter_number, min_words)
```

- [ ] **Step 3: 修改 generate_chapter_content_stream — 适配最低字数**

```python
async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """生成章节内容（流式，增强版）"""

    info = state.get("collected_info", {})

    # 格式化章节大纲（使用共享工具函数）
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)

    # 格式化人物关系（使用共享工具函数）
    relations_str = format_relations_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化人物演变历史（使用共享工具函数）
    evolution_str, evolution_plans_str = format_evolution_info(state, chapter_outline.get("chapter_number", 1))

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)

    # 合并人物设定、关系和演变信息
    combined_characters_str = chars_str + relations_str + evolution_str + evolution_plans_str

    # 获取每章最低字数
    min_words, _ = parse_words_per_chapter(info)
    suggested_max = int(min_words * 1.5)

    # 获取前章结尾用于衔接
    previous_ending = ""
    written_chapters = state.get("written_chapters", [])
    chapter_number = chapter_outline.get("chapter_number", 1)
    if written_chapters:
        for ch in written_chapters:
            if ch.get("chapter_number") == chapter_number - 1:
                ch_content = ch.get("content", "")
                previous_ending = ch_content[-500:] if len(ch_content) > 500 else ch_content
                break

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

    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    ):
        yield chunk
```

- [ ] **Step 4: 修改 generate_chapter_content_node — 适配最低字数**

```python
async def generate_chapter_content_node(state: NovelState) -> NovelState:
    """LangGraph 兼容的章节内容生成节点"""

    llm = await get_llm_from_state_async(state)

    current_chapter = state.get("current_chapter", 1)
    chapter_outlines = state.get("chapter_outlines", [])
    written_chapters = state.get("written_chapters", [])

    chapter_outline = None
    for outline in chapter_outlines:
        if outline.get("chapter_number") == current_chapter:
            chapter_outline = outline
            break

    if not chapter_outline:
        chapter_count = state.get("chapter_count", 0)
        raise ValueError(
            f"章节大纲未找到：第 {current_chapter} 章（共 {chapter_count} 章，"
            f"已生成 {len(chapter_outlines)} 个章节大纲）"
        )

    # 获取上一章的结尾用于衔接
    previous_ending = ""
    if written_chapters:
        for chapter in written_chapters:
            if chapter.get("chapter_number") == current_chapter - 1:
                content = chapter.get("content", "")
                previous_ending = content[-500:] if len(content) > 500 else content
                break

    info = state.get("collected_info", {})

    # 获取每章最低字数
    min_words, _ = parse_words_per_chapter(info)
    suggested_max = int(min_words * 1.5)

    outline_str = _format_chapter_outline_str(chapter_outline)
    chars_str = format_characters_info(state)
    relations_str = format_relations_info(state, chapter_outline.get("chapter_number", 1))
    evolution_str, _ = format_evolution_info(state, chapter_outline.get("chapter_number", 1))
    world_str = format_world_setting(state)
    combined_characters_str = chars_str + relations_str + evolution_str

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

    content = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    ):
        content += chunk

    content = clean_chapter_content(content)
    word_count = len(content)

    new_chapter = {
        "chapter_number": current_chapter,
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": word_count
    }

    new_state: NovelState = {
        **state,
        "written_chapters": [new_chapter],
        "current_chapter": current_chapter + 1,
        "stage": STAGE_WRITING,
    }

    return new_state
```

- [ ] **Step 5: 移除顶部不再使用的硬编码 import**

将 `chapter_generation.py` 顶部的：
```python
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
)
```
改为只在函数内部需要时通过 `state["_prompts"]` 或 `DEFAULT_PROMPTS` 获取。但这步和 Fix 4 合并，暂不删除。

- [ ] **Step 6: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: PASS（注意 parse_words_per_chapter 返回值已变，需确认 outline_generation.py 不受影响）

- [ ] **Step 7: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "refactor(chapter): adapt to min_words mechanism instead of range clamping"
```

---

### Task 4: Fix GENERATE_CHAPTER_CONTENT_PROMPT — 改为最低字数指令

**Files:**
- Modify: `backend/app/agents/prompts.py:146-230`

- [ ] **Step 1: 修改 Prompt 模板**

在 `prompts.py` 中，将 `GENERATE_CHAPTER_CONTENT_PROMPT` 的两处 `{target_words}` 替换：

将：
```
- 本章目标字数：{target_words} 字
```
改为：
```
- 本章最低字数：{min_words} 字（建议不超过 {suggested_max} 字，完整性优先）
```

将：
```
确认全部通过后，请直接输出章节正文，字数约 {target_words} 字。
不要输出自检清单，不要输出任何解释说明。
```
改为：
```
确认全部通过后，请直接输出章节正文，字数不低于 {min_words} 字，情节完整比字数更重要。
不要输出自检清单，不要输出任何解释说明。
```

- [ ] **Step 2: 验证 Prompt 模板中不再有 {target_words}**

Run: `grep -n "target_words" backend/app/agents/prompts.py`
Expected: 无匹配（review 和 rewrite 模板中不使用此变量）

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/prompts.py
git commit -m "fix(prompt): replace target_words with min_words/suggested_max in chapter content prompt"
```

---

### Task 5: Fix GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT — 增加上下文变量

**Files:**
- Modify: `backend/app/agents/prompts.py:74-141`
- Modify: `backend/app/agents/nodes/chapter_generation.py:181-222`

- [ ] **Step 1: 修改 Prompt 模板，增加人物/世界观/情感曲线区域**

在 `prompts.py` 的 `GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT` 中，在 `## 主要情节节点及伏笔状态` 和 `## 当前进度` 之间插入：

```
## 人物设定
{characters}

## 世界观
{world_setting}

## 情感曲线
{emotional_curve}
```

完整位置：在 `{plot_points}` 块之后、`## 当前进度` 之前。

- [ ] **Step 2: 修改 generate_single_chapter_outline — 传入新上下文**

在 `chapter_generation.py` 的 `generate_single_chapter_outline` 函数中，在 `previous_info` 构建之后、`prompt = ...` 之前，增加：

```python
    # 格式化人物设定（使用共享工具函数）
    chars_str = format_characters_info(state)

    # 格式化世界观（使用共享工具函数）
    world_str = format_world_setting(state)

    # 获取情感曲线
    emotional_curve = state.get("outline_emotional_curve", "") or "未提供"
```

修改 `.format()` 调用：

```python
    prompt = GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT.format(
        outline=outline,
        plot_points=plot_points_str,
        characters=chars_str,
        world_setting=world_str,
        emotional_curve=emotional_curve,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
    )
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/chapter_generation.py
git commit -m "fix(chapter): add characters/world_setting/emotional_curve context to chapter outline prompt"
```

---

### Task 6: Fix chapter_generation Prompt 加载 — 改为 state["_prompts"]

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py:1-20` (imports)
- Modify: `backend/app/agents/nodes/chapter_generation.py:181-222` (generate_single_chapter_outline)
- Modify: `backend/app/agents/nodes/chapter_generation.py:295-356` (generate_chapter_content_stream)
- Modify: `backend/app/agents/nodes/chapter_generation.py:375-493` (generate_chapter_content_node)

- [ ] **Step 1: 移除顶部硬编码 Prompt import**

将 `chapter_generation.py` 顶部的：
```python
from app.agents.prompts import (
    GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
)
```
删除。

- [ ] **Step 2: 修改 generate_single_chapter_outline — 从 state["_prompts"] 加载**

在函数内部，替换直接使用 `GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT`：

```python
    # 从 state 获取预加载的 prompts（LangGraph 合规）
    prompts = state.get("_prompts", {})
    if prompts and "chapter_outline_generation" in prompts:
        prompt_template = prompts["chapter_outline_generation"]
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_template = DEFAULT_PROMPTS.get("chapter_outline_generation", "")

    prompt = prompt_template.format(
        outline=outline,
        plot_points=plot_points_str,
        characters=chars_str,
        world_setting=world_str,
        emotional_curve=emotional_curve,
        chapter_count=chapter_count,
        chapter_number=chapter_number,
        previous_chapters_info=previous_info,
    )
```

- [ ] **Step 3: 修改 generate_chapter_content_stream — 从 state["_prompts"] 加载**

替换直接使用 `GENERATE_CHAPTER_CONTENT_PROMPT`：

```python
    # 从 state 获取预加载的 prompts（LangGraph 合规）
    prompts = state.get("_prompts", {})
    if prompts and "chapter_content_generation" in prompts:
        prompt_template = prompts["chapter_content_generation"]
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_template = DEFAULT_PROMPTS.get("chapter_content_generation", "")

    prompt = prompt_template.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        min_words=min_words,
        suggested_max=suggested_max,
    )
```

- [ ] **Step 4: 修改 generate_chapter_content_node — 从 state["_prompts"] 加载**

与 Step 3 相同模式，替换 `GENERATE_CHAPTER_CONTENT_PROMPT`：

```python
    # 从 state 获取预加载的 prompts（LangGraph 合规）
    prompts = state.get("_prompts", {})
    if prompts and "chapter_content_generation" in prompts:
        prompt_template = prompts["chapter_content_generation"]
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_template = DEFAULT_PROMPTS.get("chapter_content_generation", "")

    prompt = prompt_template.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        min_words=min_words,
        suggested_max=suggested_max,
    )
```

- [ ] **Step 5: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "refactor(chapter): load prompts from state['_prompts'] for LangGraph compliance"
```

---

### Task 7: Fix 前端灵感选项 — 改为单一数字

**Files:**
- Modify: `frontend/src/lib/inspiration.ts:95-101`

- [ ] **Step 1: 修改 wordsPerChapter 选项**

替换 `inspiration.ts` 中的 `wordsPerChapter` 选项：

```typescript
wordsPerChapter: [
  { value: '2000', label: '2000字起', desc: '短章' },
  { value: '3000', label: '3000字起', desc: '标准·番茄推荐' },
  { value: '4000', label: '4000字起', desc: '中章·七猫推荐' },
  { value: '5000', label: '5000字起', desc: '长章' },
  { value: 'custom', label: '自定义' },
],
```

- [ ] **Step 2: 更新 getWordsPerChapterDisplay 函数**

`getWordsPerChapterDisplay` 函数已能处理新格式（`find(o => o.value === data.wordsPerChapter)` 匹配 value='3000'），无需修改。验证一下：

Run: `cd frontend && npm run test:run -- src/lib/inspiration.test 2>/dev/null || echo "No test file, skip"`

- [ ] **Step 3: 更新 parseTemplateToData 中的每章字数解析**

`parseTemplateToData` 中匹配 `**每章字数**` 的逻辑已能处理新格式（如"3000字起" → 匹配数字 → `wordsPerChapter: 'custom'` + `customWordsPerChapter: 3000`）。

但新格式的 value 是 `'3000'`，应该直接匹配选项而非走 custom。修改解析逻辑：

```typescript
    if (line.includes('**每章字数**')) {
      const value = line.split('：')[1]?.trim()
      const option = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.label === value)
      if (option) data.wordsPerChapter = option.value
      else if (value && value !== '未设置') {
        // 兼容旧格式 "2000-2500字" 和新格式 "3000字起"
        const numMatch = value.match(/(\d+)/)
        if (numMatch) {
          const numVal = parseInt(numMatch[1])
          // 检查是否匹配预设选项的 value
          const presetOption = INSPIRATION_OPTIONS.wordsPerChapter.find(o => o.value === String(numVal))
          if (presetOption) {
            data.wordsPerChapter = presetOption.value
          } else {
            data.wordsPerChapter = 'custom'
            data.customWordsPerChapter = numVal
          }
        }
      }
    }
```

- [ ] **Step 4: 更新 QUICK_TEMPLATES 中的 wordsPerChapter 值**

将快捷模板中的 `wordsPerChapter` 从旧格式（如 `'option_3000'`）改为新格式：

```typescript
// wuxia 模板
wordsPerChapter: '3000',
// romance 模板
wordsPerChapter: '3000',
// scifi 模板
wordsPerChapter: '3000',
```

- [ ] **Step 5: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/lib/inspiration.ts
git commit -m "feat(inspiration): change wordsPerChapter options from range to minimum value"
```

---

### Task 8: 全量验证与清理

**Files:** 无新增修改

- [ ] **Step 1: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: 全部 PASS

- [ ] **Step 3: 检查 outline_generation.py 是否受 parse_words_per_chapter 返回值变更影响**

`outline_generation.py` 有自己的内联 `wordsPerChapter` 解析逻辑（第 452-464 行），不调用 `parse_words_per_chapter()`。确认无影响：

Run: `grep -n "parse_words_per_chapter" backend/app/agents/nodes/outline_generation.py`
Expected: 只有 import 行，无实际调用

- [ ] **Step 4: 检查其他调用 parse_words_per_chapter 的位置**

Run: `grep -rn "parse_words_per_chapter" backend/ --include="*.py" | grep -v test | grep -v "__pycache__"`
Expected: 只在 utils.py（定义）和 chapter_generation.py（使用）中

- [ ] **Step 5: 构建并重启后端验证**

Run: `docker compose build --no-cache backend && docker compose up -d backend`
Expected: 构建成功，服务正常启动

- [ ] **Step 6: 更新 anatomy.md 和 memory.md**

Run: (手动记录变更到 .wolf/anatomy.md 和 .wolf/memory.md)
