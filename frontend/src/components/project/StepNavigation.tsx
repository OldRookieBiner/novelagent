import { Fragment } from 'react'

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

// Props interface
interface StepNavigationProps {
  currentStage: string
  viewingStep: number | null  // null = 当前步骤, 数字 = 查看历史步骤
  onViewStep: (stepIndex: number | null) => void
}

// StepNode component
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

  const statusClasses = {
    completed: "opacity-100",
    current: "opacity-100",
    pending: "opacity-50 pointer-events-none"
  }

  const circleClasses = {
    completed: "bg-green-500 text-white",
    current: "bg-blue-500 text-white animate-pulse",
    pending: "bg-gray-300 text-gray-600"
  }

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

// StepConnector component
function StepConnector({ completed }: { completed: boolean }) {
  return (
    <div className={`w-10 h-0.5 mx-1 ${completed ? 'bg-green-500' : 'bg-gray-300'}`} />
  )
}

// Main StepNavigation component
export default function StepNavigation({ currentStage, viewingStep, onViewStep }: StepNavigationProps) {
  return (
    <div className="p-4 border-b bg-gray-50 overflow-x-auto">
      <div className="flex items-center justify-center min-w-max mx-auto">
        <div className="flex items-center">
          {STEPS.map((step, index) => {
            const status = getStepStatus(index, currentStage)
            const isViewing = viewingStep === index
            const isCompleted = status === 'completed'

            return (
              <Fragment key={step.index}>
                <StepNode
                  step={step}
                  status={status}
                  isViewing={isViewing}
                  onClick={() => onViewStep(index)}
                />
                {index < STEPS.length - 1 && (
                  <StepConnector completed={isCompleted} />
                )}
              </Fragment>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// HistoryBanner component (Task 3)
interface HistoryBannerProps {
  stepName: string
  onReturn: () => void
}

export function HistoryBanner({ stepName, onReturn }: HistoryBannerProps) {
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
