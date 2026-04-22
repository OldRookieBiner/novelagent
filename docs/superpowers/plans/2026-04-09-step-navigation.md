# v0.4.0 步骤导航栏实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在项目详情页顶部添加步骤导航栏，可视化显示创作流程进度，支持查看已完成步骤的历史结果。

**Architecture:** 纯前端实现，不涉及后端 API 修改。新增 StepNavigation 组件，修改 ProjectDetail 页面集成。

**Tech Stack:** React 18, TypeScript, Tailwind CSS

---

## 文件结构

**新增文件：**
```
frontend/src/components/project/StepNavigation.tsx    # 步骤导航栏组件
```

**修改文件：**
```
frontend/src/pages/ProjectDetail.tsx                  # 集成导航栏
```

---

## Task 1: 步骤配置和工具函数

**Files:**
- Create: `frontend/src/components/project/StepNavigation.tsx`

**Step 1: 创建步骤配置常量**

在 `StepNavigation.tsx` 中定义步骤配置：

```typescript
// frontend/src/components/project/StepNavigation.tsx

export interface StepConfig {
  index: number
  name: string
  stages: string[]  // 对应的后端 stage 列表
}

export const STEPS: StepConfig[] = [
  { index: 0, name: '信息收集', stages: ['collecting_info'] },
  { index: 1, name: '大纲生成', stages: ['outline_generating', 'outline_confirming'] },
  { index: 2, name: '章节数', stages: ['chapter_count_suggesting', 'chapter_count_confirming'] },
  { index: 3, name: '章节纲', stages: ['chapter_outlines_generating', 'chapter_outlines_confirming'] },
  { index: 4, name: '写作', stages: ['chapter_writing'] },
  { index: 5, name: '审核', stages: ['chapter_reviewing', 'completed'] },
]

export type StepStatus = 'completed' | 'current' | 'pending'
```

**Step 2: 创建状态计算函数**

```typescript
// 获取步骤状态
export function getStepStatus(stepIndex: number, currentStage: string): StepStatus {
  const step = STEPS[stepIndex]
  
  // 当前步骤
  if (step.stages.includes(currentStage)) {
    return 'current'
  }
  
  // 判断是否已完成
  const stageOrder = [
    'collecting_info',
    'outline_generating', 'outline_confirming',
    'chapter_count_suggesting', 'chapter_count_confirming',
    'chapter_outlines_generating', 'chapter_outlines_confirming',
    'chapter_writing',
    'chapter_reviewing', 'completed'
  ]
  
  const currentIndex = stageOrder.indexOf(currentStage)
  const lastStageOfStep = step.stages[step.stages.length - 1]
  const stepEndIndex = stageOrder.indexOf(lastStageOfStep)
  
  if (currentIndex > stepEndIndex) {
    return 'completed'
  }
  
  return 'pending'
}

// 获取当前步骤索引
export function getCurrentStepIndex(currentStage: string): number {
  for (let i = 0; i < STEPS.length; i++) {
    if (STEPS[i].stages.includes(currentStage)) {
      return i
    }
  }
  return 0
}
```

---

## Task 2: StepNavigation 组件实现

**Files:**
- Modify: `frontend/src/components/project/StepNavigation.tsx`

**Step 1: 创建组件 Props 接口**

```typescript
interface StepNavigationProps {
  currentStage: string
  viewingStep: number | null  // null = 当前步骤, 数字 = 查看历史步骤
  onViewStep: (stepIndex: number | null) => void
}
```

**Step 2: 实现步骤节点组件**

