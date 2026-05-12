# 提示词质量优化设计文档

## 背景

当前7个生成节点的提示词质量差异明显：

| 等级 | 节点 | 评分 | 核心问题 |
|------|------|------|----------|
| A | 章节正文、审核 | 89-91 | 微调即可 |
| B | 大纲、章节大纲、重写 | 82-88 | 有明确改进点 |
| C | 角色生成、关系生成 | 74-76 | 需重点优化 |

## 设计目标

1. **统一人物设定标准** — 简化章节正文人物要求，与角色生成输出对齐
2. **增强反AI能力** — 全部7个节点统一加入禁用词检查
3. **增强上下文** — 角色/关系生成增加情节节点、情感曲线输入
4. **保持系统兼容性** — 输出格式不变，节点代码仅调整传参

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 人物设定统一方向 | 简化章节正文人物要求 | 角色生成输出是源头，改源头影响下游所有节点；简化消费端更安全 |
| 优化范围 | 全部7个 | C类大改、B类中改、A类微调 |
| 禁用词策略 | 全部7个节点统一 | AI味不仅出现在正文，大纲/角色描述同样存在 |
| 输出格式 | 保持现状 | 不同节点输出性质不同，强行统一会降低质量 |
| 角色/关系上下文增强 | 增加 plot_points + emotional_curve | 数据已在 state 中，只需传参，无需新功能 |

---

## 各节点优化方案

### 1. 角色生成提示词（76→85分）

**问题**：输入信息过少（仅 outline_summary + world_era），缺少情节节点和情感曲线；无AI味检查。

**修改**：

#### 1a. 新增输入变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `{plot_points}` | state.outline_plot_points | 让角色与情节节点关联生成 |
| `{emotional_curve}` | state.outline_emotional_curve | 让角色弧光与情感曲线匹配 |

#### 1b. 新增质量约束

- 增加"反AI味"规则：性格描述必须用具体行为特征而非抽象形容词，禁止使用禁用词列表中的词汇
- 增加"角色功能"要求：每个角色必须明确标注其在大纲情节节点中承担的任务
- 增加自检清单

#### 1c. 节点代码修改

文件：`backend/app/agents/nodes/character_generation.py`

```python
# 现有代码
prompt = prompt_template.format(
    outline_summary=outline_summary,
    world_era=world_era,
)

# 修改后
plot_points = state.get("outline_plot_points", [])
plot_points_str = "\n".join([f"{i+1}. {p.get('event', '')}" for i, p in enumerate(plot_points)]) if plot_points else "未提供"
emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

prompt = prompt_template.format(
    outline_summary=outline_summary,
    world_era=world_era,
    plot_points=plot_points_str,
    emotional_curve=emotional_curve,
)
```

---

### 2. 关系生成提示词（74→83分）

**问题**：输入信息不足；无冲突点要求；无AI味检查。

**修改**：

#### 2a. 新增输入变量

| 变量 | 来源 | 说明 |
|------|------|------|
| `{plot_points}` | state.outline_plot_points | 让关系与情节冲突关联 |
| `{emotional_curve}` | state.outline_emotional_curve | 让关系发展与情感曲线匹配 |

#### 2b. 新增质量约束

- 增加"关系冲突点"要求：描述字段必须说明"为什么这两人会产生冲突/合作"
- 增加"反AI味"规则：描述必须具体，禁止使用"复杂""微妙""纠葛"等空洞词
- 增加自检清单

#### 2c. 节点代码修改

文件：`backend/app/agents/nodes/relation_generation.py`

```python
# 现有代码
prompt = default_prompt.format(
    characters_text=characters_text,
    world_era=world_era,
    outline_summary=outline_summary,
)

# 修改后
plot_points = state.get("outline_plot_points", [])
plot_points_str = "\n".join([f"{i+1}. {p.get('event', '')}" for i, p in enumerate(plot_points)]) if plot_points else "未提供"
emotional_curve = state.get("outline_emotional_curve", "") or "未提供"

prompt = default_prompt.format(
    characters_text=characters_text,
    world_era=world_era,
    outline_summary=outline_summary,
    plot_points=plot_points_str,
    emotional_curve=emotional_curve,
)
```

---

### 3. 大纲生成提示词（82→85分）

**问题**：无AI味检查；无自检清单。

**修改**：

#### 3a. 新增自检清单

在"严格注意事项"后追加自检清单：

```
## 输出自检（输出前逐项确认）

1. 【完整性】六大板块是否全部输出？标题、概述、世界观、情节节点、情感曲线、伏笔地图？
2. 【伏笔密度】前1/3章节是否至少埋设5个伏笔，且全部在后文有回收？
3. 【AI味检查】全文是否避免了以下空洞表达：[禁用词简表]
4. 【章节数匹配】情节节点数量是否与目标章节数匹配？
5. 【情感起伏】情感曲线是否至少有3次起伏？
```

#### 3b. 禁用词简表

