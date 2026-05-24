// 灵感面板编排组件 — 组合表单 + 进度弹窗 + 重新规划确认

import { useState } from 'react'
import { collectedInfoApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import { InspirationForm } from './InspirationForm'
import { OutlineProgressDialog } from './OutlineProgressDialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'

interface InspirationPanelProps
{
  projectId: number
  hasOutline?: boolean
  onPlanningComplete?: () => void
}

export function InspirationPanel({ projectId, hasOutline = false, onPlanningComplete }: InspirationPanelProps)
{
  const [showProgressDialog, setShowProgressDialog] = useState(false)
  const [showReplanConfirm, setShowReplanConfirm] = useState(false)
  // 暂存确认/重新规划的灵感数据，供 OutlineProgressDialog 使用
  const [pendingCollectedInfo, setPendingCollectedInfo] = useState<Record<string, unknown> | null>(null)
  const [pendingTemplate, setPendingTemplate] = useState<string>('')
  // 审核模型配置 ID
  const [reviewLlmConfigId, setReviewLlmConfigId] = useState<number | null>(null)
  const { setActiveMenuItem, setActiveTab, selectedModelKey } = useWorkbenchStore()

  // 确认灵感：API 保存 → 打开进度弹窗
  const handleConfirm = async (collectedInfo: Record<string, unknown>) =>
  {
    await collectedInfoApi.update(projectId, collectedInfo)
    toast.success('灵感已确认')
    setPendingCollectedInfo(collectedInfo)
    setPendingTemplate((collectedInfo.inspiration_template as string) || '')
    setShowProgressDialog(true)
  }

  // 重新规划请求：暂存数据 → 打开确认弹窗（不直接执行）
  const handleReplanRequest = (collectedInfo: Record<string, unknown>) =>
  {
    setPendingCollectedInfo(collectedInfo)
    setPendingTemplate((collectedInfo.inspiration_template as string) || '')
    setShowReplanConfirm(true)
  }

  // 确认重新规划：关闭确认弹窗 → 打开进度弹窗
  const handleReplanConfirm = () =>
  {
    setShowReplanConfirm(false)
    setShowProgressDialog(true)
  }

  // 解析模型信息
  const modelConfigId = selectedModelKey ? parseInt(selectedModelKey.split(':')[0]) : undefined
  const modelName = selectedModelKey ? selectedModelKey.split(':').slice(1).join(':') : undefined

  return (
    <div className="flex h-full">
      <InspirationForm
        projectId={projectId}
        hasOutline={hasOutline}
        onConfirm={handleConfirm}
        onRequestReplan={handleReplanRequest}
        onReviewModelChange={setReviewLlmConfigId}
      />

      {/* 重新规划确认 */}
      <AlertDialog open={showReplanConfirm} onOpenChange={setShowReplanConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认重新规划？</AlertDialogTitle>
            <AlertDialogDescription>
              重新规划将清除当前的大纲、人物和关系数据，基于当前灵感重新生成。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleReplanConfirm}>确认重新规划</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 大纲生成进度弹窗 */}
      <OutlineProgressDialog
        open={showProgressDialog}
        onClose={() => setShowProgressDialog(false)}
        projectId={projectId}
        modelConfigId={modelConfigId}
        modelName={modelName}
        reviewLlmConfigId={reviewLlmConfigId}
        isReplan={hasOutline}
        collectedInfo={pendingCollectedInfo}
        inspirationTemplate={pendingTemplate}
        onComplete={() => onPlanningComplete?.()}
        onViewOutline={() =>
        {
          onPlanningComplete?.()
          setShowProgressDialog(false)
          setActiveTab('settings')
          setActiveMenuItem('outline')
        }}
      />
    </div>
  )
}
