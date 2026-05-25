// 灵感面板编排组件 — 灵感简报（AI 搭档通过右侧全局边栏交互）

import { useState, useEffect } from 'react'
import { collectedInfoApi, outlineApi, modelConfigsApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import InspirationBrief from './InspirationBrief'
import { OutlineProgressDialog } from './OutlineProgressDialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Sparkles, MessageSquare, ChevronDown, Loader2 } from 'lucide-react'
import type { ModelConfig } from '@/types'

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
  const [saving, setSaving] = useState(false)
  const [reviewModels, setReviewModels] = useState<ModelConfig[]>([])
  const [reviewModelId, setReviewModelId] = useState<number | null>(null)
  const [reviewDropdownOpen, setReviewDropdownOpen] = useState(false)
  const {
    setActiveMenuItem,
    setActiveTab,
    selectedModelKey,
    inspirationBrief,
    setInspirationBrief,
    aiSidebarOpen,
    toggleAiSidebar,
  } = useWorkbenchStore()

  // 挂载时从后端加载已有的灵感简报
  useEffect(() =>
  {
    let cancelled = false
    outlineApi.get(projectId).then((outline) =>
    {
      if (cancelled) return
      if (outline.inspiration_template)
      {
        setInspirationBrief(outline.inspiration_template)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [projectId, setInspirationBrief])

  // 加载审核模型列表
  useEffect(() =>
  {
    modelConfigsApi.list().then((res) =>
    {
      const healthy = (res.models || []).filter((c: ModelConfig) => c.health_status === 'healthy')
      setReviewModels(healthy)
    }).catch(() => {})
  }, [])

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
    setSaving(true)
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
    finally
    {
      setSaving(false)
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

  const selectedReviewModel = reviewModels.find((m) => m.id === reviewModelId)

  return (
    <div className="flex h-full gap-0">
      {/* 灵感简报 + 确认按钮 */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-medium">灵感简报</h3>
            {/* 审核模型选择器 */}
            <div className="relative">
              <button
                onClick={() => setReviewDropdownOpen(!reviewDropdownOpen)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground px-1.5 py-0.5 rounded hover:bg-accent transition-colors"
                title="选择审核模型（不选则使用创作模型）"
              >
                <span className="max-w-[100px] truncate">
                  {selectedReviewModel ? `审核: ${selectedReviewModel.name}` : '审核模型'}
                </span>
                <ChevronDown className="h-3 w-3" />
              </button>
              {reviewDropdownOpen && reviewModels.length > 0 && (
                <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-gray-200 rounded-md shadow-lg z-50 py-1 max-h-48 overflow-auto">
                  <button
                    onClick={() => { setReviewModelId(null); setReviewDropdownOpen(false) }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 transition-colors ${
                      reviewModelId === null ? 'text-emerald-600' : 'text-gray-500'
                    }`}
                  >
                    使用创作模型
                  </button>
                  {reviewModels.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => { setReviewModelId(m.id); setReviewDropdownOpen(false) }}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-100 transition-colors ${
                        m.id === reviewModelId ? 'text-emerald-600' : 'text-gray-600'
                      }`}
                    >
                      {m.name}{m.provider_type === 'single' && m.model_name ? ` · ${m.model_name}` : ''}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 未打开 AI 侧栏时显示入口 */}
            {!aiSidebarOpen && (
              <button
                className="text-xs px-3 py-1 border border-emerald-300 text-emerald-600 rounded hover:bg-emerald-50 flex items-center gap-1"
                onClick={toggleAiSidebar}
              >
                <MessageSquare className="h-3 w-3" />
                AI 搭档
              </button>
            )}
            {hasOutline && (
              <button
                className="text-xs px-3 py-1 border border-orange-300 text-orange-600 rounded hover:bg-orange-50"
                onClick={handleReplanRequest}
              >
                重新规划
              </button>
            )}
            <button
              className="text-xs px-3 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1"
              disabled={!inspirationBrief.trim() || saving}
              onClick={handleConfirm}
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
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
        reviewLlmConfigId={reviewModelId}
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