```tsx
function StepNode({ 
  step, 
  status, 
  isViewing,
  onClick 
}: { 
  step: StepConfig
  status: StepStatus
  isViewing: boolean
  onClick: () => void 
}) {
  const baseClasses = "flex items-center cursor-pointer transition-opacity"
  
  // 样式根据状态变化
  const statusClasses = {
    completed: "opacity-100",
    current: "opacity-100",
    pending: "opacity-50 pointer-events-none"
  }
  
  // 圆形样式
  const circleClasses = {
    completed: "bg-green-500 text-white",
    current: "bg-blue-500 text-white animate-pulse",
    pending: "bg-gray-300 text-gray-600"
  }
  
  // 选中状态
  const viewingRing = isViewing ? "ring-4 ring-green-200" : ""
  
  return (
    <div 
      className={`${baseClasses} ${statusClasses[status]}`}
      onClick={status !== 'pending' ? onClick : undefined}
    >
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${circleClasses[status]} ${viewingRing}`}>
        {status === 'completed' ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          step.index + 1
        )}
      </div>
      <span className={`ml-2 text-sm font-medium ${
        isViewing ? 'text-green-600 font-bold' :
        status === 'current' ? 'text-blue-600 font-bold' : 'text-gray-700'
      }`}>
        {step.name}
      </span>
    </div>
  )
}
```

**Step 3: 实现连接线组件**

```tsx
function StepConnector({ completed }: { completed: boolean }) {
  return (
    <div className={`w-10 h-0.5 mx-1 ${completed ? 'bg-green-500' : 'bg-gray-300'}`} />
  )
}
```

**Step 4: 组装完整组件**

```tsx
export default function StepNavigation({ currentStage, viewingStep, onViewStep }: StepNavigationProps) {
  const currentStepIndex = getCurrentStepIndex(currentStage)
  
  return (
    <div className="p-4 border-b bg-gray-50">
      <div className="flex items-center justify-center overflow-x-auto">
        <div className="flex items-center">
          {STEPS.map((step, index) => {
            const status = getStepStatus(index, currentStage)
            const isViewing = viewingStep === index
            const isCompleted = status === 'completed'
            const isNextCompleted = index < STEPS.length - 1 && 
              getStepStatus(index + 1, currentStage) !== 'pending'
            
            return (
              <Fragment key={step.index}>
                <StepNode
                  step={step}
                  status={status}
                  isViewing={isViewing}
                  onClick={() => onViewStep(index)}
                />
                {index < STEPS.length - 1 && (
                  <StepConnector completed={isCompleted || (status === 'current' && index < currentStepIndex)} />
                )}
              </Fragment>
            )
          })}
        </div>
      </div>
    </div>
  )
}
```

---

## Task 3: 历史查看提示条组件

**Files:**
- Modify: `frontend/src/components/project/StepNavigation.tsx`

**Step 1: 创建历史查看提示条**

```tsx
interface HistoryBannerProps {
  stepName: string
  onReturn: () => void
}

function HistoryBanner({ stepName, onReturn }: HistoryBannerProps) {
  return (
    <div className="px-4 py-2 bg-yellow-50 border-b flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span>📋</span>
        <span className="text-sm text-yellow-800">
          正在查看历史步骤：<strong>{stepName}</strong>
        </span>
      </div>
      <button 
        onClick={onReturn}
        className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
      >
        返回当前步骤
      </button>
    </div>
  )
}

export { HistoryBanner }
```

---

## Task 4: ProjectDetail 页面集成

**Files:**
- Modify: `frontend/src/pages/ProjectDetail.tsx`

**Step 1: 添加 imports 和状态**

```typescript
// 在文件顶部添加
import StepNavigation, { HistoryBanner, STEPS } from '@/components/project/StepNavigation'

// 在组件内部添加状态
const [viewingStep, setViewingStep] = useState<number | null>(null)
```

**Step 2: 添加事件处理函数**

```typescript
// 查看历史步骤
const handleViewStep = (stepIndex: number | null) => {
  setViewingStep(stepIndex)
}

// 返回当前步骤
const handleReturnToCurrent = () => {
  setViewingStep(null)
}
```

**Step 3: 渲染步骤导航栏**

在项目标题下方添加：

```tsx
return (
  <div>
    {/* Project Header */}
    <div className="mb-4">
      <h1 className="text-2xl font-bold mb-2">{project.name}</h1>
      <div className="flex gap-6 text-sm text-muted-foreground">
        <span>创建时间: {new Date(project.created_at).toLocaleDateString()}</span>
        <span>阶段: {STAGE_LABELS[project.stage] || project.stage}</span>
        <span>字数: {project.total_words.toLocaleString()}</span>
      </div>
    </div>

    {/* Step Navigation - 新增 */}
    <StepNavigation
      currentStage={project.stage}
      viewingStep={viewingStep}
      onViewStep={handleViewStep}
    />

    {/* History Banner - 当查看历史时显示 */}
    {viewingStep !== null && (
      <HistoryBanner
        stepName={STEPS[viewingStep].name}
        onReturn={handleReturnToCurrent}
      />
    )}

    {/* Main Content - 根据 viewingStep 渲染 */}
    {/* ... */}
  </div>
)
```

**Step 4: 条件渲染历史内容**

```tsx
// 根据 viewingStep 渲染不同内容
const renderContent = () => {
  // 查看历史步骤
  if (viewingStep !== null) {
    return renderHistoryContent(viewingStep)
  }
  
  // 正常流程（根据当前 stage 渲染）
  return renderCurrentContent()
}

