# 工作台灵感采集与写作编辑器优化设计

## 日期：2026-04-30
## 状态：已确认

---

## 一、概述

优化新工作台（ProjectWorkbench）的灵感采集面板和写作面板两个模块：

1. **灵感采集面板**：加入 Prompt 模板实时生成，左右分栏布局
2. **写作面板**：将 textarea 编辑器升级为 TipTap 富文本编辑器

---

## 二、灵感采集面板重构

### 2.1 当前问题

- InspirationPanel 只有一个"保存"按钮，缺少"生成 Prompt 模板 → 确认"的完整流程
- 右侧面完善度面板占地大，信息量少

### 2.2 目标布局

```
┌──────────────┬──────────────┐
│ 表单选择区     │ Prompt模板区  │
│ (flex-1)      │ (flex-1)     │
│              │              │
│  目标读者     │  # 小说创作灵感 │
│  基本设定     │              │
│  进阶设定     │  ## 基本信息  │
│              │  - 目标读者... │
│              │  ...         │
│              │  实时同步更新  │
│              │              │
├──────────────┴──────────────┤
│       [确认，生成大纲]        │
└─────────────────────────────┘
```

### 2.3 交互逻辑

1. **实时同步**：表单任何变化 → 自动调用 `generateInspirationTemplate()` → 右侧模板实时更新
2. **手动编辑保护**：用户手动编辑模板后，标记 `templateManuallyEdited = true`，不再自动覆盖；提供"重置模板"按钮恢复自动同步
3. **自动保存草稿**：保留现有 localStorage 草稿机制
4. **确认按钮**：保存 `collected_info` + `inspiration_template` 到后端 → toast 提示"灵感已确认" → 自动切换到创作 Tab 的"小说大纲"菜单
5. **表单验证**：确认前验证必填项（目标读者、小说类型、目标字数、每章字数、年代、核心主题、主角设定）

### 2.4 模板区功能

- Textarea 展示 Markdown 模板，`font-mono`，`resize-none`
- 模板高度 `h-[calc(100vh-250px)]`，跟随窗口自适应
- 用户编辑模板后顶部显示"手动编辑模式"提示 + "重置模板"按钮
- 点击"重置模板"调用 `generateInspirationTemplate()` 重新生成并覆盖

### 2.5 移除

- 移除右侧完善度面板（右侧改为 Prompt 模板区）
- 移除现有的"保存"按钮（改为底部的"确认，生成大纲"按钮）
- 灵感采集期间不需要"保存草稿"按钮（localStorage 自动保存已足够）

---

## 三、写作面板升级：TipTap 编辑器

### 3.1 当前问题

- `WritingPanel.tsx` 使用纯 `<textarea>` 做编辑器
- 旧版 `Writing.tsx` 中已有 TipTap 编辑器实现（`ChapterEditor` 组件），未复用

### 3.2 方案

在 WritingPanel 中引入 TipTap 编辑器，复用旧版 editor 逻辑但适配工作台布局。

### 3.3 编辑器功能

- 基础富文本编辑（粗体、斜体、标题、段落）
- 字数统计（复用现有 `getWordCount`）
- 预览/编辑模式切换
- SSE 流式 AI 生成内容以 HTML 格式写入编辑器（`setContent(accumulatedHTML)`）
- 章节导航（上一章/下一章）
- 保存功能
- 右侧 AI 助手面板保留

### 3.4 编辑器工具栏

参考旧版 ChapterEditor 的工具栏设计：

- 撤销/重做
- 段落/标题选择
- 粗体/斜体
- 预览按钮
- 字数实时显示

### 3.5 AI 生成内容处理

```typescript
// 流式接收纯文本，前端按段落包装为 HTML
const accumulated = []
onChunk: (text: string) => {
  accumulated.push(text)
  const fullText = accumulated.join('')
  const html = fullText
    .split('\n')
    .filter(paragraph => paragraph.trim())
    .map(paragraph => `<p>${paragraph}</p>`)
    .join('')
  editor.commands.setContent(html)
}
```

---

## 四、技术实施要点

### 4.1 灵感面板改动

| 文件 | 改动 |
|------|------|
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 重构为左右分栏布局 |
| `frontend/src/lib/inspiration.ts` | 无需改动（generateInspirationTemplate 已存在） |
| `frontend/src/stores/workbenchStore.ts` | 可能需添加 setActiveTab 方法以便切换 Tab |

### 4.2 写作面板改动

| 文件 | 改动 |
|------|------|
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 将 textarea 替换为 TipTap 编辑器 |
| `frontend/src/components/writing/ChapterEditor.tsx` | 参考复用（或直接引入） |

### 4.3 依赖

- 前端项目已安装 `@tiptap/react`、`@tiptap/starter-kit` 等依赖

---

## 五、验收标准

1. 灵感采集表单实时生成 Prompt 模板到右侧区域
2. 用户可编辑模板，手动编辑后不自动覆盖
3. 点击"确认，生成大纲"保存数据并跳转到大纲面板
4. 写作面板使用 TipTap 编辑器替代 textarea
5. AI 生成内容正确格式化并写入编辑器
6. 所有现有功能不丢失（章节导航、保存、字数统计、右侧 AI 助手）