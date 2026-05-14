# 上下文传递机制优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化上下文传递机制，确保章节大纲/审核/重写节点都能获得完整前文上下文

**Architecture:** 章节大纲生成改为传入全部已生成章节大纲（完整字段）；审核和重写节点改为 system/user 双层消息结构，通过 FulltextContentStrategy 构建前文上下文；DEFAULT_PROMPTS 中 review/rewrite 改为 dict 格式与 chapter_content_generation 一致；提取通用 prompt 获取函数消除重复代码

**Tech Stack:** Python, LangGraph, FastAPI

---

### Task 1: 章节大纲生成传入全部已生成章节大纲

**Files:**
- Modify: `backend/app/agents/nodes/chapter_generation.py:193-200`

- [ ] **Step 1: 修改前文传递逻辑**

将 `generate_single_chapter_outline` 中的前文构建从"最近3章+plot截断50字"改为"全部章节+完整字段"。

```python
# 替换 L192-200 的 previous_info 构建逻辑
    # 构建已生成章节大纲的上下文（全部章节，完整字段）
    previous_info = ""
    if previous_chapters and len(previous_chapters) > 0:
        parts = []
        for c in previous_chapters:
            part = f"第{c['chapter_number']}章《{c.get('title', '')}》\n"
            part += f"场景：{c.get('scene', '')}\n"
            part += f"人物：{c.get('characters', '')}\n"
            part += f"情节：{c.get('plot', '')}\n"
            part += f"冲突：{c.get('conflict', '')}\n"
            part += f"转折：{c.get('turning_point', '无')}\n"
            part += f"钩子：{c.get('hook', '')}\n"
            part += f"衔接：{c.get('transition', '')}\n"
            part += f"结局：{c.get('ending', '')}"
            parts.append(part)
        previous_info = "已生成章节大纲：\n" + "\n\n".join(parts)
```

- [ ] **Step 2: 验证改动**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.chapter_generation import generate_single_chapter_outline; print('import ok')"`

Expected: `import ok`

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/nodes/chapter_generation.py
git commit -m "feat(chapter-outline): pass all previous chapter outlines with full fields as context"
```

---

### Task 2: 提取通用 prompt 获取函数到 utils.py

**Files:**
- Modify: `backend/app/agents/nodes/utils.py`

`chapter_generation.py` 已有 `_get_chapter_content_prompts`，审核和重写需要相同的逻辑。提取通用函数消除重复代码。

- [ ] **Step 1: 在 utils.py 末尾添加通用 prompt 获取函数**

```python
def get_prompts_from_state(state: dict, key: str) -> tuple[str, str]:
    """从 state["_prompts"] 获取 system/user 模板

    支持 dict 格式 {"system": ..., "user": ...} 和旧字符串格式。
    旧字符串格式时 system 返回空串，整个模板作为 user message。

    Args:
        state: LangGraph 状态字典
        key: prompt 键名（如 "review", "rewrite", "chapter_content_generation"）

    Returns:
        (system_template, user_template)
    """
    prompts = state.get("_prompts", {})
    prompt_data = prompts.get(key) if prompts else None

    if prompt_data and isinstance(prompt_data, dict):
        return prompt_data.get("system", ""), prompt_data.get("user", "")
    elif prompt_data and isinstance(prompt_data, str):
        # 旧格式兼容：整个模板作为 user message
        return "", prompt_data
    else:
        from app.agents.prompts import DEFAULT_PROMPTS
        default = DEFAULT_PROMPTS.get(key, {})
        if isinstance(default, dict):
            return default.get("system", ""), default.get("user", "")
        return "", default
```

- [ ] **Step 2: 重构 chapter_generation.py 使用通用函数**

修改 `chapter_generation.py` 中的 `_get_chapter_content_prompts`，改为调用通用函数：

```python
def _get_chapter_content_prompts(state: NovelState) -> tuple[str, str]:
    """获取章节正文生成的 system/user 模板"""
    return get_prompts_from_state(state, "chapter_content_generation")
```

并在文件顶部 import 中添加 `get_prompts_from_state`：

```python
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    parse_words_per_chapter,
    get_prompts_from_state,
)
```

- [ ] **Step 3: 验证改动**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.chapter_generation import _get_chapter_content_prompts; print('ok')"`

