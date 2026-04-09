# v0.4.0 步骤导航栏设计文档

> 创建日期: 2026-04-09
> 版本: v0.4.0
> 功能: 小说生成流程 UI/UX 优化

---

## 概述

在项目详情页顶部添加步骤导航栏（Stepper），让用户清晰了解当前进度，并支持查看已完成步骤的历史结果。

---

## 目标

- **可视化进度**: 用户一目了然当前处于哪个阶段
- **快速回溯**: 点击已完成步骤可查看历史结果
- **整体把控**: 展示完整工作流，帮助用户理解创作流程

---

## 设计决策

| 项目 | 决定 |
|------|------|
| 导航栏位置 | 横向顶部 |
| 节点显示 | 数字 + 标题 + 状态图标 |
| 交互方式 | 已完成步骤可点击查看历史 |
| 查看模式 | 跳转查看 + "返回当前步骤"按钮 |
| 响应式 | 横向滚动 |

---

## 步骤定义

| 序号 | 步骤名称 | 对应 Stage | 说明 |
|------|----------|------------|------|
| 1 | 信息收集 | collecting_info | 对话式收集创作信息 |
| 2 | 大纲生成 | outline_generating, outline_confirming | 生成并确认小说大纲 |
| 3 | 章节数 | chapter_count_suggesting, chapter_count_confirming | 设置章节数量 |
| 4 | 章节纲 | chapter_outlines_generating, chapter_outlines_confirming | 生成每章大纲 |
| 5 | 写作 | chapter_writing | 正文写作 |
| 6 | 审核 | chapter_reviewing, completed | 审核与重写 |

**步骤状态判定逻辑：**

```typescript
// 判断步骤是否完成
function isStepCompleted(stepIndex: number, currentStage: string): boolean {
  const stageOrder = [
    'collecting_info',
    'outline_generating', 'outline_confirming',
    'chapter_count_suggesting', 'chapter_count_confirming',
    'chapter_outlines_generating', 'chapter_outlines_confirming',
    'chapter_writing',
    'chapter_reviewing', 'completed'
  ]
  const currentIndex = stageOrder.indexOf(currentStage)
  const stepEndStages = [
    ['outline_generating'],  // 步骤1结束（信息收集完成）
    ['chapter_count_suggesting'],  // 步骤2结束（大纲确认完成）
    ['chapter_outlines_generating'],  // 步骤3结束（章节数确认完成）
    ['chapter_writing'],  // 步骤4结束（章节纲确认完成）
    ['chapter_reviewing', 'completed'],  // 步骤5结束（写作完成）
    ['completed']  // 步骤6结束（审核完成）
  ]
  return stepEndStages[stepIndex].some(s => stageOrder.indexOf(s) <= currentIndex)
}

// 判断步骤是否为当前
function isCurrentStep(stepIndex: number, currentStage: string): boolean {
  const stepStages = [
    ['collecting_info'],
    ['outline_generating', 'outline_confirming'],
    ['chapter_count_suggesting', 'chapter_count_confirming'],
    ['chapter_outlines_generating', 'chapter_outlines_confirming'],
    ['chapter_writing'],
    ['chapter_reviewing', 'completed']
  ]
  return stepStages[stepIndex].includes(currentStage)
}
```

---

## UI 设计

### 步骤导航栏样式

```
[✓ 信息收集] ━━ [✓ 大纲生成] ━━ [✓ 章节数] ━━ [● 写作] ━━ [○ 审核]

✓ = 绿色圆形 + 勾选图标（已完成）
● = 蓝色圆形 + 数字（当前步骤）
○ = 灰色圆形 + 数字（未开始）
━━ = 绿色连接线（已完成部分）
── = 灰色连接线（未完成部分）
```

### 查看历史步骤

点击已完成的步骤后：

1. 顶部显示黄色提示条："正在查看历史步骤：步骤X - XXX"
2. 右侧显示"返回当前步骤"按钮
3. 内容区显示该步骤的历史结果
4. 导航栏中当前步骤变为半透明，选中的历史步骤高亮

### 响应式设计

- 宽屏：所有步骤完整显示
- 窄屏：导航栏可横向滚动（`overflow-x: auto`）
- 移动端：支持触摸滑动

---

## 组件设计

### 新增组件

```
frontend/src/components/project/StepNavigation.tsx
```

**Props:**
```typescript
interface StepNavigationProps {
  currentStage: string
  onViewHistory: (stepIndex: number) => void
  viewingStep: number | null  // null 表示当前步骤
}
```

**内部状态:**
- 步骤列表配置
- 计算每个步骤的状态（completed/current/pending）

### 修改组件

**ProjectDetail.tsx**

- 添加 StepNavigation 组件
- 添加 viewingStep 状态管理
- 根据 viewingStep 渲染对应内容

---

## 数据需求

### 现有数据

- `project.stage` - 当前阶段
- `outline` - 大纲数据（步骤2结果）
- `collected_info` - 收集的信息（步骤1结果）
- `chapterOutlines` - 章节大纲（步骤4结果）

### 新增需求

- 步骤1（信息收集）结果：已有 `outline.collected_info`
- 步骤2（大纲生成）结果：已有 `outline`
- 步骤3（章节数）结果：已有 `outline.chapter_count`
- 步骤4（章节纲）结果：已有 `chapterOutlines`
- 步骤5（写作）结果：已有章节内容
- 步骤6（审核）结果：已有审核记录

**结论：无需新增 API，现有数据足够。**

---

## 交互流程

### 正常流程

1. 用户进入项目详情页
2. 步骤导航栏显示当前进度
3. 内容区显示当前步骤对应的工作界面

### 查看历史

1. 用户点击已完成的步骤节点
2. 导航栏更新：当前步骤半透明，历史步骤高亮
3. 顶部显示黄色提示条 + "返回当前步骤"按钮
4. 内容区切换显示该步骤的历史结果
5. 用户点击"返回当前步骤"，恢复到当前步骤视图

---

## 实现范围

### 本次实现

- [ ] StepNavigation 组件
- [ ] ProjectDetail 页面集成
- [ ] 历史步骤查看逻辑
- [ ] 响应式横向滚动
- [ ] 基础样式和动画

### 暂不实现

- 步骤内的子进度（如"写作中 3/10 章"）
- 步骤预计时间/实际耗时
- 步骤失败/卡住的异常状态

---

## 验收标准

- [ ] 导航栏正确显示6个步骤
- [ ] 状态图标正确反映完成/当前/未开始
- [ ] 点击已完成步骤可查看历史
- [ ] "返回当前步骤"按钮正常工作
- [ ] 窄屏时可横向滚动
- [ ] 不影响现有工作流功能