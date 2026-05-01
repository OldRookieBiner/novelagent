# 右栏优化、灵感保存与进度弹窗设计

日期: 2026-04-30

## 概述

本设计涵盖3个相关优化需求：右栏加宽与收缩展开、灵感选项保存、灵感确认后进度弹窗替代页面跳转。

## 需求1：右栏加宽 + 收缩展开

### 当前问题

各页面右栏宽度不一致且偏窄：

| 页面 | 右栏宽度 | 文件 | 行号 |
|------|----------|------|------|
| 灵感 | flex-[3] + max-w-[280px] | InspirationPanel.tsx | 824 |
| 小说大纲 | w-[240px] | OutlinePanel.tsx | 379 |
| 章节大纲 | w-56 (224px) | ChapterOutlinePanel.tsx | 424 |
| 章节正文 | w-[240px] | AIAssistantPanel.tsx | 54 |

### 设计方案

**加宽：** 所有右栏统一加宽到 **360px**

**收缩展开：** 采用侧边圆形按钮方案

- 右栏左边缘增加圆形按钮（◀ 收缩 / ▶ 展开）
- 展开状态：宽度 360px，显示完整内容
- 收缩状态：宽度 48px，仅显示收缩按钮
- 默认展开
- 每个面板独立管理收缩状态（useState），不共享
- 过渡动画：`transition-all duration-300`

### 涉及文件

1. `frontend/src/components/workbench/planning/InspirationPanel.tsx`
   - 右栏从 `flex-[3] max-w-[280px]` 改为 `w-[360px]`
   - 增加收缩按钮和收缩状态逻辑
   - 收缩时 `w-12`，展开时 `w-[360px]`

2. `frontend/src/components/workbench/creation/OutlinePanel.tsx`
   - 右栏从 `w-[240px]` 改为 `w-[360px]`
   - 增加收缩按钮和收缩状态逻辑

3. `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`
   - 右栏从 `w-56` 改为 `w-[360px]`
   - 增加收缩按钮和收缩状态逻辑

4. `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`
   - 从 `w-[240px]` 改为 `w-[360px]`
   - 增加收缩按钮和收缩状态逻辑
   - 通过 props 接收收缩状态（由 WritingPanel 管理）

5. `frontend/src/components/workbench/creation/WritingPanel.tsx`
   - 传递收缩状态给 AIAssistantPanel

### 收缩按钮样式

```
位置：右栏左边缘垂直居中
尺寸：28x28px 圆形
颜色：bg-indigo-600 text-white
图标：ChevronLeft（展开时）/ ChevronRight（收缩时）
hover：bg-indigo-700
绝对定位：left-[-14px] top-1/2 -translate-y-1/2
z-index：z-10
```

## 需求2：灵感选项保存

### 当前问题

前端 `handleConfirm` 发送完整的灵感数据（novelType, targetWords, coreTheme, targetReader, era, maleLead, femaleLead 等十几个字段），但后端 `CollectedInfoUpdate` schema 只接受 5 个字段（genre, theme, main_characters, world_setting, style_preference），其余字段被忽略丢弃。

### 设计方案

**后端：** 扩展 `CollectedInfoUpdate` schema，增加灵感表单的所有字段

```python
class CollectedInfoUpdate(BaseModel):
    """灵感收集信息更新"""
    # 原有字段
    genre: Optional[str] = None
    theme: Optional[str] = None
    main_characters: Optional[str] = None
    world_setting: Optional[str] = None
    style_preference: Optional[str] = None
    # 新增字段
    novelType: Optional[str] = None
    targetWords: Optional[int] = None
    coreTheme: Optional[str] = None
    targetReader: Optional[str] = None
    era: Optional[str] = None
    wordsPerChapter: Optional[str] = None
    customWordsPerChapter: Optional[int] = None
    maleLead: Optional[str] = None
    customMaleLead: Optional[str] = None
    femaleLead: Optional[str] = None
    customFemaleLead: Optional[str] = None
    protagonist: Optional[str] = None
    narrative: Optional[str] = None
    goldFinger: Optional[str] = None
    customGoldFinger: Optional[str] = None
    customGenre: Optional[str] = None
    customWorldSetting: Optional[str] = None
    inspiration_template: Optional[str] = None
```

**后端：** `update_collected_info` 端点更新所有新字段

