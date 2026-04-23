/**
 * WorkflowStatus - 工作流状态显示组件
 * 显示当前工作流阶段、进度、正在处理的节点等信息
 */

import { Check, Circle, Loader2, AlertCircle } from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'
import type { WorkflowStage } from '@/types'

// 工作流阶段配置
const STAGE_CONFIG: Record<WorkflowStage, { label: string; step: number }> = {
  inspiration: { label: '灵感收集', step: 1 },
  outline: { label: '大纲生成', step: 2 },
  chapter_outlines: { label: '章节大纲', step: 3 },
  writing: { label: '章节写作', step: 4 },
  review: { label: '审核', step: 5 },
  complete: { label: '已完成', step: 6 },
}

// 总阶段数
const TOTAL_STEPS = 6

/**
 * 阶段标签组件
 */
function StageLabel(
  { stage, isActive, isCompleted }:
  { stage: WorkflowStage; isActive: boolean; isCompleted: boolean }
)
{
  const config = STAGE_CONFIG[stage]

  return (
    <div className={`flex items-center gap-1.5 transition-colors
      ${isActive ? 'text-blue-600 font-semibold' : isCompleted ? 'text-green-600' : 'text-muted-foreground'}`}
    >
      {isCompleted && <Check className="h-4 w-4" />}
      <span className="text-sm">{config.label}</span>
    </div>
  )
}

/**
 * 进度步骤指示器
 */
function ProgressIndicator({ currentStep }: { currentStep: number })
{
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: TOTAL_STEPS }, (_, index) =>
      {
        const stepNumber = index + 1
        const isCompleted = stepNumber < currentStep
        const isCurrent = stepNumber === currentStep

        return (
          <div
            key={index}
            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors
              ${isCompleted
                ? 'bg-green-500 text-white'
                : isCurrent
                  ? 'bg-blue-500 text-white ring-2 ring-blue-200'
                  : 'bg-gray-200 text-gray-500'}`}
          >
            {isCompleted ? (
              <Check className="h-3 w-3" />
            ) : (
              stepNumber
            )}
          </div>
        )
      })}
    </div>
  )
}

/**
 * 工作流状态显示组件
 */
export default function WorkflowStatus()
{
  const {
    stage,
    currentNode,
    currentChapter,
    writtenChapters,
    isRunning,
    waitingForConfirmation,
    confirmationType,
  } = useWorkflowStore()

  const stageConfig = STAGE_CONFIG[stage]
  const currentStep = stageConfig?.step || 1
  const writtenCount = writtenChapters.length

  return (
    <div className="bg-white border rounded-lg p-4 space-y-4">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">工作流状态</h3>
        {isRunning && (
          <div className="flex items-center gap-1.5 text-blue-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-xs">运行中</span>
          </div>
        )}
      </div>

      {/* 当前阶段 */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">当前阶段</span>
        <StageLabel
          stage={stage}
          isActive={true}
          isCompleted={stage === 'complete'}
        />
      </div>

      {/* 进度指示器 */}
      <div className="flex items-center justify-center py-2">
        <ProgressIndicator currentStep={currentStep} />
      </div>

      {/* 正在处理的节点 */}
      {isRunning && currentNode && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-xs text-gray-500">处理中</span>
          <div className="flex items-center gap-1.5 text-blue-600">
            <Circle className="h-3 w-3 fill-current animate-pulse" />
            <span className="text-xs">{currentNode}</span>
          </div>
        </div>
      )}

      {/* 写作进度 */}
      {stage === 'writing' && writtenCount > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-xs text-gray-500">已写章节</span>
          <span className="text-xs font-medium text-gray-700">
            {writtenCount} 章
            {currentChapter > 0 && ` / 正在写第 ${currentChapter} 章`}
          </span>
        </div>
      )}

      {/* 等待确认提示 */}
      {waitingForConfirmation && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md">
          <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <div className="text-xs text-amber-800">
            <span className="font-medium">等待确认：</span>
            {confirmationType === 'outline' && '大纲已生成，请确认后继续'}
            {confirmationType === 'chapter_outlines' && '章节大纲已生成，请确认后继续'}
            {confirmationType === 'review_failed' && '审核未通过，请修改后重试'}
          </div>
        </div>
      )}

      {/* 完成状态 */}
      {stage === 'complete' && (
        <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-md">
          <Check className="h-4 w-4 text-green-600" />
          <span className="text-xs text-green-800 font-medium">
            创作完成！共 {writtenCount} 章
          </span>
        </div>
      )}
    </div>
  )
}
