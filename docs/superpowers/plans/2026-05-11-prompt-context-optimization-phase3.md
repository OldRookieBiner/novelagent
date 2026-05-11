# Phase 3: System Message + 上下文策略 + 审核解析解耦 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 章节正文生成拆为 system+user 双层消息，短篇前文全文放入上下文，审核解析改为 JSON 格式

**Architecture:** 新增 ContextStrategy 策略模式管理前文上下文，拆分 prompt 模板为 system/user 两部分，审核输出改为 JSON 结构化

**Tech Stack:** Python 3.11, LangGraph, SQLAlchemy

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/agents/context_strategy.py` | 新建 | 上下文策略基类 + Fulltext 实现 + 策略选择函数 |
| `backend/app/agents/prompts.py` | 修改 | 拆分 CHAPTER_CONTENT prompt 为 system/user，改 review 输出格式为 JSON |
| `backend/app/agents/nodes/chapter_generation.py` | 修改 | system/user 消息拆分 + 上下文策略集成 |
| `backend/app/agents/nodes/review.py` | 修改 | 重写 parse_review_result，新增 _parse_review_result_legacy，更新 check_review_passed |
| `backend/app/api/workflow.py` | 修改 | _build_prompts_dict 适配 dict 格式，written_chapters 补 title |
| `backend/tests/test_context_strategy.py` | 新建 | Fulltext 策略测试 |
| `backend/tests/test_review.py` | 修改 | 新增 JSON 解析测试 |
| `backend/tests/test_agents.py` | 修改 | 更新 chapter_content prompt 测试 |

---

### Task 1: 创建上下文策略模块

**Files:**
- Create: `backend/app/agents/context_strategy.py`
- Test: `backend/tests/test_context_strategy.py`

- [ ] **Step 1: 写失败的测试**

```python
"""上下文策略测试"""
import pytest
from app.agents.context_strategy import (
    FulltextContentStrategy,
    get_context_strategy,
)


class TestFulltextContentStrategy:
    def test_no_previous_chapters(self):
        """第一章没有前文"""
        strategy = FulltextContentStrategy()
        result = strategy.build_previous_context([], 1)
        assert "第一章" in result or "没有前文" in result

    def test_single_previous_chapter(self):
        """有一章前文"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "那天风很大。"},
        ]
        result = strategy.build_previous_context(chapters, 2)
        assert "起风了" in result
        assert "那天风很大" in result
        assert "第1章" in result

    def test_multiple_previous_chapters(self):
        """有多章前文"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 3)
        assert "第1章" in result
        assert "第2章" in result
        assert "风起" in result
        assert "雨落" in result

    def test_excludes_current_chapter(self):
        """不包含当前正在写的章节"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": "雨落。"},
        ]
        result = strategy.build_previous_context(chapters, 2)
        assert "第1章" in result
        assert "第2章" not in result

    def test_skips_empty_content(self):
        """跳过没有内容的章节"""
        strategy = FulltextContentStrategy()
        chapters = [
            {"chapter_number": 1, "title": "起风了", "content": "风起。"},
            {"chapter_number": 2, "title": "雨来了", "content": ""},
        ]
        result = strategy.build_previous_context(chapters, 3)
        assert "第1章" in result
        assert "第2章" not in result


class TestGetContextStrategy:
    def test_short_novel_returns_fulltext(self):
        """短篇返回 Fulltext 策略"""
        strategy = get_context_strategy(50000)
        assert isinstance(strategy, FulltextContentStrategy)

    def test_medium_novel_returns_fulltext_for_now(self):
        """中篇暂时也返回 Fulltext（Phase 4 改为 Hybrid）"""
        strategy = get_context_strategy(200000)
        assert isinstance(strategy, FulltextContentStrategy)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.context_strategy'`

- [ ] **Step 3: 实现 context_strategy.py**

```python
"""上下文策略 — 管理章节生成时的前文上下文构建方式"""

from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    """上下文策略基类"""

    @abstractmethod
    def build_previous_context(self, written_chapters: list[dict], current_chapter: int) -> str:
        """构建前文上下文文本"""
        pass


class FulltextContentStrategy(ContextStrategy):
    """短篇策略：所有已写章节全文放入上下文"""

    def build_previous_context(self, written_chapters: list[dict], current_chapter: int) -> str:
        parts = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                title = ch.get("title", "")
                content = ch.get("content", "")
                if content:
                    parts.append(f"第{ch_num}章《{title}》\n{content}")
        if not parts:
            return "（这是第一章，没有前文）"
        return "\n\n---\n\n".join(parts)


class HybridContentStrategy(ContextStrategy):
    """中篇策略（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
        raise NotImplementedError("HybridContentStrategy 尚未实现")