// 渲染历史步骤内容
const renderHistoryContent = (stepIndex: number) => {
  switch (stepIndex) {
    case 0: // 信息收集
      return (
        <Card>
          <CardHeader><CardTitle>收集的创作信息</CardTitle></CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap text-sm">
              {JSON.stringify(outline?.collected_info, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )
    case 1: // 大纲生成
      return (
        <Card>
          <CardHeader><CardTitle>小说大纲</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div><strong>标题:</strong> {outline?.title || '未设置'}</div>
              <div><strong>概述:</strong> {outline?.summary || '未设置'}</div>
              <div><strong>章节数:</strong> {outline?.chapter_count || '未设置'}</div>
            </div>
          </CardContent>
        </Card>
      )
    case 2: // 章节数
      return (
        <Card>
          <CardHeader><CardTitle>章节数设置</CardTitle></CardHeader>
          <CardContent>
            <p>章节数量: {outline?.chapter_count || '未设置'}</p>
          </CardContent>
        </Card>
      )
    case 3: // 章节纲
      return (
        <Card>
          <CardHeader><CardTitle>章节大纲列表</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {chapterOutlines.map(ch => (
                <div key={ch.id} className="p-2 border rounded">
                  第{ch.chapter_number}章: {ch.title || '未命名'}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )
    case 4: // 写作
    case 5: // 审核
      return (
        <Card>
          <CardHeader><CardTitle>章节列表</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {chapterOutlines.map(ch => (
                <div key={ch.id} className="p-2 border rounded flex justify-between">
                  <span>第{ch.chapter_number}章: {ch.title || '未命名'}</span>
                  {ch.has_content && <span className="text-green-600">✓</span>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )
    default:
      return null
  }
}

// 正常流程渲染
const renderCurrentContent = () => {
  // 原有的逻辑保持不变
  if (showInfoCollection) { ... }
  if (showOutlineWorkflow) { ... }
  if (showChapterList) { ... }
}
```

---

## Task 5: 响应式优化

**Files:**
- Modify: `frontend/src/components/project/StepNavigation.tsx`

**Step 1: 添加横向滚动样式**

```tsx
// 导航栏容器添加滚动样式
<div className="p-4 border-b bg-gray-50 overflow-x-auto">
  <div className="flex items-center justify-center min-w-max mx-auto">
    {/* 步骤内容 */}
  </div>
</div>
```

**Step 2: 添加移动端触摸优化**

```css
/* 可选：添加平滑滚动 */
.step-navigation {
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
```

---

## Task 6: 测试验证

**Files:**
- 无新增文件

**Step 1: 手动测试**

1. 创建新项目，验证步骤1（信息收集）高亮显示
2. 完成信息收集，验证自动跳到步骤2
3. 点击已完成的步骤1，验证历史内容显示
4. 点击"返回当前步骤"，验证恢复到当前视图
5. 调整浏览器宽度，验证横向滚动

**Step 2: 边缘情况测试**

- 项目处于 completed 状态，所有步骤应显示为已完成
- 刷新页面后 viewingStep 状态重置（符合预期）

---

## 验收清单

- [ ] 导航栏正确显示6个步骤
- [ ] 当前步骤有蓝色背景动画
- [ ] 已完成步骤显示绿色勾选
- [ ] 未开始步骤显示灰色半透明
- [ ] 连接线颜色正确（已完成=绿色）
- [ ] 点击已完成步骤可查看历史
- [ ] 历史提示条正确显示
- [ ] "返回当前步骤"按钮正常工作
- [ ] 导航栏居中显示
- [ ] 窄屏时可横向滚动
- [ ] 不影响现有工作流功能
- [ ] 前端构建无 TypeScript 错误