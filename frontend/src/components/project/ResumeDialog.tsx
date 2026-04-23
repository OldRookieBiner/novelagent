/**
 * ResumeDialog - 恢复创作弹窗组件
 * 当用户进入有检查点的项目时显示，用于恢复工作流
 */

import { FileText, ChevronRight } from 'lucide-react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { WorkflowStage, ConfirmationType } from '@/types'

// 工作流阶段标签映射
const STAGE_LABELS: Record<WorkflowStage, string> = {
  inspiration: '灵感收集',
  outline: '大纲生成',
  chapter_outlines: '章节大纲',
  writing: '章节写作',
  review: '审核',
  complete: '已完成',
}

// 确认类型标签映射
const CONFIRMATION_LABELS: Record<ConfirmationType, string> = {
  outline: '大纲确认',
  chapter_outlines: '章节大纲确认',
  review_failed: '审核修改',
}

interface ResumeDialogProps
{
  // 是否显示弹窗
  open: boolean
  // 关闭弹窗回调
  onOpenChange: (open: boolean) => void
  // 项目名称
  projectName: string
  // 当前阶段
  currentStage: WorkflowStage
  // 当前章节
  currentChapter: number
  // 已写章节数
  writtenChaptersCount: number
  // 是否等待确认
  waitingForConfirmation: boolean
  // 确认类型
  confirmationType: ConfirmationType | null
  // 是否有章节
  hasChapters: boolean
  // 恢复创作回调
  onResume: () => void
  // 查看章节回调
  onViewChapters?: () => void
}

/**
 * 恢复创作弹窗组件
 */
export default function ResumeDialog(
  {
    open,
    onOpenChange,
    projectName,
    currentStage,
    currentChapter,
    writtenChaptersCount,
    waitingForConfirmation,
    confirmationType,
    hasChapters,
    onResume,
    onViewChapters,
  }: ResumeDialogProps
)
{
  // 处理恢复按钮点击
  const handleResume = () =>
  {
    onResume()
    onOpenChange(false)
  }

  // 处理查看章节按钮点击
  const handleViewChapters = () =>
  {
    onViewChapters?.()
    onOpenChange(false)
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-600" />
            发现未完成的创作
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 pt-2">
              {/* 项目名称 */}
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">项目</span>
                <span className="font-medium text-gray-900">{projectName}</span>
              </div>

              {/* 当前阶段 */}
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">当前阶段</span>
                <span className="font-medium text-gray-900">
                  {STAGE_LABELS[currentStage]}
                </span>
              </div>

              {/* 当前章节（写作阶段显示） */}
              {currentStage === 'writing' && currentChapter > 0 && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">当前章节</span>
                  <span className="font-medium text-gray-900">
                    第 {currentChapter} 章
                  </span>
                </div>
              )}

              {/* 已写章节数 */}
              {writtenChaptersCount > 0 && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">已写章节</span>
                  <span className="font-medium text-gray-900">
                    {writtenChaptersCount} 章
                  </span>
                </div>
              )}

              {/* 等待确认状态 */}
              {waitingForConfirmation && confirmationType && (
                <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-md">
                  <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                  <span className="text-xs text-amber-800">
                    等待{CONFIRMATION_LABELS[confirmationType]}
                  </span>
                </div>
              )}

              {/* 提示信息 */}
              <p className="text-xs text-gray-500 pt-1">
                是否继续上次未完成的创作？
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-col sm:flex-row gap-2">
          {/* 取消按钮 */}
          <AlertDialogCancel>取消</AlertDialogCancel>

          {/* 查看章节按钮（有章节时显示） */}
          {hasChapters && (
            <AlertDialogAction
              onClick={handleViewChapters}
              className="bg-secondary text-secondary-foreground hover:bg-secondary/80"
            >
              <FileText className="h-4 w-4 mr-1" />
              查看章节
            </AlertDialogAction>
          )}

          {/* 恢复创作按钮 */}
          <AlertDialogAction onClick={handleResume}>
            恢复创作
            <ChevronRight className="h-4 w-4 ml-1" />
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