class SummaryContentStrategy(ContextStrategy):
    """长篇策略（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
        raise NotImplementedError("SummaryContentStrategy 尚未实现")


def get_context_strategy(target_words: int) -> ContextStrategy:
    """根据目标字数选择上下文策略"""
    if target_words <= 100000:
        return FulltextContentStrategy()
    else:
        return FulltextContentStrategy()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_context_strategy.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/context_strategy.py backend/tests/test_context_strategy.py
git commit -m "feat(context): add ContextStrategy module with Fulltext implementation"
```

---

### Task 2: 拆分章节正文 Prompt 为 system/user 双层

**Files:**
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 在 prompts.py 中新增 system 和 user 模板**

在 `GENERATE_CHAPTER_CONTENT_PROMPT` 之后，新增：

```python
# ==============================================================================
# 3a. 章节正文 System Prompt — 角色定位 + 写作规则 + 前文 + 人物 + 世界观
# ==============================================================================
CHAPTER_CONTENT_SYSTEM_PROMPT = """你是一位获得茅盾文学奖的当代小说家，以细节精准、人物鲜活、情感克制而著称。

## 前文（你需要确保本章与前文在情节、人物、风格上自然衔接）
{previous_context}

## 人物档案
{main_characters}
（注意：写作时严格遵守人物的口头禅、习惯动作、深层恐惧等设定。）

## 世界观
{world_setting}

---

## 写作原则（违反任何一条都会导致作品质量严重下降）

### 1. 展示而非讲述（Show, Don't Tell）
- ❌ "他很生气"
- ✅ "他把杯子往桌上一摔，釉面裂开一道缝，热水顺着桌沿滴在他鞋上，他都没顾上擦"
- ❌ "她感到害怕"
- ✅ "她把门反锁了，又推了一下，再推了一下，手指在门把手上停了五秒钟"

### 2. 对话技巧
- 对话要有潜台词，不直白说教。让角色"说反话""顾左右而言他"。
- 每个人物有独一无二的说话方式：语速、用词偏好、句式习惯、是否使用方言/外语。
- 用对话推进情节，严禁无意义的寒暄和天气讨论。

### 3. 节奏控制
- 紧张场景用短句，甚至断句，制造呼吸感。
- 舒缓场景用长句，但不超过 40 个字，避免欧化语法。
- 适当留白，不要解释角色的每一个动机。让读者猜。

### 4. 细节描写
- 用五感描写：视觉、听觉、嗅觉、触觉、味觉。
- 每个细节必须服务于情节或人物心理，拒绝纯粹的环境装饰。
- 一个精准的细节胜过十句泛泛描述。优先写"不合常理"的细节。

### 5. 情感张力
- 每个场景都要有情感目标，写之前问自己"读者读到这里应该感受到什么"。
- 情感克制比情感宣泄更有力。愤怒不写怒吼，写手指的颤抖。
- 高潮部分的冲击力来自于此前压抑的积累，不要一上来就满功率输出。

### 6. 反 AI 味（最重要）

以下词汇和表达在 20 年一线作家的作品中**几乎不会出现**，如果你使用了，说明你在模仿 AI：

{forbidden_words}

**正确示例对比**：
- ❌ "他眼神复杂地看着她，欲言又止。"
- ✅ "他看了她一眼，又看向窗外，手指在桌沿上敲了两下，收回口袋里。"
- ❌ "她深吸一口气，定了定神，缓缓走向门口。"
- ✅ "她站住了，低头看着鞋尖上的一片落叶，然后用力把它踢开了。"

---

## 写完后自检（你必须在输出前逐项确认）

1. 【衔接检查】本章开头是否自然而然地承接了前文的心理/对话/动作最后一幕？
2. 【人设检查】每个出场人物的对话习惯、口头禅、行为模式是否与其档案一致？
3. 【伏笔检查】如果本章涉及伏笔，线索是否交代到位但不直给？
4. 【AI 味检查】全文搜索上面的禁用词列表，确认一个都没有出现。
5. 【节奏检查】本章是否包含至少一个"紧张-松弛"或"推进-留白"的节奏变化？
6. 【对话检查】每段对话是否推动了情节或揭示了人物关系，没有闲笔？
"""

# ==============================================================================
# 3b. 章节正文 User Prompt — 具体任务输入
# ==============================================================================
CHAPTER_CONTENT_USER_PROMPT = """请根据以下信息，写出完整的章节正文。

