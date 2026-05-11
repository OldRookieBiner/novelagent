# Phase 3 设计文档：System Message + 上下文策略 + 审核解析解耦

## 背景

Phase 1/2 已修复所有 P0 数据丢失问题和 Prompt 加载合规性。Phase 3 解决三个架构层面的问题：

1. **所有 prompt 都以 user message 发送** — LLM 对约束遵循度低，角色设定和任务输入混在一起
2. **前文上下文只取上一章最后 500 字** — 短篇足够放全文但没用，长篇没有摘要机制
3. **审核解析器与 prompt 格式强绑定** — 正则硬编码了 `【审核结果】`、`【问题列表】` 等标记，改 prompt 可能导致解析静默失败

## 评估得分（优化前）

| 维度 | Phase 1 前 | Phase 2 后 | Phase 3 目标 |
|------|-----------|-----------|-------------|
| Prompt 质量 | 7/10 | 7.5/10 | 9/10 |
| 上下文传递完整性 | 4/10 | 6/10 | 9/10 |
| Prompt 加载一致性 | 3/10 | 10/10 | 10/10 |
| 上下文利用率 | 5/10 | 6/10 | 9/10 |
| 可维护性 | 4/10 | 7/10 | 9/10 |

---

## Fix 1：System Message 机制

### 问题

当前章节正文生成将角色定位、写作规则、禁用词、人物设定、前文信息、章节大纲全部塞在一条 user message 中。LLM 对 system message 中的约束遵循度高于 user message。

### 修改方案

将 `GENERATE_CHAPTER_CONTENT_PROMPT` 拆分为 system 部分和 user 部分：

**system message 内容：**
- 角色定位（"你是一位获得茅盾文学奖的当代小说家"）
- 写作原则（展示而非讲述、禁用词表、自检清单）
- 前文上下文（由上下文策略生成）
- 人物档案 + 关系 + 演变
- 世界观

**user message 内容：**
- 章节大纲
- 前章结尾（最后 500 字衔接参考）
- 题材 / 最低字数 / 风格

**新增文件：** `backend/app/agents/prompts.py` 中新增两个模板：
- `CHAPTER_CONTENT_SYSTEM_PROMPT` — system message 模板
- `CHAPTER_CONTENT_USER_PROMPT` — user message 模板

**修改文件：** `backend/app/agents/nodes/chapter_generation.py`
- `generate_chapter_content_stream()` 和 `generate_chapter_content_node()`
- `llm.chat_stream([{"role": "user", "content": prompt}])` → `llm.chat_stream([system_msg, user_msg])`

**DEFAULT_PROMPTS 更新：**
- `"chapter_content_generation"` 改为 `{"system": ..., "user": ...}` 字典格式
- 各节点的 prompt 获取逻辑适配：`prompts["chapter_content_generation"]` 可能是 str（旧格式）或 dict（新格式），需兼容
- 具体兼容逻辑：在 `chapter_generation.py` 的 prompt 获取处增加类型判断：

```python
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
```

### LangGraph 合规性

- system/user 消息构建在节点函数内完成，不改变节点签名
- `_prompts` 中存储的是模板字符串，`chat_stream` 调用时组装为 messages 列表
- 不引入新的 state 字段

---

## Fix 2：上下文策略（Context Strategy）

### 问题

当前章节生成只取上一章最后 500 字，短篇完全可以放全文，但缺少机制支持。

### 设计

**策略基类：** `backend/app/agents/context_strategy.py`

```python
from abc import ABC, abstractmethod

class ContextStrategy(ABC):
    """上下文策略基类 — 定义前文上下文的构建方式"""

    @abstractmethod
    def build_previous_context(self, written_chapters: list[dict], current_chapter: int) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表 [{chapter_number, title, content, ...}]
            current_chapter: 当前要写的章节号

        Returns:
            前文上下文文本（放入 system message）
        """
        pass


class FulltextContentStrategy(ContextStrategy):
    """短篇策略：所有已写章节全文放入上下文"""

    def build_previous_context(self, written_chapters, current_chapter):
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
    """中篇策略：最近 N 章全文 + 更早章节摘要（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
        raise NotImplementedError("HybridContentStrategy 尚未实现")


class SummaryContentStrategy(ContextStrategy):
    """长篇策略：所有前文摘要 + 最近 1 章结尾（Phase 4 实现）"""
    def build_previous_context(self, written_chapters, current_chapter):
        raise NotImplementedError("SummaryContentStrategy 尚未实现")
```

**策略选择函数：**

```python
def get_context_strategy(target_words: int) -> ContextStrategy:
    """根据目标字数选择上下文策略

    - ≤ 10 万字（约 30 章内）→ Fulltext（短篇）
    - ≤ 30 万字 → Hybrid（中篇，Phase 4）
    - > 30 万字 → Summary（长篇，Phase 4）
    """
    if target_words <= 100000:
        return FulltextContentStrategy()
    else:
        return FulltextContentStrategy()  # 暂时回退到 fulltext，后续替换
```

**与 System Message 的结合：**

`CHAPTER_CONTENT_SYSTEM_PROMPT` 模板中新增 `{previous_context}` 占位符：

```
## 前文（你需要确保本章与前文在情节、人物、风格上自然衔接）
{previous_context}
```

节点函数中：

```python
target_words = info.get("targetWords", 100000)
if isinstance(target_words, str):
    target_words = int(target_words)
strategy = get_context_strategy(target_words)
previous_context = strategy.build_previous_context(written_chapters, current_chapter)
```

**数据来源：** 前文全文从 `state["written_chapters"]` 读取，无需额外 DB 查询。

