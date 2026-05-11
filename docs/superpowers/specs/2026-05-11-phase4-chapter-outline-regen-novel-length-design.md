# Phase 4 设计文档：章节大纲重新生成 + 篇幅选择改造

## 背景

Phase 3 完成了 System Message 机制、Fulltext 上下文策略、审核 JSON 解析。Phase 4 解决两个需求：

1. **缺少章节大纲重新生成功能** — 当前只有"重新规划"（清除大纲+人物+关系+章节大纲），无法单独重新生成章节大纲
2. **篇幅选择不够直观** — 当前灵感页面用纯数字输入目标字数，用户无法感知不同篇幅对应的上下文策略差异

## 需求 1：章节大纲重新生成

### 问题

用户对章节大纲不满意时，只能使用"重新规划"，这会清除大纲、人物、关系等所有数据。用户只想重新规划章节结构，不想丢失已确认的大纲和人物设定。

### 方案

新增 `POST /api/projects/{id}/workflow/replan-chapter-outlines` 端点，专门重新生成章节大纲。

**清理范围：**
- 删除所有 ChapterOutline（级联删除 Chapter）
- 重置 WorkflowState：stage → `STAGE_CHAPTER_OUTLINES`，current_chapter → 1，waiting_for_confirmation → False
- 删除工作流检查点
- **保留**：大纲（title/summary/plot_points 等）、人物、关系数据

**后端改动：**

| 文件 | 改动 |
|------|------|
| `backend/app/api/workflow.py` | 新增 `replan_chapter_outlines` 端点 |

端点逻辑（参考现有 `replan` 端点的模式）：
1. 获取项目，验证存在
2. 删除 ChapterOutline（级联删 Chapter）
3. 重置 WorkflowState
4. 删除检查点
5. 构建 initial_state，stage 设为 `STAGE_CHAPTER_OUTLINES`
6. 调用 `stream_workflow_events` 启动工作流（从 chapter_outlines_node 开始）
7. SSE 流式返回

**前端改动：**

| 文件 | 改动 |
|------|------|
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 新增"重新生成章节大纲"按钮 + 确认对话框 |
| `frontend/src/lib/workflowApi.ts` | 新增 `replanChapterOutlines` 方法 |

"重新生成章节大纲"按钮位置：章节大纲面板顶部操作区域，与现有按钮并列。
确认对话框文案："重新生成将清除所有章节大纲和已写正文，基于当前大纲重新规划章节结构。此操作不可撤销。"

**LangGraph 合规性：**
- 复用现有工作流架构，initial_state 的 stage 设为 `STAGE_CHAPTER_OUTLINES`
- 工作流会从 chapter_outlines_node 开始执行
- 不引入新的节点或 state 字段

---

## 需求 2：篇幅选择改造

### 问题

当前灵感页面用纯数字 `<Input type="number">` 输入目标字数，用户无法直观理解不同篇幅对上下文策略的影响。

### 方案

将目标字数输入替换为三档篇幅选择：

| 选项 | 字数范围 | 默认 targetWords | 上下文策略 | 状态 |
|------|----------|-----------------|-----------|------|
| 短篇 | ≤10万字 | 50000 | 全文上下文 | 可选 |
| 中篇 | 10-30万字 | 200000 | 混合上下文 | 禁用（待开发） |
| 长篇 | >30万字 | 500000 | 摘要上下文 | 禁用（待开发） |

**前端改动：**

| 文件 | 改动 |
|------|------|
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 将 targetWords `<Input>` 替换为三档篇幅 RadioGroup |

UI 设计：
```
篇幅类型
○ 短篇（≤10万字）— 全文上下文
● 中篇（10-30万字）— 混合上下文（待开发）
○ 长篇（>30万字）— 摘要上下文（待开发）
```

- 短篇：可选中，选中后 `targetWords` 设为 50000
- 中篇/长篇：显示但置灰（disabled），带"待开发"标签
- 去掉自定义字数输入框
- 去掉 targetWords 校验逻辑（不再需要 ≥10000 的校验，因为固定值）
- 选择篇幅后自动设定每章最低字数的合理默认值

**草稿兼容：**
- 用户之前保存的 `collected_info.targetWords` 可能是任意数字
- 加载草稿时根据 targetWords 值匹配到对应篇幅选项（≤10万→短篇，10-30万→中篇，>30万→长篇）
- 中篇/长篇置灰但能高亮显示之前的选择，用户只能切换回短篇
- targetWords 匹配逻辑与后端 `get_context_strategy` 一致

**后端改动：** 无。`collected_info.targetWords` 仍然是数字，后端 `get_context_strategy(target_words)` 已有映射逻辑。

**后端 context_strategy.py 阈值对齐：**

当前 `get_context_strategy` 阈值：
- ≤100000 → Fulltext
- \>100000 → Fulltext（暂回退）

与三档映射一致，无需修改。

---

## 影响范围

| 文件 | 改动类型 | 风险 |
|------|---------|------|
| `backend/app/api/workflow.py` | 新增端点 | 低：复用 replan 模式 |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 新增按钮+对话框 | 低：纯 UI |
| `frontend/src/lib/workflowApi.ts` | 新增方法 | 低 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 改造篇幅选择 | 中：替换输入方式，需保留草稿兼容 |

---

## 不在 Phase 4 范围的内容

| 项目 | 原因 | 归属 |
|------|------|------|
| Hybrid/Summary 上下文策略实现 | 需要 DB 摘要字段和摘要生成机制 | Phase 5 |
| 大纲/审核/重写节点的 System Message | 优先级低于本需求 | Phase 5 |
| chapters 表新增 summary 字段 | 仅 Hybrid/Summary 策略需要 | Phase 5 |
| 单个章节大纲重新生成 | 当前仅需全部重新生成 | 按需 |
| 中篇/长篇篇幅启用 | 依赖 Hybrid/Summary 策略实现 | Phase 5 |