## 章节大纲
{chapter_outline}

## 前文结尾衔接参考
{previous_ending}
（注意：前文可能存在伏笔、情绪、对话未完结。本章开头必须自然承接。）

## 全局设定
- 题材：{genre}
- 本章最低字数：{min_words} 字（建议不超过 {suggested_max} 字，完整性优先）
- 风格：{style_preference}

确认自检全部通过后，请直接输出章节正文，字数不低于 {min_words} 字，情节完整比字数更重要。
不要输出自检清单，不要输出任何解释说明。"""
```

- [ ] **Step 2: 更新 DEFAULT_PROMPTS**

将 DEFAULT_PROMPTS 中的 `"chapter_content_generation"` 改为 dict 格式：

```python
DEFAULT_PROMPTS = {
    "outline_generation": OUTLINE_GENERATION_PROMPT,
    "chapter_outline_generation": GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    "chapter_content_generation": {
        "system": _apply_forbidden_words_to_prompt(CHAPTER_CONTENT_SYSTEM_PROMPT),
        "user": CHAPTER_CONTENT_USER_PROMPT,
    },
    "review": _apply_forbidden_words_list_to_prompt(REVIEW_CHAPTER_PROMPT),
    "rewrite": _apply_forbidden_words_list_to_prompt(REWRITE_CHAPTER_PROMPT),
    "character_generation": CHARACTER_GENERATION_PROMPT,
    "relation_generation": RELATION_GENERATION_PROMPT,
}
```

注意：保留旧的 `GENERATE_CHAPTER_CONTENT_PROMPT` 不删除，确保向后兼容。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/prompts.py
git commit -m "feat(prompt): split chapter content prompt into system + user templates"
```

---

### Task 3: 更新 _build_prompts_dict 适配 dict 格式 + written_chapters 补 title

**Files:**
- Modify: `backend/app/api/workflow.py`

- [ ] **Step 1: 修改 _build_prompts_dict**

将 `_build_prompts_dict` 的返回类型从 `dict[str, str]` 改为 `dict[str, str | dict]`，对 `chapter_content_generation` 做特殊处理：

```python
def _build_prompts_dict(db: Session) -> dict[str, str | dict]:
    """构建预加载的 prompts 字典（所有节点共享）"""
    from app.services.prompt_loader import get_system_prompt
    from app.agents.prompts import DEFAULT_PROMPTS

    # chapter_content_generation 的 user 模板：优先从 DB 读取自定义版本
    # DB key 用 prompt_chapter_content_generation_user
    user_template = get_system_prompt(db, "chapter_content_generation")
    if not user_template or len(user_template.strip()) < 100:
        user_template = DEFAULT_PROMPTS["chapter_content_generation"]["user"]

    return {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
        "chapter_outline_generation": get_system_prompt(db, "chapter_outline_generation"),
        "chapter_content_generation": {
            "system": DEFAULT_PROMPTS["chapter_content_generation"]["system"],
            "user": user_template,
        },
        "review": get_system_prompt(db, "review"),
        "rewrite": get_system_prompt(db, "rewrite"),
    }
```

- [ ] **Step 2: 修改 written_chapters 补充 title**

在第 173 行，给 `written_chapters` 添加 `title` 字段：

```python
written_chapters.append({
    "chapter_number": co.chapter_number,
    "title": co.title,
    "content": co.chapter.content,
    "word_count": co.chapter.word_count,
})
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/workflow.py
git commit -m "feat(workflow): adapt _build_prompts_dict for dict format + add title to written_chapters"
```

---

### Task 4: 改造 chapter_generation.py 使用 system/user 消息 + 上下文策略

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py`
- Modify: `backend/tests/test_agents.py`

- [ ] **Step 1: 新增辅助函数 `_get_chapter_content_prompts`**

在 `chapter_generation.py` 顶部（imports 之后）添加：

```python
def _get_chapter_content_prompts(state: dict) -> tuple[str, str]:
    """获取章节正文的 system 和 user 模板

    Returns:
        (system_template, user_template)
    """
    prompts = state.get("_prompts", {})
    prompt_data = prompts.get("chapter_content_generation") if prompts else None

    if prompt_data and isinstance(prompt_data, dict):
        system_template = prompt_data.get("system", "")
        user_template = prompt_data.get("user", "")
    elif prompt_data and isinstance(prompt_data, str):
        # 旧格式兼容：整个模板作为 user message
        user_template = prompt_data
        system_template = ""
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        prompt_data = DEFAULT_PROMPTS.get("chapter_content_generation", {})
        if isinstance(prompt_data, dict):
            system_template = prompt_data.get("system", "")
            user_template = prompt_data.get("user", "")
        else:
            user_template = str(prompt_data)
            system_template = ""

    return system_template, user_template
```

- [ ] **Step 2: 改造 generate_chapter_content_stream()**

将当前的 prompt 构建和 LLM 调用逻辑替换为 system/user 双层。关键改动：

```python
# 替换原 prompt 构建逻辑
system_template, user_template = _get_chapter_content_prompts(state)

# 构建上下文策略
from app.agents.context_strategy import get_context_strategy
target_words = info.get("targetWords", 100000)
if isinstance(target_words, str):
    try:
        target_words = int(target_words)
    except (ValueError, TypeError):
        target_words = 100000
strategy = get_context_strategy(target_words)
written_chapters = state.get("written_chapters", [])
previous_context = strategy.build_previous_context(written_chapters, chapter_outline.get("chapter_number", 1))

# 格式化 system message
system_msg = system_template.format(
    previous_context=previous_context,
    main_characters=combined_characters_str,
    world_setting=world_str,
)

# 格式化 user message
user_msg = user_template.format(
    chapter_outline=outline_str,
    previous_ending=previous_ending,
    genre=info.get("novelType", "未指定"),
    min_words=min_words,
    suggested_max=suggested_max,
    style_preference=info.get("stylePreference", "未指定"),
)

# 替换 LLM 调用
messages = []
if system_msg:
    messages.append({"role": "system", "content": system_msg})
messages.append({"role": "user", "content": user_msg})

async for chunk in llm.chat_stream(messages, max_tokens=max_tokens):
    yield chunk
```

- [ ] **Step 3: 改造 generate_chapter_content_node()**

同 Step 2 逻辑，将 `chapter_generation_node` 中的 prompt 构建和 LLM 调用同样拆为 system/user。注意此函数有完整的 LLM 调用代码（约第 407-500 行），需要同样替换。

- [ ] **Step 4: 更新 test_agents.py 中的 chapter_content 测试**

将 `test_chapter_content_prompt_format` 更新为测试 system/user 模板：

```python
def test_chapter_content_prompt_format(self):
    """Chapter content prompt should format correctly with system/user split"""
    from app.agents.prompts import DEFAULT_PROMPTS

    prompt_data = DEFAULT_PROMPTS["chapter_content_generation"]
    assert isinstance(prompt_data, dict)
    assert "system" in prompt_data
    assert "user" in prompt_data

    system_msg = prompt_data["system"].format(
        previous_context="第1章《起风了》\n风很大。",
        main_characters="张三",
        world_setting="现代都市",
    )

    user_msg = prompt_data["user"].format(
        chapter_outline="第2章：测试章节\n场景：城市",
        previous_ending="上一章的结尾...",
        genre="都市",
        min_words=3000,
        suggested_max=4500,
        style_preference="轻松幽默",
    )

    assert "张三" in system_msg
    assert "前文" in system_msg
    assert "第2章" in user_msg
    assert "3000" in user_msg
```

- [ ] **Step 5: 运行测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_agents.py tests/test_context_strategy.py -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/nodes/chapter_generation.py backend/tests/test_agents.py
git commit -m "feat(chapter): use system/user messages + context strategy for chapter generation"
```

---

### Task 5: 审核解析器改为 JSON 格式 + 旧格式回退

**Files:**
- Modify: `backend/app/agents/nodes/review.py`
- Modify: `backend/app/agents/prompts.py` (REVIEW_CHAPTER_PROMPT 输出格式部分)
- Modify: `backend/tests/test_review.py`

- [ ] **Step 1: 修改 REVIEW_CHAPTER_PROMPT 输出格式**

在 `prompts.py` 中，将 REVIEW_CHAPTER_PROMPT 的 `## 输出格式` 部分（约第 321-356 行）替换为 JSON 格式要求：

将：
```
## 输出格式

---
【审核结果】通过 / 不通过

【分项评分】
- 情节一致性：X/10
- 人物一致性：X/10
- 文笔质量：X/10
- 情感张力：X/10
- AI 味程度：X/10（分数越低越好）
- 大纲偏离度：X/10（分数越低越好）

【通过标准】
- 情节一致性、人物一致性、文笔质量、情感张力均 ≥ 6 分
- AI 味程度 ≤ 3 分
- 大纲偏离度 ≤ 4 分
- 总分 ≥ 35/60

【问题列表】（如果没有问题则写"无"）
1. [问题类型：情节矛盾/人设偏离/文笔问题/情感不足/AI 味/大纲偏离] - [具体位置] - [问题描述，要求足够具体，让修改者知道改哪里]
2. ...

【修改建议】（必须给出可操作的建议）
- 针对每个问题，给出至少一个具体的修改方向或替代写法
- 如果 AI 味重，指出具体的禁用词并提供更优替换
- 如果大纲偏离，指出应如何回归大纲设计
---

## 审核原则
1. **宁可严苛，不要放水。** 如果存在让读者"出戏"的问题，必须指出。
2. **定位要精确。** 问题描述要足够具体，能让作者直接找到对应位置修改。
3. **建议要建设性。** 不要只说"这里不好"，必须说"改成什么会更好"。
4. **AI 味是零容忍区。** 只要发现 3 个以上的 AI 味词汇，AI 味维度直接打 7 分以上。

请严格按照上述格式输出。
```

替换为：

```
## 输出格式

请严格按照以下 JSON 格式输出审核结果，不要输出 JSON 以外的任何内容：

```json
{{
  "passed": true或false,
  "scores": {{
    "plot_consistency": 1到10的整数,
    "character_consistency": 1到10的整数,
    "writing_quality": 1到10的整数,
    "emotional_tension": 1到10的整数,
    "ai_flavor": 1到10的整数,
    "outline_deviation": 1到10的整数
  }},
  "issues": [
    {{"type": "情节矛盾或人设偏离或文笔问题或情感不足或AI味或大纲偏离", "location": "具体位置", "description": "问题描述"}}
  ],
  "suggestions": "修改建议，针对每个问题给出可操作的修改方向。如果AI味重，指出具体禁用词并提供替换"
}}
```

通过标准：
- plot_consistency、character_consistency、writing_quality、emotional_tension 均 ≥ 6
- ai_flavor ≤ 3
- outline_deviation ≤ 4

## 审核原则
1. **宁可严苛，不要放水。** 如果存在让读者"出戏"的问题，必须指出。
2. **定位要精确。** 问题描述要足够具体，能让作者直接找到对应位置修改。
3. **建议要建设性。** 不要只说"这里不好"，必须说"改成什么会更好"。
4. **AI 味是零容忍区。** 只要发现 3 个以上的 AI 味词汇，AI 味维度直接打 7 分以上。

请只输出 JSON，不要输出其他内容。
```

注意：JSON 模板中的 `{{` 和 `}}` 是 Python format 的转义，因为 REVIEW_CHAPTER_PROMPT 使用 `.format()` 填充 `{strictness}` 等占位符。

- [ ] **Step 2: 重写 parse_review_result + 新增 _parse_review_result_legacy**

在 `review.py` 中：

```python
import json

def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果（优先 JSON 格式，回退旧格式）"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    # 尝试提取 JSON
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            result["passed"] = data.get("passed", False)
            result["scores"] = data.get("scores", {})
            result["issues"] = data.get("issues", [])
            result["suggestions"] = data.get("suggestions", "")
            return result
        except json.JSONDecodeError:
            pass

    # 回退到旧格式解析
    return _parse_review_result_legacy(response)


def _parse_review_result_legacy(response: str) -> Dict[str, Any]:
    """旧格式回退解析（兼容期）"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    # 解析是否通过
    result["passed"] = "【审核结果】通过" in response

    # 解析分项评分
    score_patterns = {
        "plot_consistency": r"情节一致性[：:]\s*(\d+)/10",
        "character_consistency": r"人物一致性[：:]\s*(\d+)/10",
        "writing_quality": r"文笔质量[：:]\s*(\d+)/10",
        "emotional_tension": r"情感张力[：:]\s*(\d+)/10",
        "ai_flavor": r"AI味程度[：:]\s*(\d+)/10",
    }

    for key, pattern in score_patterns.items():
        match = re.search(pattern, response)
        if match:
            result["scores"][key] = int(match.group(1))

    # 解析问题列表
    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [
            i.strip()
            for i in re.findall(
                r"\d+\.\s*(.+?)(?=\n\d+\.|无|$)", issues_text, re.DOTALL
            )
            if i.strip()
        ]
        if issues_text.strip() != "无":
            result["issues"] = issues

    # 解析修改建议
    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()
        if suggestions != "无":
            result["suggestions"] = suggestions

    return result