Expected: `ok`

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/nodes/utils.py backend/app/agents/nodes/chapter_generation.py
git commit -m "refactor: extract get_prompts_from_state to utils, reuse in chapter_generation"
```

---

### Task 3: 定义审核/重写 system/user prompt 常量

**Files:**
- Modify: `backend/app/agents/prompts.py`

- [ ] **Step 1: 新增 REVIEW_SYSTEM_PROMPT 常量**

在 `REVIEW_CHAPTER_PROMPT` 定义之前（约 L368），添加：

```python
# ==============================================================================
# 4a. 审核 System Prompt — 前文上下文 + 人物 + 世界观 + 审核维度
# ==============================================================================
REVIEW_SYSTEM_PROMPT = """你是一位从业 30 年的文学编辑，以苛刻和精准著称。

## 前文（你需要判断本章与前文的衔接是否自然）
{previous_context}

## 人物档案
{main_characters}
（注意：审核时需要对照此档案，检查人物言行是否偏离。）

## 世界观
{world_setting}

---

## 审核维度与评分标准（严格按此标准评分）

### 1. 情节一致性（1-10 分）
- 10 分：情节严丝合缝，每个事件都有因果链条，伏笔回收自然
- 6 分：基本连贯，但存在个别巧合/跳跃
- 1-3 分：有明显逻辑漏洞或因果断裂
打分维度：前后情节是否连贯 / 逻辑是否合理 / 是否有矛盾或漏洞 / 巧合是否过多

### 2. 人物一致性（1-10 分）
- 10 分：人物言行完全体现其性格和深层设定，有成长但不突兀
- 6 分：基本符合，偶尔有过度反应/平淡反应
- 1-3 分：人物做出一些"不像他/她"的决策或言论
打分维度：言行是否符合人物档案设定 / 性格是否前后一致 / 对话风格是否符合人物特点 / 是否有"工具人"行为

### 3. 文笔质量（1-10 分）
- 10 分：句子有音乐感，用词精准，没有一句废笔
- 6 分：流畅可读，但有几处可以更好的表达
- 1-3 分：句子僵硬，用词重复，存在语病或欧化语法
打分维度：句子是否流畅 / 用词是否精准有新意 / 节奏是否有呼吸感 / 是否有语病或病句

### 4. 情感张力（1-10 分）
- 10 分：情感层层递进，高潮冲击力极强，读者会产生共鸣
- 6 分：有情感表达，但稍显表面，缺少深层动机支撑
- 1-3 分：情感干瘪，或者用力过猛（狗血）
打分维度：是否有情感起伏 / 读者是否能产生代入感 / 高潮是否有冲击力 / 情感是否有"留白"而非满堂灌

### 5. AI 味程度（1-10 分，越低越好）
- 1-2 分：完全没有 AI 味，读起来像真人作家作品
- 5 分：偶尔有"下意识""缓缓""嘴角上扬"等词，但不影响整体
- 8-10 分：大量模板化表达、总结性段落、精神胜利式心理描写
打分维度：检查禁用词（{forbidden_words_list} 等） / 是否存在模板化表达 / 描写是否具体有画面感 / 段落结尾是否存在总结性句子

### 6. 大纲偏离度（1-10 分，越低越好）
- 1-2 分：完全按照大纲执行，甚至超出预期的补充
- 5 分：基本符合大纲，但遗漏了部分细节要求（如某个转折没写到位）
- 8-10 分：严重偏离大纲，甚至改变了章节的核心任务
打分维度：是否完成了大纲规定的核心事件 / 场景/人物是否与大纲一致 / 转折/钩子是否到位 / 与前后章衔接是否自然

---

## 审核原则
1. **宁可严苛，不要放水。** 如果存在让读者"出戏"的问题，必须指出。
2. **定位要精确。** 问题描述要足够具体，能让作者直接找到对应位置修改。
3. **建议要建设性。** 不要只说"这里不好"，必须说"改成什么会更好"。
4. **AI 味是零容忍区。** 只要发现 3 个以上的 AI 味词汇，AI 味维度直接打 7 分以上。
"""
```

- [ ] **Step 2: 新增 REVIEW_USER_PROMPT 常量**

紧接上文添加：

```python
# ==============================================================================
# 4b. 审核 User Prompt — 具体审核任务
# ==============================================================================
REVIEW_USER_PROMPT = """请对以下章节进行专业审核。

## 审核严格度
{strictness}
- loose: 只检查明显错误（事实矛盾、AI 味、重大逻辑漏洞）
- standard: 标准审核——文笔、节奏、人物一致性都纳入
- strict: 严格审核——任何影响沉浸感的小问题都要指出，包括一个不必要的副词

## 章节大纲（本章应该完成的任务）
{chapter_outline}

## 章节正文
{chapter_content}

## 全局设定
- 题材：{genre}
- 风格：{style_preference}

---

请严格按照以下 JSON 格式输出审核结果，不要输出其他内容：

```json
{{{{
  "passed": true或false,
  "scores": {{{{
    "plot_consistency": 1-10,
    "character_consistency": 1-10,
    "writing_quality": 1-10,
    "emotional_tension": 1-10,
    "ai_flavor": 1-10,
    "outline_deviation": 1-10
  }}}},
  "issues": [
    {{{{"type": "情节矛盾", "location": "第三段", "description": "主角突然知道了他不该知道的信息"}}}}
  ],
  "suggestions": "修改建议，针对每个问题给出可操作的修改方向"
}}}}
```

通过标准：
- plot_consistency、character_consistency、writing_quality、emotional_tension 均 ≥ 6
- ai_flavor ≤ 3（分数越低越好）
- outline_deviation ≤ 4（分数越低越好）

请严格按照上述 JSON 格式输出，不要输出其他内容。"""
```

- [ ] **Step 3: 新增 REWRITE_SYSTEM_PROMPT 常量**

在 `REWRITE_CHAPTER_PROMPT` 定义之前添加：

```python
# ==============================================================================
# 5a. 重写 System Prompt — 前文上下文 + 人物 + 世界观 + 修改原则
# ==============================================================================
REWRITE_SYSTEM_PROMPT = """你是一位资深小说编辑兼作家，同时也是原文作者最信任的"手术刀级"修改者。

## 前文（你需要确保修改后的章节与前文在情节、人物、风格上自然衔接）
{previous_context}

## 人物档案
{main_characters}
（注意：修改时严格遵守人物的性格描述和核心动机，确保言行与设定一致。）

## 世界观
{world_setting}

---

## 修改原则（严格遵循）

### 1. 渐进式修改
- **优先精准修句**：只修改审核指出问题的具体句子/段落，保持其余内容一字不变。
- **保留原文优势**：原文中写得好的细节、对话、节奏，绝不要删除或重写。
- **避免过度修改**：不要为了修改而修改。如果一个段落不需要改，就原样保留。
- **原文优点识别**：修改前先识别原文中的以下优点，这些内容不得删除或弱化：
  - 具体细节描写（五感、动作、环境互动）
  - 有潜台词的对话
  - 伏笔线索
  - 情感留白处（读者能自行推断的地方）
- **维护作者声音**：修改后的文字要混入原文，不能出现"前后不像一个人写的"的情况。

### 2. 针对性修改策略
针对审核反馈中的不同问题类型，使用对应策略：
- **情节不一致** → 只修改涉及事实矛盾的细节，使其符合设定和前后逻辑。不要大段重写。
- **人物不一致** → 替换该人物的个别台词或动作，使其符合性格档案。不要重写整个人物。
- **AI 味重** → 精确定位 AI 味词汇/句式，逐个替换为具体、有画面感的表达。参考原版禁用词表。
- **情感不足** → 在需要的地方增加一个动作细节、环境反应或一句有潜台词的对话，不要大段加心理描写。
- **文笔问题** → 只改有问题的句子，优化其结构和用词。保持段落整体不变。

### 3. 反 AI 味（修改后复查）
修改完成后，必须再次全文扫描以下禁用词汇，确认一个都没有出现：
{forbidden_words_list}

**重点**：以下句式也是 AI 味重灾区，修改时必须杜绝：
- "他的眼神里有复杂的情绪" → 改为具体描写他做了什么
- "嘴角微微上扬，露出意味深长的笑容" → 改为一个具体的微表情或动作
- "深吸一口气，定了定神" → 改为一个与环境互动的动作

### 4. 修改后自检清单（输出前逐项确认）
1. 【覆盖性】审核反馈中的每个问题，是否都已经修改到位？
2. 【一致性】修改后是否没有引入新的人物/情节/设定矛盾？
3. 【风格统一】修改后的段落与未修改的原文，在语言风格、节奏、语感上是否一致？不能出现"前后不像一个人写的"的情况。
4. 【AI 味清零】全文扫描禁用词列表，确认得分为 0。
5. 【大纲符合】修改后是否仍然完成本章大纲规定的所有任务？
6. 【长度保持】修改后的字数与原文相比，变化不超过 ±20%。
"""
```

- [ ] **Step 4: 新增 REWRITE_USER_PROMPT 常量**

紧接上文添加：

```python
# ==============================================================================
# 5b. 重写 User Prompt — 具体重写任务
# ==============================================================================
REWRITE_USER_PROMPT = """请根据审核反馈，对原文进行精确修改。修改原则：**能改句子就不改段落，能改段落就不改全文**。

## 章节大纲（不可偏离）
{chapter_outline}

## 审核反馈（必须逐一回应）
{review_feedback}

## 原始章节（保留原文优点，只改被指出问题的部分）
{original_content}

## 全局设定
- 题材：{genre}

请直接输出修改后的完整章节正文。**不要**输出说明文字、不要输出修改对照、不要输出自检清单。
只输出正文内容。

如果某个段落不需要修改，请直接原样保留原文，不要改写。"""
```

- [ ] **Step 5: 更新 DEFAULT_PROMPTS，删除旧常量引用**

将 `DEFAULT_PROMPTS` 中的 `"review"` 和 `"rewrite"` 从字符串改为 dict，同时删除对旧常量 `REVIEW_CHAPTER_PROMPT` 和 `REWRITE_CHAPTER_PROMPT` 的引用：

```python
DEFAULT_PROMPTS = {
    "outline_generation": _apply_forbidden_words_brief_to_prompt(OUTLINE_GENERATION_PROMPT),
    "chapter_outline_generation": GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT,
    "chapter_content_generation": {
        "system": _apply_forbidden_words_to_prompt(CHAPTER_CONTENT_SYSTEM_PROMPT),
        "user": CHAPTER_CONTENT_USER_PROMPT,
    },
    "review": {
        "system": _apply_forbidden_words_list_to_prompt(REVIEW_SYSTEM_PROMPT),
        "user": REVIEW_USER_PROMPT,
    },
    "rewrite": {
        "system": _apply_forbidden_words_list_to_prompt(REWRITE_SYSTEM_PROMPT),
        "user": REWRITE_USER_PROMPT,
    },
    "character_generation": CHARACTER_GENERATION_PROMPT,
    "relation_generation": RELATION_GENERATION_PROMPT,
}
```

同时删除 `REVIEW_CHAPTER_PROMPT` 和 `REWRITE_CHAPTER_PROMPT` 两个旧常量定义（它们已无任何引用者，保留是死代码/技术债）。

- [ ] **Step 6: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.prompts import DEFAULT_PROMPTS; r=DEFAULT_PROMPTS['review']; w=DEFAULT_PROMPTS['rewrite']; assert isinstance(r, dict) and 'system' in r and 'user' in r; assert isinstance(w, dict) and 'system' in w and 'user' in w; print('ok')"`

