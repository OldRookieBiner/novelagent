# 章节字数统一优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一使用灵感页面的"每章字数"区间作为章节大纲和正文生成的字数约束，修复 range 解析 bug。

**Architecture:** 在 utils.py 新增 `parse_words_per_chapter` 统一解析函数，章节大纲生成 prompt 注入字数约束，大纲解析时钳制 target_words，正文生成使用区间格式替代单一 target_words。所有改动在 LangGraph 节点层面完成，不修改数据库模型和工作流连接。

**Tech Stack:** Python, LangGraph, Pytest

---

### Task 1: 新增 parse_words_per_chapter 工具函数 + 测试

**Files:**
- Modify: `backend/app/agents/nodes/utils.py` (追加函数)
- Modify: `backend/tests/test_nodes_utils.py` (追加测试类)

- [ ] **Step 1: 写失败的测试**

在 `backend/tests/test_nodes_utils.py` 末尾追加：

```python
from app.agents.nodes.utils import parse_words_per_chapter


class TestParseWordsPerChapter:
    """测试解析每章字数区间"""

    def test_range_format(self):
        """range 格式应正确解析上下限"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "2000-2500"})
        assert lower == 2000
        assert upper == 2500
        assert display == "2000-2500字"

    def test_custom_format(self):
        """自定义字数应上下浮动 10%"""
        lower, upper, display = parse_words_per_chapter({
            "wordsPerChapter": "custom",
            "customWordsPerChapter": 3000
        })
        assert lower == 2700
        assert upper == 3300
        assert display == "约3000字"

    def test_custom_without_value(self):
        """自定义模式但无值时应使用默认值"""
        lower, upper, display = parse_words_per_chapter({
            "wordsPerChapter": "custom"
        })
        assert lower == 2000
        assert upper == 3000
        assert "字" in display

    def test_empty_words_per_chapter(self):
        """空值应使用默认值"""
        lower, upper, display = parse_words_per_chapter({})
        assert lower == 2000
        assert upper == 3000

    def test_invalid_range_format(self):
        """无效的 range 字符串应使用默认值"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "abc"})
        assert lower == 2000
        assert upper == 3000

    def test_single_number_range(self):
        """纯数字字符串（非 range）应解析为上下限相同"""
        lower, upper, display = parse_words_per_chapter({"wordsPerChapter": "3000"})
        assert lower == 3000
        assert upper == 3000
        assert display == "3000字"

    def test_none_collected_info(self):
        """None 输入应使用默认值"""
        lower, upper, display = parse_words_per_chapter(None)
        assert lower == 2000
        assert upper == 3000
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestParseWordsPerChapter -v`
Expected: FAIL - ImportError: cannot import name 'parse_words_per_chapter'

- [ ] **Step 3: 实现函数**

在 `backend/app/agents/nodes/utils.py` 末尾追加：

```python
def parse_words_per_chapter(collected_info: dict | None) -> tuple[int, int, str]:
    """解析每章字数区间

    统一处理灵感页面 wordsPerChapter 字段的三种格式：
    - range 格式："2000-2500" → (2000, 2500, "2000-2500字")
    - custom 格式：需要 customWordsPerChapter，上下浮动 10%
    - 空值/无效值：返回默认区间 (2000, 3000, "2000-3000字")

    Args:
        collected_info: 灵感采集信息字典

    Returns:
        (下限, 上限, 显示文本)
    """
    DEFAULT_LOWER = 2000
    DEFAULT_UPPER = 3000
    DEFAULT_DISPLAY = "2000-3000字"

    if not collected_info:
        return DEFAULT_LOWER, DEFAULT_UPPER, DEFAULT_DISPLAY

    wpc_str = collected_info.get("wordsPerChapter", "")
    custom_val = collected_info.get("customWordsPerChapter")

    # custom 模式
    if wpc_str == "custom":
        if custom_val and isinstance(custom_val, int) and custom_val > 0:
            lower = max(100, int(custom_val * 0.9))
            upper = int(custom_val * 1.1)
            return lower, upper, f"约{custom_val}字"
        return DEFAULT_LOWER, DEFAULT_UPPER, DEFAULT_DISPLAY

    # range 格式："2000-2500"
    if wpc_str and "-" in str(wpc_str):
        try:
            parts = str(wpc_str).split("-")
            lower = int(parts[0].strip())
            upper = int(parts[1].strip())
            if lower > 0 and upper > 0:
                return lower, upper, f"{lower}-{upper}字"
        except (ValueError, IndexError):
            pass
        return DEFAULT_LOWER, DEFAULT_UPPER, DEFAULT_DISPLAY

    # 纯数字格式："3000"
    if wpc_str:
        try:
            val = int(wpc_str)
            if val > 0:
                return val, val, f"{val}字"
        except (ValueError, TypeError):
            pass

    return DEFAULT_LOWER, DEFAULT_UPPER, DEFAULT_DISPLAY
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_nodes_utils.py::TestParseWordsPerChapter -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/utils.py backend/tests/test_nodes_utils.py
git commit -m "feat(workflow): add parse_words_per_chapter utility function"
```