### 与小说长度的关联

前端灵感配置已有 `targetWords` 选项（5万/10万/30万/50万/自定义），后端根据此值自动选择策略。用户无需额外配置。

### Token 消耗评估（Fulltext 策略）

| 章节数 | 前文全文 | 约 token | 128K 模型余量 |
|--------|----------|----------|--------------|
| 5 章 | ~15K 字 | ~20K | 充足 |
| 10 章 | ~30K 字 | ~40K | 充足 |
| 20 章 | ~60K 字 | ~80K | 偏紧，需 Hybrid |
| 30 章 | ~90K 字 | ~120K | 超限，必须 Hybrid/Summary |

10 万字约 30 章左右，Fulltext 策略在短篇范围内安全。

---

## Fix 3：审核解析器解耦 — JSON 结构化输出

### 问题

`parse_review_result()` 用正则硬编码了 prompt 的输出标记：
- `"【审核结果】通过" in response` — 精确字符串匹配
- `r"情节一致性[：:]\s*(\d+)/10"` — 依赖维度名称和分数格式
- `r"【问题列表】(.+?)【修改建议】"` — 依赖两个标记的精确出现和顺序

改 prompt → 解析可能静默失败（返回默认值，不报错）。

### 修改方案

**3a. 修改 REVIEW_CHAPTER_PROMPT 输出格式要求**

从自由文本标记格式改为 JSON 格式：

```
## 输出格式

请严格按照以下 JSON 格式输出审核结果，不要输出其他内容：

```json
{
  "passed": true或false,
  "scores": {
    "plot_consistency": 1-10,
    "character_consistency": 1-10,
    "writing_quality": 1-10,
    "emotional_tension": 1-10,
    "ai_flavor": 1-10,
    "outline_deviation": 1-10
  },
  "issues": [
    {"type": "情节矛盾|人设偏离|文笔问题|情感不足|AI味|大纲偏离", "location": "具体位置", "description": "问题描述"}
  ],
  "suggestions": "修改建议，针对每个问题给出可操作的修改方向"
}
```

通过标准：
- plot_consistency、character_consistency、writing_quality、emotional_tension 均 ≥ 6
- ai_flavor ≤ 3
- outline_deviation ≤ 4
```

**3b. 重写 parse_review_result()**

```python
def parse_review_result(response: str) -> Dict[str, Any]:
    """解析审核结果（JSON 格式）"""
    result = {"passed": False, "scores": {}, "issues": [], "suggestions": ""}

    # 提取 JSON（兼容 LLM 在 JSON 前后加文字的情况）
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        # 回退：尝试旧格式解析
        return _parse_review_result_legacy(response)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return _parse_review_result_legacy(response)

    result["passed"] = data.get("passed", False)
    result["scores"] = data.get("scores", {})
    result["issues"] = data.get("issues", [])
    result["suggestions"] = data.get("suggestions", "")

    return result


def _parse_review_result_legacy(response: str) -> Dict[str, Any]:
    """旧格式回退解析（兼容期）"""
    # 当前正则逻辑原封不动搬过来
    ...
```

**3c. check_review_passed() 更新**

新增 `outline_deviation` 维度检查：

```python
def check_review_passed(review_result: Dict[str, Any]) -> bool:
    scores = review_result.get("scores", {})

    for key in ["plot_consistency", "character_consistency", "writing_quality", "emotional_tension"]:
        if scores.get(key, 0) < 6:
            return False

    if scores.get("ai_flavor", 10) > 3:
        return False

    if scores.get("outline_deviation", 0) > 4:
        return False

    return True
```

### 向后兼容

- `_parse_review_result_legacy()` 保留旧正则逻辑作为回退
- 如果 LLM 返回的不是 JSON，自动降级到旧解析
- 数据库中已有的 `review_result` 字段格式不受影响（它存的是解析后的 dict，不是原始 LLM 输出）

---

## 影响范围

| 文件 | 改动类型 | 风险 |
|------|---------|------|
| `backend/app/agents/context_strategy.py` | 新建 | 低：纯函数，无副作用 |
| `backend/app/agents/prompts.py` | 拆分模板 + 改 review 输出格式 | 中：模板变更影响生成行为 |
| `backend/app/agents/nodes/chapter_generation.py` | system/user 消息拆分 | 中：核心生成逻辑 |
| `backend/app/agents/nodes/review.py` | 重写 parse_review_result | 中：解析逻辑变更 |
| `backend/tests/test_review.py` | 更新测试用例 | 低 |

---

## 不在 Phase 3 范围的内容

| 项目 | 原因 | 归属 |
|------|------|------|
| Hybrid/Summary 策略实现 | 需要 DB 摘要字段和摘要生成机制 | Phase 4 |
| 大纲/审核/重写节点的 System Message | 优先级低于章节正文 | Phase 4 |
| chapters 表新增 summary 字段 | 仅 Hybrid/Summary 策略需要 | Phase 4 |
| 前端上下文策略选择 UI | 后端自动判断，暂不需要 | Phase 4 |

---

## 验证方案

1. 运行现有测试：`docker exec novelagent-backend-1 pytest -v`
2. 手动测试：创建短篇项目（5 万字）→ 生成大纲 → 生成章节 → 检查：
   - 章节正文中 LLM 是否正确引用前文细节（非仅最后 500 字）
   - 审核结果是否以 JSON 格式返回并正确解析
   - 旧项目审核结果回退到旧解析是否正常
3. Token 消耗观察：对比 Phase 2 前后单章生成的 token 用量
