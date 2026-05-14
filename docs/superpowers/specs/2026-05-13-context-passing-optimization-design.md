# 上下文传递机制优化设计

## 背景

当前上下文传递机制存在以下问题：

1. **章节大纲生成**只传最近3章概要，前面章节的伏笔和情节线完全丢失
2. **审核节点**没有传递前文上下文，无法判断与前文的衔接
3. **重写节点**没有传递前文上下文，重写后可能与前文脱节
4. **混合策略暂不实现**，长篇小说只能全文传递

## 优化项

### 1. 章节大纲生成：传入全部已生成章节大纲

**文件：** `backend/app/agents/nodes/chapter_generation.py`

**当前代码** (`generate_single_chapter_outline`，约 L194-199)：
```python
# Only show last 3 chapters for context
recent = previous_chapters[-3:]
previous_info = "前几章概要：\n" + "\n".join([
    f"- 第{c['chapter_number']}章《{c.get('title', '')}》：{c.get('plot', '')[:50]}..."
    for c in recent
])
```

**改为：** 传入全部已生成章节大纲，传递完整字段（不再只传截断的 plot）：
```python
previous_info = "已生成章节大纲：\n" + "\n".join([
    f"第{c['chapter_number']}章《{c.get('title', '')}》\n"
    f"场景：{c.get('scene', '')}\n"
    f"人物：{c.get('characters', '')}\n"
    f"情节：{c.get('plot', '')}\n"
    f"冲突：{c.get('conflict', '')}\n"
    f"转折：{c.get('turning_point', '无')}\n"
    f"钩子：{c.get('hook', '')}\n"
    f"衔接：{c.get('transition', '')}\n"
    f"结局：{c.get('ending', '')}"
    for c in previous_chapters
])
```

**理由：** 每条章节大纲约200-300字，40章全部传入约8000-12000字，不会溢出。传递完整字段可确保伏笔追踪、人物状态、场景衔接的连贯性。

### 2. 审核节点：添加前文上下文

**文件：** `backend/app/agents/prompts.py`，`backend/app/api/workflow.py`

**改动：**

2a. 在 `prompts.py` 新增 `REVIEW_SYSTEM_PROMPT` 和 `REVIEW_USER_PROMPT`，`REWRITE_SYSTEM_PROMPT` 和 `REWRITE_USER_PROMPT` 常量。将 `DEFAULT_PROMPTS["review"]` 和 `DEFAULT_PROMPTS["rewrite"]` 改为 dict 格式（与 `chapter_content_generation` 一致）：
```python
"review": {
    "system": _apply_forbidden_words_to_prompt(REVIEW_SYSTEM_PROMPT),
    "user": REVIEW_USER_PROMPT,
},
"rewrite": {
    "system": _apply_forbidden_words_to_prompt(REWRITE_SYSTEM_PROMPT),
    "user": REWRITE_USER_PROMPT,
},
```

2b. 在 `workflow.py` 更新 `_build_prompts_dict()` 支持 dict 格式的 review/rewrite（参考 `chapter_content_generation` 的处理方式）。

2c. 新增 `REVIEW_SYSTEM_PROMPT`，包含：
- 前文上下文 `{previous_context}`（使用上下文策略构建）
- 人物档案 `{main_characters}`
- 世界观 `{world_setting}`
- 审核维度和评分标准（从现有 `REVIEW_CHAPTER_PROMPT` 迁移）

2d. `REVIEW_USER_PROMPT` 只包含：
- 章节大纲 `{chapter_outline}`
- 章节正文 `{chapter_content}`
- 题材/风格/严格度

2e. `review.py` 中 `review_chapter_node()` 和 `review_node()` 改为从 `state["_prompts"]["review"]` 提取 system/user dict，构建 `system/user` 双层消息，添加前文上下文（使用 `FulltextContentStrategy.build_previous_context()`）。

### 3. 重写节点：添加前文上下文

**文件：** `backend/app/agents/nodes/rewrite.py`，`backend/app/agents/prompts.py`

**改动：**

3a. 将 `REWRITE_SYSTEM_PROMPT` 和 `REWRITE_USER_PROMPT` 添加到 `DEFAULT_PROMPTS` 作为 dict（见 2a）。

3b. `REWRITE_SYSTEM_PROMPT` 包含：
- 前文上下文 `{previous_context}`（使用上下文策略构建）
- 人物档案 `{main_characters}`
- 世界观 `{world_setting}`
- 修改原则和反AI味规则

3c. `REWRITE_USER_PROMPT` 只包含：
- 章节大纲 `{chapter_outline}`
- 审核反馈 `{review_feedback}`
- 原始章节 `{original_content}`
- 题材

3d. `rewrite.py` 中 `rewrite_chapter_node()` 和 `rewrite_node()` 改为从 `state["_prompts"]["rewrite"]` 提取 system/user dict，构建 `system/user` 双层消息，添加前文上下文。

### 4. 上下文策略：保留空实现

**文件：** `backend/app/agents/context_strategy.py`

`HybridContentStrategy` 和 `SummaryContentStrategy` 暂不实现，保留 `NotImplementedError`。当前所有场景统一使用 `FulltextContentStrategy`，后续有长篇需求时再补充。

## 涉及文件

| 文件 | 修改类型 |
|------|----------|
| `backend/app/agents/context_strategy.py` | 不改动（混合策略暂不实现） |
| `backend/app/api/workflow.py` | 更新 `_build_prompts_dict()` 支持 dict 格式的 review/rewrite |
| `backend/app/agents/nodes/chapter_generation.py` | 修改章节大纲生成的前文传递为全部章节 |
| `backend/app/agents/nodes/review.py` | 添加前文上下文，改为 system/user 双层消息 |
| `backend/app/agents/nodes/rewrite.py` | 添加前文上下文，改为 system/user 双层消息 |
| `backend/app/agents/prompts.py` | 新增 REVIEW_SYSTEM_PROMPT、REWRITE_SYSTEM_PROMPT，调整现有审核/重写 prompt 为 user message |
| `backend/tests/test_context_strategy.py` | 不改动 |

## 不涉及

- 前端代码不改动
- 数据库 schema 不改动
- API 接口不改动
- 大纲生成节点不改动（已有完整上下文传递）