Expected: `ok`

- [ ] **Step 7: 提交**

```bash
git add backend/app/agents/prompts.py
git commit -m "feat(prompts): add system/user split for review and rewrite prompts, remove old single-string constants"
```

---

### Task 4: 更新 _build_prompts_dict 支持 dict 格式的 review/rewrite

**Files:**
- Modify: `backend/app/api/workflow.py:283-308`

- [ ] **Step 1: 修改 _build_prompts_dict**

将 `review` 和 `rewrite` 从字符串改为 dict。由于 Task 3 已将 DEFAULT_PROMPTS 中两者改为 dict 格式，无需 isinstance 防御，直接按 dict 访问：

```python
def _build_prompts_dict(db: Session) -> dict[str, str | dict]:
    """构建预加载的 prompts 字典（所有节点共享）

    chapter_content_generation, review, rewrite 为 dict 格式 {"system": ..., "user": ...}，
    system 模板始终使用默认值（角色定位+规则+禁用词+上下文），
    user 模板可由用户自定义（DB 中存储）。
    """
    from app.services.prompt_loader import get_system_prompt
    from app.agents.prompts import DEFAULT_PROMPTS

    # dict 格式的 prompt：system 固定默认值，user 可自定义
    default_cc = DEFAULT_PROMPTS["chapter_content_generation"]
    default_review = DEFAULT_PROMPTS["review"]
    default_rewrite = DEFAULT_PROMPTS["rewrite"]

    return {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
        "chapter_outline_generation": get_system_prompt(db, "chapter_outline_generation"),
        "chapter_content_generation": {
            "system": default_cc["system"] if isinstance(default_cc, dict) else default_cc,
            "user": get_system_prompt(db, "chapter_content_generation"),
        },
        "review": {
            "system": default_review["system"],
            "user": get_system_prompt(db, "review"),
        },
        "rewrite": {
            "system": default_rewrite["system"],
            "user": get_system_prompt(db, "rewrite"),
        },
    }
```