```

- [ ] **Step 3: 更新 check_review_passed**

```python
def check_review_passed(review_result: Dict[str, Any]) -> bool:
    """检查审核是否通过"""
    scores = review_result.get("scores", {})

    for key in [
        "plot_consistency",
        "character_consistency",
        "writing_quality",
        "emotional_tension",
    ]:
        if scores.get(key, 0) < 6:
            return False

    if scores.get("ai_flavor", 10) > 3:
        return False

    if scores.get("outline_deviation", 0) > 4:
        return False

    return True
```

- [ ] **Step 4: 新增 JSON 解析测试**

在 `test_review.py` 的 `TestParseReviewResult` 类中新增：

```python
def test_parse_json_passed_result(self):
    """Should parse a JSON passed review result"""
    response = '''```json
{
  "passed": true,
  "scores": {
    "plot_consistency": 8,
    "character_consistency": 9,
    "writing_quality": 7,
    "emotional_tension": 8,
    "ai_flavor": 2,
    "outline_deviation": 1
  },
  "issues": [],
  "suggestions": ""
}
```'''
    result = parse_review_result(response)
    assert result["passed"] is True
    assert result["scores"]["plot_consistency"] == 8
    assert result["scores"]["outline_deviation"] == 1
    assert result["issues"] == []

