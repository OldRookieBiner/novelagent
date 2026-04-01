# NovelAgent 设计文档

## 项目概述

**NovelAgent** - AI 小说创作 Agent 系统，三 Agent 协作完成小说创作流程。

### 核心目标

- 初版专注跑通流程，验证 Agent 协作可行性
- 采用"先 Agent 后框架"策略，避免过度设计
- CLI 命令行交互，最简单直接的实现方式

---

## Agent 组成

### 三 Agent 流程

```
用户 ←──→ 大纲Agent（对话收集想法 → 大纲 → 卷纲 → 单元纲）
                ↓ 确认后交付
         写作Agent（章节纲 → 章节正文）
                ↓
         审核Agent（一致性 + 质量 + AI味 + 规则检查）
                ↓ 问题则重写，通过则继续下一章
```

### 大纲 Agent（阶段1核心）

职责：
1. 与用户对话，收集小说想法和细节
2. 自动询问补充信息（人物、背景、风格等）
3. 用户确认信息充足后，生成小说大纲
4. 与用户讨论修改大纲
5. 确认后保存状态，交付写作 Agent

### 写作 Agent（阶段3）

职责：
1. 接收大纲 Agent 交付的大纲/单元纲
2. 先写章节纲，与用户确认
3. 确认后写章节正文
4. 交付审核 Agent
5. 审核通过后继续下一章；有问题则重写

### 审核 Agent（阶段3）

职责：
检查章节正文的：
- **一致性**：人物名、地名、前后情节是否一致
- **质量**：文笔、节奏、逻辑
- **AI味检测**：是否有明显 AI 生成痕迹
- **规则检查**：是否符合用户设定的风格/限制条件

发现问题直接罗列，确认后让写作 Agent 重写，直到通过。

---

## 实现阶段

| 阶段 | 目标 | 验证点 |
|------|------|--------|
| **阶段1** | 大纲Agent：对话收集想法 → 生成大纲 → 确认 | Agent 能跟人对话、能产出大纲 |
| **阶段2** | 大纲Agent：加入卷纲、单元纲的生成和确认 | 完整大纲流程跑通 |
| **阶段3** | 写作Agent + 审核Agent：单章节的"写→审→改→确认"循环 | 章节生成流程跑通 |
| **阶段4** | 写作Agent：单元之间衔接、章节纲循环 | 完整章节生成跑通 |

**阶段1范围：** 暂不做卷纲、单元纲，先跑通"对话→大纲→确认"的最小闭环。

---

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 语言 | Python 3 | AI 生态最成熟 |
| LLM 调用 | 直接 API 调用 | 无框架依赖，完全可控 |
| CLI | argparse + input() | 最简单交互 |
| 模型 | DeepSeek（初版） | 可切换，设计成多模型支持 |
| 持久化 | JSON 文件 | 人类可读，备份方便 |

---

## 项目结构

```
novelagent/
├── cli.py               # CLI 入口，对话循环
├── config.py            # 配置（API Key、模型选择等）
├── core/
│   ├── llm_client.py    # API 调用封装，支持多模型切换
│   ├── conversation.py  # 对话历史管理
│   └── state.py         # 状态持久化（JSON读写）
├── agents/
│   ├── base.py          # Agent 基类（简单抽象）
│   ├── outline_agent.py # 大纲 Agent
│   ├── writing_agent.py # 写作 Agent（阶段3）
│   └── review_agent.py  # 审核 Agent（阶段3）
├── prompts/
│   ├── outline.py       # 大纲相关 prompt
│   ├── writing.py       # 写作相关 prompt（阶段3）
│   └── review.py        # 审核相关 prompt（阶段3）
└── data/                # JSON 存储目录
    └── projects/        # 各项目状态文件
```

---

## 大纲 Agent 详细设计（阶段1）

### 对话流程

```
1. 用户启动 CLI，输入项目名称
2. Agent 加载/创建项目状态
3. Agent 进入"收集想法"模式：
   - 用户输入想法/点子
   - Agent 自动分析信息充足度
   - Agent 询问补充问题（人物设定？世界观？风格偏好？）
   - 循环直到信息充足
4. Agent 询问确认："信息已充足，是否开始生成大纲？"
5. 用户确认后，Agent 生成小说大纲
6. Agent 展示大纲，询问修改意见
7. 用户可提出修改，Agent 调整大纲
8. 循环直到用户确认大纲完成
9. 保存状态，等待下一阶段
```

### 状态结构

```json
{
  "project_name": "武侠小说A",
  "created_at": "2026-04-01T10:00:00",
  "updated_at": "2026-04-01T12:30:00",
  "stage": "outline_confirming",
  "conversation_history": [
    {"role": "user", "content": "我想写一个武侠小说..."},
    {"role": "assistant", "content": "好的，请告诉我更多细节..."}
  ],
  "collected_info": {
    "genre": "武侠",
    "theme": "复仇与救赎",
    "main_characters": ["李逍遥", "林月如"],
    "world_setting": "古代江湖",
    "style_preference": "轻松幽默",
    "target_length": "中篇，约20万字"
  },
  "outline": {
    "title": "剑心传说",
    "summary": "少年李逍遥...",
    "chapters_count": 50,
    "main_plot_points": [...]
  },
  "outline_confirmed": false
}
```