```python
# 在现有字段处理后，增加新字段
new_fields = [
    'novelType', 'targetWords', 'coreTheme', 'targetReader', 'era',
    'wordsPerChapter', 'customWordsPerChapter', 'maleLead', 'customMaleLead',
    'femaleLead', 'customFemaleLead', 'protagonist', 'narrative',
    'goldFinger', 'customGoldFinger', 'customGenre', 'customWorldSetting',
    'inspiration_template'
]
for field in new_fields:
    value = getattr(request, field, None)
    if value is not None:
        current_info[field] = value
```

**前端：** 无需改动，已经在发送完整数据。

### 涉及文件

1. `backend/app/schemas/outline.py` — 扩展 CollectedInfoUpdate
2. `backend/app/api/outline.py` — update_collected_info 端点增加新字段处理

## 需求3：进度弹窗替代页面跳转

### 当前问题

点击"确认灵感，生成大纲"后：
1. 保存灵感数据
2. 跳转到小说大纲页面
3. 用户需要手动点击"AI 生成"按钮

体验不连贯，且灵感选择视觉上似乎"丢失"了。

### 设计方案

**新流程：**
1. 点击"确认灵感，生成大纲"
2. 保存灵感数据（同需求2）
3. 弹出进度弹窗（Dialog），不跳转页面
4. 自动调用 `outlineApi.createStream()` 生成大纲
5. 弹窗展示3个步骤的进度
6. 完成后提示"规划已完成"，提供操作按钮

**步骤定义：**

| 步骤 | 说明 | 进度触发 |
|------|------|----------|
| 生成大纲 | 大纲主体内容 | SSE 流式，收到 chunk 时更新进度 |
| 生成人物 | 从大纲中提取人物 | 大纲完成后瞬间标记 |
| 生成关系 | 从大纲中提取关系 | 人物完成后瞬间标记 |

**新组件：`OutlineProgressDialog`**

```
frontend/src/components/workbench/planning/OutlineProgressDialog.tsx
```

**Props：**
```typescript
interface OutlineProgressDialogProps
{
  open: boolean
  onClose: () => void
  projectId: number
  onComplete: () => void
}
```

**状态：**
```typescript
type StepStatus = 'pending' | 'active' | 'done'
interface Step
{
  label: string
  status: StepStatus
}
```

**弹窗交互：**
- 使用 shadcn/ui Dialog 组件
- 生成中不可关闭（防止中断）
- 生成完成后显示"留在灵感页"和"查看大纲"两个按钮
- 点击"查看大纲"：关闭弹窗 + 切换到大纲菜单项
- 点击"留在灵感页"：仅关闭弹窗
- 错误状态：显示错误信息 + "重试"和"关闭"按钮

**灵感页面改动：**

`InspirationPanel.tsx` 的 `handleConfirm` 函数：
- 移除 `setActiveMenuItem('outline')` 跳转
- 改为设置 `showProgressDialog: true`
- 渲染 `OutlineProgressDialog` 组件

**大纲生成 API 调用：**

在 `OutlineProgressDialog` 内部调用 `outlineApi.createStream()`：
```typescript
outlineApi.createStream(projectId, {
  onChunk: (chunk) => {
    // 步骤1：生成大纲 - 活跃状态
  },
  onDone: (outline) => {
    // 步骤1完成 → 步骤2瞬间完成 → 步骤3瞬间完成
  },
  onError: (error) => {
    // 显示错误状态
  }
})
```

### 涉及文件

1. `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` — 新建
2. `frontend/src/components/workbench/planning/InspirationPanel.tsx` — 修改 handleConfirm，增加进度弹窗

## 数据流

```
用户选择灵感选项
  ↓
点击"确认灵感，生成大纲"
  ↓
handleConfirm:
  1. 验证必填字段
  2. collectedInfoApi.update() 保存所有灵感数据（含新增字段）
  3. setShowProgressDialog(true)
  ↓
OutlineProgressDialog 弹出:
  1. 显示步骤1"生成大纲"为 active
  2. 调用 outlineApi.createStream()
  3. SSE 流式接收大纲内容
  4. 步骤1完成 → 步骤2"生成人物"瞬间完成 → 步骤3"生成关系"瞬间完成
  5. 显示"规划已完成"
  ↓
用户选择:
  - "查看大纲" → 关闭弹窗 + setActiveMenuItem('outline')
  - "留在灵感页" → 关闭弹窗
```

## 不涉及的改动

- LangGraph 工作流节点不变
- 大纲生成逻辑不变（仍是 outlineApi.createStream 直接调用）
- 灵感 draft localStorage 机制不变
- 后端大纲解析逻辑不变