def test_parse_json_failed_result(self):
    """Should parse a JSON failed review result"""
    response = '''{
  "passed": false,
  "scores": {
    "plot_consistency": 5,
    "character_consistency": 4,
    "writing_quality": 6,
    "emotional_tension": 5,
    "ai_flavor": 7,
    "outline_deviation": 3
  },
  "issues": [
    {"type": "情节矛盾", "location": "第3段", "description": "转折过于突兀"},
    {"type": "AI味", "location": "第5段", "description": "使用了禁用词"}
  ],
  "suggestions": "建议增加过渡描写，替换AI味词汇"
}'''
    result = parse_review_result(response)
    assert result["passed"] is False
    assert result["scores"]["ai_flavor"] == 7
    assert len(result["issues"]) == 2
    assert result["issues"][0]["type"] == "情节矛盾"
    assert "过渡描写" in result["suggestions"]

def test_parse_fallback_to_legacy(self):
    """Should fallback to legacy parser when JSON parse fails"""
    # 旧格式文本
    response = """
【审核结果】通过

情节一致性：8/10
人物一致性：9/10
"""
    result = parse_review_result(response)
    assert result["passed"] is True
    assert result["scores"]["plot_consistency"] == 8
```

在 `TestCheckReviewPassed` 类中新增：

```python
def test_pass_with_outline_deviation(self):
    """Should pass when outline deviation is within threshold"""
    result = {
        "scores": {
            "plot_consistency": 8,
            "character_consistency": 8,
            "writing_quality": 8,
            "emotional_tension": 8,
            "ai_flavor": 2,
            "outline_deviation": 3,
        }
    }
    assert check_review_passed(result) is True

def test_fail_on_high_outline_deviation(self):
    """Should fail when outline deviation exceeds threshold"""
    result = {
        "scores": {
            "plot_consistency": 8,
            "character_consistency": 8,
            "writing_quality": 8,
            "emotional_tension": 8,
            "ai_flavor": 2,
            "outline_deviation": 5,
        }
    }
    assert check_review_passed(result) is False
```

- [ ] **Step 5: 运行测试验证**

Run: `docker exec novelagent-backend-1 pytest tests/test_review.py -v`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/nodes/review.py backend/app/agents/prompts.py backend/tests/test_review.py
git commit -m "feat(review): JSON structured output + legacy fallback for review parsing"
```

---

### Task 6: 全量验证与清理

**Files:**
- Verify all test files pass

- [ ] **Step 1: 运行完整后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: 新增测试全部通过，无新增失败

- [ ] **Step 2: 运行前端测试**

Run: `cd /opt/project/novelagent/frontend && npm run test:run`
Expected: 85 passed

- [ ] **Step 3: 重建并重启后端**

Run: `docker compose build --no-cache backend && docker compose up -d backend`

- [ ] **Step 4: 更新 anatomy.md 和 memory.md**

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: Phase 3 verification complete"
```
