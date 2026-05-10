# 章节字数统一优化设计文档

## 日期

2026-05-10

## 问题

章节正文生成字数不规范。灵感页面的"每章字数"（如 2000-2500）只用于计算章节数，未传递给章节大纲和正文生成节点。章节大纲的 `target_words` 由 AI 自由发挥，波动很大，导致最终生成的章节字数与用户预期不符。

附带 Bug：`outline_generation.py` 中 `int("2000-2500")` 只解析出 2000，range 格式处理有误。

## 当前链路

```
灵感页面 wordsPerChapter ("2000-2500")
    ↓ 只用于计算章节数，不传递给后续节点
章节大纲生成（AI 自由发挥预计字数，可能 5000、8000）
    ↓ target_words 波动大
章节正文生成（使用 target_words → 字数不规范）
```

## 优化目标

1. 章节大纲生成时，AI 在用户设定的"每章字数"区间内生成预计字数
2. 章节正文生成时，使用用户设定的"每章字数"区间替代单一 target_words
3. 修复 range 格式解析 bug
4. 不改变当前系统功能流程逻辑表现

## 设计方案

### 改动 1：新增解析工具函数

**文件**：`backend/app/agents/nodes/utils.py`

新增 `parse_words_per_chapter(collected_info: dict) -> tuple[int, int, str]` 函数：

- 输入：collected_info 字典
- 输出：(下限, 上限, 显示文本)
- 处理逻辑：
  - `"2000-2500"` → (2000, 2500, "2000-2500字")
  - `"custom"` + `customWordsPerChapter=3000` → (2700, 3300, "约3000字")，上下浮动 10%
  - 空值 → (2000, 3000, "2000-3000字")，使用默认值

**目的**：统一解析逻辑，修复 `int("2000-2500")` bug，供所有节点复用。

### 改动 2：章节大纲生成 prompt 注入字数约束

**文件**：`backend/app/agents/prompts.py`

修改 `GENERATE_SINGLE_CHAPTER_OUTLINE_PROMPT`：

- 新增 `{words_per_chapter}` 占位符
- `预计字数：XXXX 字` → `预计字数：XXXX 字（要求：在{words_per_chapter}范围内）`

**文件**：`backend/app/agents/nodes/chapter_generation.py`

修改 `generate_single_chapter_outline`：

- 从 `state["collected_info"]` 调用 `parse_words_per_chapter` 获取区间
- 传入 prompt 的 `{words_per_chapter}` 参数（使用显示文本，如 "2000-2500字"）

### 改动 3：章节大纲解析时校验 target_words

**文件**：`backend/app/agents/nodes/chapter_generation.py`

修改 `parse_single_chapter_outline`：

- 新增 `words_per_chapter_range: tuple[int, int] | None = None` 参数
- 解析出 target_words 后，若提供了区间：
  - `target_words < lower` → `target_words = lower`
  - `target_words > upper` → `target_words = upper`
  - 区间内的值保持不变（尊重 AI 的合理浮动）
- 区间外的情况记录 warning 日志

### 改动 4：章节正文生成使用区间格式

**文件**：`backend/app/agents/prompts.py`

修改 `GENERATE_CHAPTER_CONTENT_PROMPT`：

- 将 `{target_words}` 占位符改为 `{words_per_chapter_range}`
- prompt 中 "本章目标字数：{target_words} 字" → "本章目标字数：{words_per_chapter_range}"
- 结尾 "字数约 {target_words} 字" → "字数约 {words_per_chapter_range}"

**文件**：`backend/app/agents/nodes/chapter_generation.py`

修改 `generate_chapter_content_stream` 和 `generate_chapter_content_node`：

- 从 `state["collected_info"]` 调用 `parse_words_per_chapter` 获取区间
- prompt 使用区间显示文本替代单一 target_words
- `_calc_max_tokens` 使用区间上限（upper）计算，确保不截断

### 改动 5：修复 outline_generation.py 的 range 解析

**文件**：`backend/app/agents/nodes/outline_generation.py`

修改 `prepare_outline_prompt`：

- 使用 `parse_words_per_chapter` 替代手动的 `int(words_per_chapter_str)` 解析
- 计算章节数时使用区间中值 `(lower + upper) // 2`

### 优化后链路

```
灵感页面 wordsPerChapter ("2000-2500")
    ↓ parse_words_per_chapter 统一解析
章节大纲生成（prompt 注入"2000-2500字"约束，解析时钳制到区间）
    ↓ target_words 在用户设定范围内
章节正文生成（使用"2000-2500字"区间，max_tokens 按上限计算）
    ↓ 字数规范
```

## 不改动的部分

- `NovelState` 结构（collected_info 已包含 wordsPerChapter）
- 灵感页面 UI
- 工作流节点连接关系
- 数据库模型
- 前端逻辑
- 重写节点（rewrite 使用原文长度，不受影响）

## 文件改动清单

| 文件 | 改动 |
|------|------|
| `backend/app/agents/nodes/utils.py` | 新增 `parse_words_per_chapter` 工具函数 |
| `backend/app/agents/prompts.py` | 章节大纲 prompt 增加 `words_per_chapter` 占位符；正文 prompt 的 `target_words` 改为 `words_per_chapter_range` |
| `backend/app/agents/nodes/chapter_generation.py` | 大纲生成注入字数约束、解析时钳制、正文生成使用区间 |
| `backend/app/agents/nodes/outline_generation.py` | 使用 `parse_words_per_chapter` 修复 range 解析 bug |

## 风险评估

- **低风险**：不修改工作流节点连接关系，不修改数据库模型
- **向后兼容**：`parse_words_per_chapter` 对空值/异常值有默认处理
- **可回退**：prompt 变更为纯文本替换，可快速回退