大纲生成不需要完整的36个禁用词列表，只需一个精简版（约10个最常见的大纲场景AI味词）：

```python
OUTLINE_FORBIDDEN_WORDS_BRIEF = [
    "错综复杂", "扑朔迷离", "暗流涌动", "波澜壮阔",
    "命运交织", "跌宕起伏", "扣人心弦", "引人入胜",
    "令人唏嘘", "发人深省",
]
```

在 constants.py 中新增，在 prompts.py 中引用。

---

### 4. 章节大纲生成提示词（88→90分）

**问题**：无AI味检查；字数预算可更明确。

**修改**：

#### 4a. 新增AI味检查

在"注意事项"末尾追加：

```
7. 禁止使用空洞的AI味表达，如"气氛紧张""暗流涌动""命运交织"等。场景和冲突必须用具体细节描述。
```

#### 4b. 优化字数预算

在输出格式的"预计字数"字段说明中增加约束：

```
预计字数：XXXX 字（必须与全局设定的每章最低字数一致，不得低于 {min_words} 字）
```

需要在 prompt 中新增 `{min_words}` 变量，从 `parse_words_per_chapter(state.get("collected_info", {}))` 获取。

---

### 5. 章节正文生成提示词（91→92分）

**问题**：人物档案字段与角色生成输出不一致。

**修改**：

#### 5a. 简化人物档案要求（核心改动）

**System Prompt** 中的人物档案说明：

```
# 现有
## 人物档案
{main_characters}
（注意：写作时严格遵守人物的口头禅、习惯动作、深层恐惧等设定。）

# 修改后
## 人物档案
{main_characters}
（注意：写作时严格遵守人物的性格描述和核心动机，确保言行与设定一致。）
```

**User Prompt** 中无需修改（不涉及人物字段说明）。

#### 5b. 优化自检清单

```
# 现有
2. 【人设检查】每个出场人物的对话习惯、口头禅、行为模式是否与其档案一致？

# 修改后
2. 【人设检查】每个出场人物的言行是否符合其性格描述和核心动机？
```

---

### 6. 审核提示词（89→90分）

**问题**：issues 字段格式示例不够明确。

**修改**：

#### 6a. 优化 issues 格式示例

```json
"issues": [
    {"type": "情节矛盾", "location": "第三段", "description": "主角突然知道了他不该知道的信息"},
    {"type": "AI味", "location": "第五段", "description": "使用了'不禁''缓缓'等禁用词"}
]
```

将当前的简写示例替换为更完整的示例，确保 LLM 输出与 JSON schema 严格一致。

---

### 7. 重写提示词（85→88分）

**问题**：缺少"原文优点保留"的具体判定标准。

**修改**：

#### 7a. 增加原文优点判定标准

在"修改原则"第1条"渐进式修改"中追加：

```
- **原文优点识别**：修改前先识别原文中的以下优点，这些内容不得删除或弱化：
  - 具体细节描写（五感、动作、环境互动）
  - 有潜台词的对话
  - 伏笔线索
  - 情感留白处（读者能自行推断的地方）
```

#### 7b. 优化自检清单

```
# 现有
3. 【风格统一】修改后的段落与未修改的原文，在语言风格、节奏、语感上是否一致？

# 修改后
3. 【风格统一】修改后的段落与未修改的原文，在语言风格、节奏、语感上是否一致？不能出现"前后不像一个人写的"的情况。
```

---

## 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/app/agents/constants.py` | 新增 | 增加 OUTLINE_FORBIDDEN_WORDS_BRIEF |
| `backend/app/agents/prompts.py` | 修改 | 7个提示词模板全部更新 |
| `backend/app/agents/nodes/character_generation.py` | 修改 | prompt.format() 增加 plot_points, emotional_curve |
| `backend/app/agents/nodes/relation_generation.py` | 修改 | prompt.format() 增加 plot_points, emotional_curve |
| `backend/app/agents/nodes/chapter_generation.py` | 修改 | 章节大纲 prompt.format() 增加 min_words |

**不需要修改的文件**：
- 数据库、API、前端页面
- 节点输出格式和解析逻辑
- outline_generation.py、review.py、rewrite.py（仅改 prompts.py 中的模板文本）

## 兼容性保证

1. 所有新增变量使用 `{variable}` 占位符，format() 时必传，但内容为"未提供"时不会影响生成
2. 输出格式完全不变：管道分隔、JSON、Markdown 各保持原样
3. DEFAULT_PROMPTS 字典的 key 不变，value 为更新后的模板字符串
4. system_prompts API 的"重置为默认"功能自动使用新的 DEFAULT_PROMPTS

## 验证方法

1. 修改后运行现有测试：`docker exec novelagent-backend-1 pytest -v`
2. 手动测试：通过前端创建项目，运行完整工作流，检查各阶段生成质量
3. 重点验证：角色生成是否引用了情节节点；关系生成是否包含冲突点描述
