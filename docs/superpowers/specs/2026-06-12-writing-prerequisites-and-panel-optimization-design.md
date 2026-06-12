# 写作前置校验与面板优化设计

**创建日期**: 2026-06-12  
**设计范围**: Agent 写作前置条件校验 + 写作页面 UI 优化  
**当前阶段**: 设计已完成，待实施

---

## 1. 背景与目标

### 1.1 问题陈述

1. **正文生成上下文缺失检查**：当前 Agent 在生成章节正文时，不会主动检查知识库和项目结构的内容是否齐全，导致生成质量不稳定或中途因缺失项而失败。

2. **写作页面 UI 冗余**：现有 WritingPanel 包含"AI 生成"和"保存"按钮，但：
   - "AI 生成"仅打开已可见的 Agent 侧边栏，功能冗余
   - "保存"需要手动点击，不符合现代写作体验
   - "预览"按钮对 WYSIWYG 编辑器无意义

3. **知识库完整性不可见**：用户进入写作页面时，无法直观了解当前项目的知识库就绪状态。

### 1.2 设计目标

1. **后端**：在 Agent 上下文构建层增加前置条件校验，关键项缺失时阻断生成并返回详细报告
2. **前端**：优化写作页面 UI，引入自动保存机制和底部知识库状态栏

---

## 2. 设计方案

### 2.1 后端：Agent 写作前置校验

#### 2.1.1 校验项分级

| 类别 | 项目 | 缺失行为 |
|------|------|----------|
| **关键项** | 大纲已确认 (ChapterOutline.confirmed) | 阻断 |
| | 章节大纲记录存在 | 阻断 |
| | 项目内角色数量 ≥1 | 阻断 |
| | 世界观记录存在（core_concept 非空） | 阻断 |
| **次要项** | 伏笔记录 | 警告 |
| | 风格约束记录存在 | 警告 |
| | 情节块 (PlotBlock) | 警告 |
| | 上一章结尾内容（非第1章） | 警告 |
| | 关系演变规划 (EvolutionPlan) | 警告 |
| | 时间线记录 | 警告 |

#### 2.1.2 实现位置

`backend/app/agents/agent_context.py`

新增函数 `validate_prerequisites(project_id: int, current_chapter: int | None) -> dict`，在 `_load_writing_context` 末尾调用，将结果写入 `context["prerequisites"]`。

#### 2.1.3 Model 导入确认

| Model | 文件路径 |
|-------|----------|
| ChapterOutline | `app.models.outline` |
| Character | `app.models.character` |
| WorldSetting | `app.models.world_setting` |
| Foreshadowing | `app.models.foreshadowing` |
| StyleConstraints | `app.models.style_constraints` |
| PlotBlock | `app.models.plot_structure` |
| Chapter | `app.models.chapter` |
| EvolutionPlan | `app.models.character` (via Relation.project_id) |
| TimelineEntry | `app.models.timeline` |

#### 2.1.4 context 结构

```python
context["prerequisites"] = {
    "blocked": [
        {"type": "outline_unconfirmed", "chapter": 5, "message": "第5章大纲尚未确认", "severity": "error"},
        {"type": "character_missing", "message": "项目中没有任何角色", "severity": "error"},
    ],
    "warnings": [
        {"type": "foreshadowing_empty", "message": "当前无伏笔记录", "severity": "warning"},
    ],
    "validated": True,
}
```

#### 2.1.5 Agent System Prompt 适配

修改 `backend/app/agents/prompts.py` 中的 `AGENT_SYSTEM_PROMPT`，在 `## 当前阶段信息` 后新增段落：

```
## 前置条件检测结果
{context_prerequisites_warning}

当 prerequisites.blocked 非空且用户请求生成/重写/续写章节时，你应当：
1. 向用户列出所有 blocked 缺失项（用中文）
2. 说明每项缺失对写作质量的影响
3. 引导用户通过对应工具补全后再试
4. 除非用户明确要求，否则不要尝试绕过缺失项生成内容

当仅有 warnings 时，你可以继续执行，但在正文结尾添加一条写作建议（用中文）。
```

注入逻辑在 `api/agent.py` 的 `agent_chat` 中实现。

---

### 2.2 前端：写作页面优化

#### 2.2.1 UI 变化

**移除的元素**：
- "AI 生成"按钮 → Agent 侧边栏始终可见
- "保存"按钮 → 引入自动保存
- "预览"按钮 → TipTap WYSIWYG 所见即所得

