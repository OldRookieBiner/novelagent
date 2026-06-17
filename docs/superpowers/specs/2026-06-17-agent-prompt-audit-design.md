# Agent 工具提示词质量审计方案

## 目标

对 NovelAgent 的 30+ Agent 工具 docstring 和 AGENT_SYSTEM_PROMPT 进行系统性质量审计，输出评分报告。不修改任何提示词，不为未来建立自动化评估工具。

## 审计范围

- **工具 docstring**：全部 `@tool` 函数的 docstring（creation 18 个、perception 6 个、modification 6 个、assist 2 个）
- **AGENT_SYSTEM_PROMPT**：`prompts.py` 末尾的 system prompt 全文
- **不在范围内**：`prompts.py` 中的 LLM 调用模板（如 `CHAPTER_WRITING_PROMPT` 等 20+ 模板）

## 评估维度（7 个，每个 1-5 分 + 文字说明）

| # | 维度 | 评估什么 | 5 分标准 | 1 分标准 |
|---|------|---------|---------|---------|
| 1 | 选择信号清晰度 | Agent 能否仅凭 docstring 判断何时该调用此工具 | 明确的触发条件和使用时机 | 只有功能描述，无法判断何时用 |
| 2 | 前置条件明确性 | 调用前必须满足的条件是否说清 | 有显式 Prerequisites 段 + 运行时校验 | 无任何前置说明，调用后才发现缺数据 |
| 3 | 输出语义明确性 | 返回结果的含义是否清晰，Agent 能否根据返回值做后续决策 | 返回结构文档化，关键字段有含义说明 | 返回不透明 dict，Agent 无法解读 |
| 4 | 同类工具区分度 | 功能相近的工具之间是否有明确边界 | docstring 主动说明与相似工具的区别 | 多个工具的描述几乎可互换 |
| 5 | 结构规范性 | docstring 的结构是否完整统一 | 统一格式：功能描述 + Prerequisites + Args + 使用时机 | 随意格式，缺关键段 |
| 6 | 与 System Prompt 一致性 | 同一概念在 docstring 和 system prompt 中是否矛盾或缺失 | 核心规则在两层中表述一致 | 存在直接矛盾或关键规则在 docstring 中缺失 |
| 7 | 指令可执行性 | Agent 看到参数描述后能否直接执行，还是靠猜 | 参数有格式/范围约束 + 输出有质量标准 | 模糊指令，Agent 需自行解读 |

## 审计方法

人工逐个阅读全部 docstring 和 system prompt，按 7 个维度打分。

辅助手段：
- 手动提取 docstring 和参数签名（避免复制粘贴遗漏）
- 手动从 system prompt 中提取核心规则关键词，与各 docstring 交叉比对
- 同类工具并排对比，判断区分度

## 报告产出

`docs/superpowers/specs/2026-06-17-agent-prompt-audit-report.md`，包含：

1. **维度级趋势**：7 个维度 × 全工具的均值/分布/典型案例
2. **工具评分卡**：每个工具 7 维度分数 + 总分 + Top 问题
3. **优先修复清单**：按"影响面 × 严重度"排序的 Top 10 问题
4. **系统性发现**：跨工具的共性问题

## AGENT_SYSTEM_PROMPT 单独审计

System prompt 作为一个整体，用同一套 7 维度的适配版本审计：
- 维度 1 替换为"行为引导清晰度"
- 维度 2 替换为"阶段规则完备性"
- 维度 4 替换为"内部一致性"（自身是否矛盾）
- 维度 6 替换为"与工具 docstring 整体一致性"
- 其余维度含义不变，适配 system prompt 语境