---

### Task 2: 修复 outline_generation.py 的 range 解析 bug

**Files:**
- Modify: `backend/app/agents/nodes/outline_generation.py:433-465`

- [ ] **Step 1: 修改 prepare_outline_prompt 使用 parse_words_per_chapter**

在 `backend/app/agents/nodes/outline_generation.py` 顶部追加 import：

```python
from app.agents.nodes.utils import parse_words_per_chapter
```

替换 `prepare_outline_prompt` 函数中第 445-465 行的字数解析逻辑（从 `# 获取目标字数和每章字数` 到 `chapter_count = DEFAULT_CHAPTER_COUNT`）为：

```python
        # 获取目标字数
        target_words = collected_info.get("targetWords", 100000)

        # 使用统一解析函数获取每章字数区间
        words_lower, words_upper, _ = parse_words_per_chapter(collected_info)
        words_per_chapter = (words_lower + words_upper) // 2  # 区间中值用于计算章节数

        # 根据目标字数和每章字数计算章节数
        if isinstance(target_words, int) and target_words > 0 and words_per_chapter > 0:
            chapter_count = max(3, int(target_words / words_per_chapter))  # 最少3章
        else:
            chapter_count = DEFAULT_CHAPTER_COUNT
```

注意：此改动删除了原来手动解析 `wordsPerChapter` 的 10 行代码（第 447-459 行），替换为 3 行。原来的 `words_per_chapter_str`、`custom_words_per_chapter` 变量不再需要。

- [ ] **Step 2: 运行现有测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/nodes/outline_generation.py
git commit -m "fix(workflow): use parse_words_per_chapter for range parsing in outline generation"
```

---

### Task 3: 章节大纲 prompt 注入字数约束 + 解析时钳制

**Files:**
- Modify: `backend/app/agents/prompts.py:74-141` (GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT)
- Modify: `backend/app/agents/nodes/chapter_generation.py:77-199` (parse_single_chapter_outline + generate_single_chapter_outline)

- [ ] **Step 1: 修改章节大纲 prompt，增加 words_per_chapter 占位符**

在 `backend/app/agents/prompts.py` 中，修改 `GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT`：

1. 在 `## 当前进度` 部分后追加一行：

```
- 每章字数范围：{words_per_chapter}
```

2. 将第 128 行 `预计字数：XXXX 字` 改为：

```
预计字数：XXXX 字（必须在{words_per_chapter}范围内）
```

3. 在注意事项中追加一条：

```
7. 预计字数必须在"每章字数范围"内，不得超出该区间。
```

- [ ] **Step 2: 修改 generate_single_chapter_outline，解析字数区间并传入 prompt**

在 `backend/app/agents/nodes/chapter_generation.py` 中：

1. 在顶部追加 import：

```python
from app.agents.nodes.utils import parse_words_per_chapter
```

2. 修改 `generate_single_chapter_outline` 函数（第 163-199 行），在构建 prompt 之前获取字数区间：

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

    # 获取每章字数区间
    collected_info = state.get("collected_info", {})
    words_lower, words_upper, words_display = parse_words_per_chapter(collected_info)

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
        words_per_chapter=words_display
    )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        response += chunk

    return parse_single_chapter_outline(response, chapter_number, (words_lower, words_upper))
```

- [ ] **Step 3: 修改 parse_single_chapter_outline，增加钳制逻辑**

修改 `parse_single_chapter_outline` 函数签名和 target_words 解析部分：

```python
def parse_single_chapter_outline(
    response: str,
    chapter_number: int,
    words_per_chapter_range: tuple[int, int] | None = None
) -> dict:
    """解析单章节大纲（增强版）

    Args:
        response: AI 返回的章节大纲文本
        chapter_number: 章节号
        words_per_chapter_range: 每章字数区间 (下限, 上限)，用于钳制 target_words
    """
    chapter = {
        "chapter_number": chapter_number,
        "title": "",
        "scene": "",
        "characters": "",
        "plot": "",
        "conflict": "",
        "turning_point": "",
        "hook": "",
        "transition": "",
        "ending": "",
        "target_words": 3000
    }
```

在函数末尾，第 155-158 行的 target_words 解析之后，追加钳制逻辑：

```python
    # 解析预计字数
    words_match = re.search(r"预计字数[：:]\s*(\d+)", response)
    if words_match:
        chapter["target_words"] = int(words_match.group(1))

    # 钳制 target_words 到用户设定的每章字数区间
    if words_per_chapter_range:
        lower, upper = words_per_chapter_range
        if chapter["target_words"] < lower:
            chapter["target_words"] = lower
        elif chapter["target_words"] > upper:
            chapter["target_words"] = upper

    return chapter
