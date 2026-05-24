// 灵感面板编排组件 — 灵感简报 + AI 搭档布局

import { useState, useEffect } from 'react'
import { collectedInfoApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import InspirationBrief from './InspirationBrief'
import { OutlineProgressDialog } from './OutlineProgressDialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { MessageSquare, Sparkles } from 'lucide-react'

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
  const [pendingTemplate, setPendingTemplate] = useState<string>('')
  const { setActiveMenuItem, setActiveTab, selectedModelKey, inspirationBrief, setInspirationBrief } = useWorkbenchStore()

  // 监听 AI 搭档通过自定义事件更新灵感简报
  useEffect(() =>
  {
    const handleBriefUpdate = (event: Event) =>
    {
      const customEvent = event as CustomEvent<{ brief: string }>
      if (customEvent.detail?.brief)
      {
        setInspirationBrief(customEvent.detail.brief)
        toast.success('AI 搭档已更新灵感简报')
      }
    }

    window.addEventListener('inspiration-brief-update', handleBriefUpdate)
    return () => window.removeEventListener('inspiration-brief-update', handleBriefUpdate)
  }, [setInspirationBrief])

  // 确认灵感：保存简报 → 打开进度弹窗
  const handleConfirm = async () =>
  {
    try
    {
      await collectedInfoApi.update(projectId, { inspiration_template: inspirationBrief })
      toast.success('灵感简报已确认')
      setPendingTemplate(inspirationBrief)
      setShowProgressDialog(true)
    }
    catch (err)
    {
      toast.error('保存灵感简报失败')
    }
  }

  // 重新规划请求：先确认
  const handleReplanRequest = () =>
  {
    setPendingTemplate(inspirationBrief)
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
    <div className="flex h-full gap-0">
      {/* 左列：灵感简报 + 确认按钮 */}
      <div className="flex-1 flex flex-col border-r">
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
          <h3 className="text-sm font-medium">灵感简报</h3>
          <div className="flex items-center gap-2">
            {hasOutline && (
              <button
                className="text-xs px-3 py-1 border border-orange-300 text-orange-600 rounded hover:bg-orange-50"
                onClick={handleReplanRequest}
              >
                重新规划
              </button>
            )}
            <button
              className="text-xs px-3 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
              disabled={!inspirationBrief.trim()}
              onClick={handleConfirm}
            >
              <Sparkles className="h-3 w-3 inline mr-1" />
              确认并生成大纲
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <InspirationBrief
            brief={inspirationBrief}
            onBriefChange={setInspirationBrief}
          />
        </div>
      </div>

      {/* 右列：AI 搭档占位 */}
      <div className="w-[380px] flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/30">
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">AI 搭档</h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 text-center">
          <div className="space-y-3 max-w-[280px]">
            <MessageSquare className="h-10 w-10 mx-auto text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              AI 搭档面板在其他视图中可用。请在右侧对话中描述你的创作灵感，AI 将自动更新灵感简报。
            </p>
          </div>
        </div>
      </div>

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
        reviewLlmConfigId={null}
        isReplan={hasOutline}
        collectedInfo={{ inspiration_template: pendingTemplate }}
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