注意：`chapter_content_generation` 保留 isinstance 防御（历史遗留，本次不动），新增的 review/rewrite 直接按 dict 访问。

- [ ] **Step 2: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.api.workflow import _build_prompts_dict; from app.database import SessionLocal; db=SessionLocal(); d=_build_prompts_dict(db); db.close(); r=d['review']; w=d['rewrite']; assert isinstance(r, dict) and 'system' in r and 'user' in r; assert isinstance(w, dict) and 'system' in w and 'user' in w; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/workflow.py
git commit -m "feat(workflow): support dict format for review/rewrite prompts in _build_prompts_dict"
```

---

### Task 5: 审核节点改为 system/user 双层消息 + 前文上下文

**Files:**
- Modify: `backend/app/agents/nodes/review.py`

- [ ] **Step 1: 添加 import 和 _build_review_messages 辅助函数**

在 `review.py` 顶部 import 中添加：

```python
from app.agents.context_strategy import FulltextContentStrategy
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    get_prompts_from_state,
)
```

删除原有的 `from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info`。

在 `_parse_review_result_legacy` 函数之后、`review_chapter_node` 之前添加：

```python
def _build_review_messages(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    strictness: str = "standard",
) -> list[dict]:
    """构建审核的 system/user 消息列表

    将前文上下文、人物档案、世界观、审核维度放入 system message，
    章节大纲、章节正文、题材/风格/严格度放入 user message。
    """
    info = state.get("collected_info", {})
    written_chapters = state.get("written_chapters", [])
    chapter_number = chapter_outline.get("chapter_number", 1)

    # 格式化章节大纲
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定、关系、演变
    chars_str = format_characters_info(state)
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_characters_str = chars_str + relations_str + evolution_str

    # 格式化世界观
    world_str = format_world_setting(state)

    # 前文上下文
    strategy = FulltextContentStrategy()
    previous_context = strategy.build_previous_context(written_chapters, chapter_number)

    # 获取 system/user 模板
    system_template, user_template = get_prompts_from_state(state, "review")

    # 构建 messages
    messages = []
    if system_template:
        system_content = system_template.format(
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    user_content = user_template.format(
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("novelType", "未指定"),
        style_preference=info.get("stylePreference", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages
```

- [ ] **Step 2: 修改 review_chapter_node 使用新消息构建**

替换 `review_chapter_node` 函数体：

```python
async def review_chapter_node(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    llm: LLMService,
    strictness: str = "standard",
    db: Session | None = None,
) -> Dict[str, Any]:
    """审核章节内容（使用 system/user 双层消息 + 前文上下文）"""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # 构建 system/user 消息
        messages = _build_review_messages(state, chapter_content, chapter_outline, strictness)

        # 流式调用 LLM
        response = ""
        async for chunk in llm.chat_stream(messages):
            response += chunk

        result = parse_review_result(response)
        result["raw_response"] = response

        return result
    finally:
        if should_close:
            db.close()
```

- [ ] **Step 3: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.review import review_chapter_node, review_node, _build_review_messages; print('ok')"`

Expected: `ok`

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/nodes/review.py
git commit -m "feat(review): add previous context via system/user dual-message structure"
```

---

### Task 6: 重写节点改为 system/user 双层消息 + 前文上下文

**Files:**
- Modify: `backend/app/agents/nodes/rewrite.py`

- [ ] **Step 1: 添加 import 和 _build_rewrite_messages 辅助函数**

在 `rewrite.py` 顶部 import 中添加：

```python
from app.agents.context_strategy import FulltextContentStrategy
from app.agents.nodes.utils import (
    _format_chapter_outline_str,
    format_characters_info,
    format_relations_info,
    format_evolution_info,
    format_world_setting,
    get_prompts_from_state,
)
```

删除原有的 `from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info`。

在 `rewrite_chapter_node` 函数之前添加：

```python
def _build_rewrite_messages(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
) -> list[dict]:
    """构建重写的 system/user 消息列表

    将前文上下文、人物档案、世界观、修改原则放入 system message，
    章节大纲、审核反馈、原始章节、题材放入 user message。
    """
    info = state.get("collected_info", {})
    written_chapters = state.get("written_chapters", [])
    chapter_number = chapter_outline.get("chapter_number", 1)

    # 格式化章节大纲
    outline_str = _format_chapter_outline_str(chapter_outline)

    # 格式化人物设定、关系、演变
    chars_str = format_characters_info(state)
    relations_str = format_relations_info(state, chapter_number)
    evolution_str, _ = format_evolution_info(state, chapter_number)
    combined_characters_str = chars_str + relations_str + evolution_str

    # 格式化世界观
    world_str = format_world_setting(state)

    # 前文上下文
    strategy = FulltextContentStrategy()
    previous_context = strategy.build_previous_context(written_chapters, chapter_number)

    # 获取 system/user 模板
    system_template, user_template = get_prompts_from_state(state, "rewrite")

    # 构建 messages
    messages = []
    if system_template:
        system_content = system_template.format(
            previous_context=previous_context,
            main_characters=combined_characters_str,
            world_setting=world_str,
        )
        messages.append({"role": "system", "content": system_content})

    user_content = user_template.format(
        chapter_outline=outline_str,
        review_feedback=review_feedback,
        original_content=original_content,
        genre=info.get("novelType", "未指定"),
    )
    messages.append({"role": "user", "content": user_content})

    return messages
```

- [ ] **Step 2: 修改 rewrite_chapter_node 使用新消息构建**

替换 `rewrite_chapter_node` 函数体：

```python
async def rewrite_chapter_node(
    state: NovelState,
    chapter_outline: dict,
    original_content: str,
    review_feedback: str,
    llm: LLMService,
    db: Session | None = None,
) -> str:
    """根据审核反馈重写章节（使用 system/user 双层消息 + 前文上下文）"""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # 构建 system/user 消息
        messages = _build_rewrite_messages(state, chapter_outline, original_content, review_feedback)

        # 流式调用 LLM
        response = ""
        async for chunk in llm.chat_stream(messages):
            response += chunk

        return response
    finally:
        if should_close:
            db.close()
```

- [ ] **Step 3: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.agents.nodes.rewrite import rewrite_chapter_node, rewrite_node, _build_rewrite_messages; print('ok')"`

Expected: `ok`

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/nodes/rewrite.py
git commit -m "feat(rewrite): add previous context via system/user dual-message structure"
```

---

### Task 7: 适配 chapters.py 审核 SSE 端点

**Files:**
- Modify: `backend/app/api/chapters.py:827-847`

`chapters.py` 的审核 SSE 端点自行构建 prompt（L827-847），直接用 `get_system_prompt(db, "review").format(...)` 构造单条 user message。改成 dict 格式后 `get_system_prompt` 返回的是 user 模板字符串，旧代码会崩溃。

- [ ] **Step 1: 修改 stream_generator 中的审核 prompt 构建逻辑**

将 L827-847 的 prompt 构建和 LLM 调用替换为调用 `_build_review_messages`：

```python
            # 构建审核消息（使用共享的 _build_review_messages）
            from app.agents.nodes.review import _build_review_messages

            messages = _build_review_messages(
                initial_state, chapter.content, chapter_outline_dict, strictness
            )

            # 流式调用 LLM，逐块发送审核文本
            response = ""
            async for chunk in llm.chat_stream(messages):
                response += chunk
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
```

删除原有的 `from app.services.prompt_loader import get_system_prompt` 和 `from app.agents.nodes.utils import _format_chapter_outline_str, format_characters_info` import，以及手动构建 prompt 的代码。

- [ ] **Step 2: 验证 import 无报错**

Run: `docker exec novelagent-backend-1 python -c "from app.api.chapters import router; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/chapters.py
git commit -m "fix(chapters): adapt review SSE endpoint to use _build_review_messages"
```

---

### Task 8: 运行后端测试验证

**Files:** 无修改

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`

Expected: 全部 PASS。重点关注：
- `test_review.py`
- `test_rewrite.py`
- `test_context_strategy.py`
- `test_agents.py`

- [ ] **Step 2: 如有测试失败，修复并重新运行**

常见可能失败原因：
- 旧测试 mock 了 `prompts["review"]` 为字符串，需改为 dict 格式
- `rewrite_with_retry` 调用 `review_chapter_node`，签名变化需适配

- [ ] **Step 3: 提交修复（如有）**

```bash
git add -u
git commit -m "fix: update tests for review/rewrite system/user prompt split"
```