### Prompt 设计原则

1. **收集阶段 prompt**：
   - 分析用户输入，判断信息缺口
   - 生成针对性询问，而非泛泛的"请提供更多信息"
   - **信息充足度标准**：至少包含以下 5 类信息才视为充足：
     - 题材类型（武侠/科幻/都市等）
     - 核心主题或故事主线
     - 主角设定（姓名 + 基本性格/背景）
     - 世界设定（时代背景/世界观）
     - 风格偏好或目标篇幅

2. **大纲生成 prompt**：
   - 基于收集的信息生成结构化大纲
   - **大纲格式**：
     ```
     标题：[小说名称]
     概述：[200-300字故事概述]
     预计章节：[数量]
     主要情节节点：
     1. [开篇事件]
     2. [关键转折点1]
     3. [关键转折点2]
     ...
     N. [结局]
     ```

3. **修改 prompt**：
   - 根据用户反馈调整大纲
   - 保持大纲结构一致性

---

## LLM 客户端设计

### 多模型支持

```python
# config.py
MODEL_CONFIGS = {
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "api_key": "YOUR_API_KEY",
        "model": "deepseek-chat"
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "api_key": "YOUR_API_KEY",
        "model": "gpt-4"
    },
    "claude": {
        "api_base": "https://api.anthropic.com/v1",
        "api_key": "YOUR_API_KEY",
        "model": "claude-3-opus"
    }
}

CURRENT_MODEL = "deepseek"
```

### API 调用封装

```python
# core/llm_client.py
class LLMClient:
    def __init__(self, model_name: str):
        self.config = MODEL_CONFIGS[model_name]

    def chat(self, messages: list) -> str:
        """发送对话请求，返回回复内容"""
        # 统一的 OpenAI 兼容接口调用
        pass
```

**设计要点：**
- DeepSeek、OpenAI 均支持 OpenAI 兼容接口，可统一封装
- Claude 需单独处理，但初版先不实现
- 模型切换只需修改 config.py 中的 CURRENT_MODEL

---

## CLI 交互设计

### 基本命令

```bash
# 启动新项目
python cli.py new "武侠小说A"

# 继续现有项目
python cli.py continue "武侠小说A"

# 查看项目列表
python cli.py list

# 查看项目状态
python cli.py status "武侠小说A"
```

### 对话交互

```
> 我想写一个武侠小说，主角是一个年轻的剑客

[大纲Agent] 好的，这听起来很有趣。请告诉我更多细节：
- 主角的名字是什么？
- 故事发生在什么时代背景？
- 你希望故事风格是怎样的（严肃、轻松、悬疑）？

> 主角叫李逍遥，古代江湖背景，轻松幽默风格

[大纲Agent] 收到。还有几个问题：
- 主角的目标或使命是什么？
- 有反派角色吗？
- 你预期小说大概多少字？

...
```

---

## 商业化规划（参考）

初版不考虑商业化，但未来方向明确：

### SaaS 会员模式

- **初级会员**：用户自己配置 API Key，支持多家模型
- **高级会员**：平台已集成 API，无需配置，每月赠送积分

### 技术迁移

- Agent 核心代码（agents/、core/）直接复用
- CLI 入口替换为 Web API 入口
- JSON 持久化迁移为数据库

---

## 验收标准（阶段1）

阶段1 完成标志：

1. ✅ CLI 可启动，进入对话模式
2. ✅ Agent 能与用户多轮对话收集信息
3. ✅ Agent 能自动判断信息充足度并询问补充
4. ✅ Agent 能生成小说大纲（标题 + 概述 + 情节节点）
5. ✅ 用户可提出修改意见，Agent 能调整大纲
6. ✅ 状态持久化到 JSON 文件，可断点续聊
7. ✅ 支持查看项目列表和状态

---

## 文件清单（阶段1）

需要实现的文件：

| 文件 | 内容 |
|------|------|
| `cli.py` | CLI 入口、命令解析、对话循环 |
| `config.py` | API 配置、模型选择 |
| `core/llm_client.py` | API 调用封装 |
| `core/conversation.py` | 对话历史管理 |
| `core/state.py` | JSON 状态读写 |
| `agents/base.py` | Agent 基类 |
| `agents/outline_agent.py` | 大纲 Agent 逻辑 |
| `prompts/outline.py` | 大纲相关 prompt 模板 |

---

## 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 回复不稳定 | Prompt 明确格式要求，解析时容错处理 |
| 对话历史过长超出 token 限制 | 阶段1暂不处理，后续可压缩历史 |
| JSON 文件损坏 | 提示用户备份，初版接受风险 |
| 信息收集判断不准 | Prompt 中明确判断标准，初版接受一定误差 |