```

- [ ] **Step 4: 同步修改 generate_chapter_outlines_node 中的调用**

在 `generate_chapter_outlines_node`（第 235-259 行）中，也需要获取字数区间并传递。该函数通过调用 `generate_single_chapter_outline` 间接调用 `parse_single_chapter_outline`，而 `generate_single_chapter_outline` 已经从 state 获取区间并传递，所以无需额外修改。

同样，`generate_chapter_outlines_stream`（第 202-232 行）也通过 `generate_single_chapter_outline` 间接调用，无需修改。

- [ ] **Step 5: 运行测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 6: 提交**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/chapter_generation.py
git commit -m "feat(workflow): inject words_per_chapter constraint into chapter outline prompt and clamp target_words"
```

---

### Task 4: 章节正文生成使用区间格式

**Files:**
- Modify: `backend/app/agents/prompts.py:146-230` (GENERATE_CHAPTER_CONTENT_PROMPT)
- Modify: `backend/app/agents/nodes/chapter_generation.py:272-330` (generate_chapter_content_stream)
- Modify: `backend/app/agents/nodes/chapter_generation.py:349-462` (generate_chapter_content_node)

- [ ] **Step 1: 修改章节正文 prompt**

在 `backend/app/agents/prompts.py` 中，修改 `GENERATE_CHAPTER_CONTENT_PROMPT`：

1. 将第 158 行的 `{target_words}` 替换为 `{words_per_chapter_range}`：

```
- 本章目标字数：{words_per_chapter_range}
```

2. 将最后一行（第 228 行）的 `{target_words}` 替换为 `{words_per_chapter_range}`：

```
确认全部通过后，请直接输出章节正文，字数约 {words_per_chapter_range}。
```

- [ ] **Step 2: 修改 generate_chapter_content_stream**

在 `backend/app/agents/nodes/chapter_generation.py` 中，修改 `generate_chapter_content_stream` 函数（第 272-330 行）：

替换第 299-300 行：

```python
    # 获取章节目标字数
    target_words = chapter_outline.get("target_words", 3000)
```

为：

```python
    # 获取每章字数区间（优先使用用户设定，回退到章节大纲的 target_words）
    _, _, words_display = parse_words_per_chapter(info)
    words_per_chapter_range = words_display
    # 使用区间上限计算 max_tokens，确保不截断
    target_words_for_tokens = chapter_outline.get("target_words", 3000)
```

替换第 313-324 行的 prompt 构建和 max_tokens 计算：

```python
    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        words_per_chapter_range=words_per_chapter_range
    )

    # 根据目标字数计算 max_tokens，避免截断
    max_tokens = _calc_max_tokens(target_words_for_tokens)
```

- [ ] **Step 3: 修改 generate_chapter_content_node**

在 `backend/app/agents/nodes/chapter_generation.py` 中，修改 `generate_chapter_content_node` 函数（第 349-462 行）：

替换第 416-417 行：

```python
    # 获取章节目标字数
    target_words = chapter_outline.get("target_words", 3000)
```

为：

```python
    # 获取每章字数区间（优先使用用户设定，回退到章节大纲的 target_words）
    _, _, words_display = parse_words_per_chapter(info)
    words_per_chapter_range = words_display
    # 使用区间上限计算 max_tokens，确保不截断
    target_words_for_tokens = chapter_outline.get("target_words", 3000)
```

替换第 419-430 行的 prompt 构建和 max_tokens 计算：

```python
    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending=previous_ending,
        genre=info.get("novelType", "未指定"),
        main_characters=combined_characters_str,
        world_setting=world_str,
        style_preference=info.get("stylePreference", "未指定"),
        words_per_chapter_range=words_per_chapter_range
    )

    # 根据目标字数计算 max_tokens，避免截断
    max_tokens = _calc_max_tokens(target_words_for_tokens)
```

- [ ] **Step 4: 修改 chapters.py API 中的调用**

在 `backend/app/api/chapters.py` 中搜索 `generate_chapter_content_stream` 调用。该函数签名未变（仍然接收 state, chapter_outline, llm），内部已使用 parse_words_per_chapter 从 state.collected_info 获取区间。无需修改 chapters.py。

但需确认：API 中的 `initial_state` 是否包含 `collected_info`。查看 chapters.py 中构建 initial_state 的代码，确认 `collected_info` 已包含在内。

- [ ] **Step 5: 运行测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v`
Expected: All existing tests pass

- [ ] **Step 6: 提交**

```bash
git add backend/app/agents/prompts.py backend/app/agents/nodes/chapter_generation.py
git commit -m "feat(workflow): use words_per_chapter range in chapter content generation prompt"
```

---

### Task 5: 端到端验证

**Files:** 无新文件

- [ ] **Step 1: 运行完整后端测试套件**

Run: `docker exec novelagent-backend-1 pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: 重启后端服务确认无启动错误**

Run: `docker compose restart backend && docker compose logs backend --tail 30`
Expected: 无 import 错误或启动异常

- [ ] **Step 3: 最终提交（如有遗漏修复）**

如果 Step 1 或 Step 2 发现问题，修复后提交。