**新增的元素**：
- 底部状态栏（固定）：章节进度 + 字数 + 知识库缺失项概览
- 保存状态指示器（右上角）：自动保存状态实时反馈

#### 2.2.2 自动保存机制

| 触发条件 | 行为 | 实现方式 |
|----------|------|----------|
| 编辑器内容变化后 2 秒无操作 | 自动保存到后端 | `setTimeout` 防抖 |
| 用户切换到其他章节 | 自动保存当前章节 | `useEffect` 监听章节变化 |
| 用户离开写作页面 | 自动保存当前内容 | `navigator.sendBeacon` |

**保存状态**：
- 默认：✓ 已自动保存（灰色）
- 保存中：↻ 保存中...（蓝色）
- 保存失败：⚠ 保存失败，点击可重试（红色）

**异常处理**：
- 保存失败时显示重试按钮，用户点击后重新保存
- 网络错误时最多重试 3 次，每次间��递增（1s, 2s, 4s）

#### 2.2.3 底部状态栏布局

```
┌──────────────────────────────────────────────────────────────────┐
│ 第 2 章 / 8 章    │  字数 2,450  │  ⚠ 缺失: 风格约束 · 情节块   │
└──────────────────────────────────────────────────────────────────┘
```

右侧显示知识库各检查项的状态图标（✓ 正常 / ✗ 缺失）。

#### 2.2.4 前端 API 端点

| 端点 | 路径 | 说明 |
|------|------|------|
| 获取 KB 状态 | `GET /api/{project_id}/knowledge-status?current_chapter=N` | 返回 prerequisites 结构 |
| 更新章节内容 | `PUT /api/v1/{project_id}/chapters/{chapter_number}` | 自动保存调用（使用 `chaptersApi.update`） |

---

## 3. 数据流

```
用户请求"写第5章"
       ↓
Agent 调用 build_agent_context(phase=WRITING, current_chapter=5)
       ↓
validate_prerequisites() 执行
       ↓
┌─ 关键项缺失 → context.prerequisites.blocked 非空
│      ↓
│  Agent system prompt 注入阻���引导
│      ↓
│  Agent 返回"无法生成，缺少以下前置条件..."
│
└─ 仅次要项缺失 → context.prerequisites.warnings 非空
       ↓
  Agent 可继续执行，但在正文末尾添加警告建议
```

---

## 4. 技术细节

### 4.1 错误处理

- `validate_prerequisites` 中的数据库操作需要 try-except 包裹，防止单点查询失败导致整个校验失败
- 每个检查项独立捕获异常，不影响其他检查项

### 4.2 性能考虑

- 校验函数在非 WRITING 阶段不执行，避免无谓开销
- 校验结果缓存在 request scope 内，避免重复查询

### 4.3 前端认证

- 使用现有的 `request` 函数处理认证（自动附加 Basic Auth）
- 不直接使用 fetch，避免重复处理 token

---

## 5. 后续议题

1. 自动保存频率：2 秒是否合适？是否需要可配置？
2. 大纲面板的展开/折叠状态是否需要持久化
3. 离线编辑场景下的保存策略
4. 前端知识库状态栏的详情浮层交互设计
5. 保存冲突处理：用户在多个标签页编辑同一章节
6. 大纲确认状态的乐观更新（用户点击确���后立即更新 UI，后台同步）

---

## 6. 验收标准

### 后端
- [ ] 调用 `/api/v1/{project_id}/agent/chat` 时，`context.prerequisites` 字段正确返回
- [ ] 关键项缺失时，Agent 拒绝生成并返回缺失项列表
- [ ] 仅次要项缺失时，Agent 正常执行并在末尾添加建议
- [ ] `/knowledge-status` API 正常返回 KB 状态
- [ ] 校验函数中单项异常不影响整体结果

### 前端
- [ ] 写作页面底部显示状态栏，包含章节进度、字数、知识库状态
- [ ] 编辑器内容变化后 2 秒自动保存
- [ ] 切换章节时自动保存
- [ ] 离开页面时自动保存（使用 sendBeacon）
- [ ] 保存状态指示器实时反馈保存状态（saved/saving/error）
- [ ] 保存失败可点击重试
- [ ] 无"AI 生成"、"保存"、"预览"按钮

---

**设计完成，等待用户审核后转入实施阶段。**
