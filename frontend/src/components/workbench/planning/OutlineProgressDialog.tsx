// frontend/src/components/workbench/planning/OutlineProgressDialog.tsx

import { useState, useEffect, useRef } from 'react'
import { Sparkles, Check, Loader2, PartyPopper, AlertCircle, RefreshCw } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { workflowApi } from '@/lib/workflowApi'
import { workflowCleanupApi } from '@/lib/api'

type StepStatus = 'pending' | 'active' | 'done'

interface Step
{
  key: string
  label: string
  status: StepStatus
  nodeName: string
}

interface OutlineProgressDialogProps
{
  open: boolean
  onClose: () => void
  projectId: number
  /** 可选的模型配置 ID */
  modelConfigId?: number
  /** 可选的模型名称 */
  modelName?: string
  /** 是否为重新规划模式 */
  isReplan?: boolean
  onComplete: () => void
  onViewOutline: () => void
}

const STEPS: Step[] = [
  { key: 'outline', label: '生成大纲', status: 'pending', nodeName: 'outline_generation_node' },
  { key: 'characters', label: '生成人物', status: 'pending', nodeName: 'create_characters_from_outline_node' },
  { key: 'relations', label: '生成关系', status: 'pending', nodeName: 'generate_relations_node' },
]

export function OutlineProgressDialog({
  open,
  onClose,
  projectId,
  modelConfigId,
  modelName,
  isReplan = false,
  onComplete,
  onViewOutline,
}: OutlineProgressDialogProps)
{
  const [steps, setSteps] = useState<Step[]>(STEPS.map(s => ({ ...s })))
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const startedRef = useRef(false)

  useEffect(() =>
  {
    if (open && !startedRef.current)
    {
      startedRef.current = true
      handleGenerate()
    }
    if (!open)
    {
      startedRef.current = false
    }
  }, [open])

  const markNodeDone = (nodeName: string) =>
  {
    setSteps(prev =>
    {
      const newSteps = prev.map(s =>
        s.nodeName === nodeName && s.status === 'active' ? { ...s, status: 'done' as StepStatus } : s
      )
      const nextPending = newSteps.find(s => s.status === 'pending')
      if (nextPending)
      {
        const idx = newSteps.indexOf(nextPending)
        newSteps[idx] = { ...nextPending, status: 'active' }
      }
      return newSteps
    })
  }

  const handleGenerate = async () =>
  {
    setError(null)
    setCompleted(false)
    setSteps(STEPS.map(s => ({ ...s, status: s.key === 'outline' ? 'active' : 'pending' })))

    const controller = new AbortController()
    abortRef.current = controller

    // 重新规划模式由后端 replan 端点处理清理；非重新规划模式先清除旧 checkpoint
    if (!isReplan)
    {
      try
      {
        await workflowCleanupApi.cleanup(projectId)
      }
      catch (cleanupErr)
      {
        console.warn('Failed to cleanup checkpoints before retry:', cleanupErr)
      }
    }

    try
    {
      const workflowFn = isReplan ? workflowApi.replanWorkflow.bind(workflowApi) : workflowApi.runWorkflow.bind(workflowApi)
      await workflowFn(
        projectId,
        {
          onNodeStart: (nodeName: string) =>
          {
            setSteps(prev => prev.map(s =>
              s.nodeName === nodeName ? { ...s, status: 'active' } : s
            ))
          },
          onNodeDone: (nodeName: string) =>
          {
            markNodeDone(nodeName)
          },
          onChunk: () =>
          {
            // 大纲流式输出中的文本块，进度条不需要处理
          },
          onWaiting: () =>
          {
            // 收到 waiting 事件（规划阶段暂停等待确认），视为规划完成
            abortRef.current = null
            setSteps(prev => prev.map(s => ({ ...s, status: 'done' })))
            setCompleted(true)
            onComplete()
          },
          onDone: () =>
          {
            abortRef.current = null
            setSteps(prev => prev.map(s => ({ ...s, status: 'done' })))
            setCompleted(true)
            onComplete()
          },
          onError: (errMsg: string) =>
          {
            abortRef.current = null
            setError(errMsg)
            setSteps(prev => prev.map(s =>
              s.status === 'active' ? { ...s, status: 'pending' } : s
            ))
          },
        },
        { signal: controller.signal, llmConfigId: modelConfigId, modelName: modelName }
      )
    }
    catch (err)
    {
      abortRef.current = null
      setError('生成失败，请重试')
      setSteps(prev => prev.map(s =>
        s.status === 'active' ? { ...s, status: 'pending' } : s
      ))
    }
  }

  useEffect(() =>
  {
    return () =>
    {
      if (abortRef.current)
      {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])

  const stepIcon = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return <Check className="h-4 w-4 text-green-600" />
      case 'active':
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
      default:
        return <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
    }
  }

  const stepBarColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'bg-green-500'
      case 'active':
        return 'bg-blue-500 animate-pulse'
      default:
        return 'bg-gray-200'
    }
  }

  const stepLabelColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'text-green-600'
      case 'active':
        return 'text-blue-600'
      default:
        return 'text-muted-foreground'
    }
  }

  return (
    <Dialog open={open} onOpenChange={() =>
    {
      if (completed || error) onClose()
    }}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) =>
      {
        if (!completed && !error) e.preventDefault()
      }}>
        <DialogHeader>
          <DialogTitle className="flex items-center justify-center gap-2 text-center">
            {completed ? (
              <>
                <PartyPopper className="h-5 w-5 text-green-500" />
                规划已完成
              </>
            ) : error ? (
              <>
                <AlertCircle className="h-5 w-5 text-red-500" />
                生成失败
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 text-blue-500" />
                {isReplan ? '正在重新规划' : '正在规划你的小说'}
              </>
            )}
          </DialogTitle>
          <DialogDescription className="text-center">
            {completed
              ? '小说大纲、人物和关系已全部生成完毕'
              : error
                ? '生成过程中出现错误'
                : 'AI 正在基于你的灵感构思角色和关系...'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {steps.map((step, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-sm ${stepLabelColor(step.status)}`}>
                  {step.label}
                </span>
                <div className="flex items-center gap-1.5">
                  {step.status === 'done' && <span className="text-xs text-green-600">完成</span>}
                  {stepIcon(step.status)}
                </div>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${stepBarColor(step.status)}`}
                  style={{
                    width: step.status === 'done' ? '100%' : step.status === 'active' ? '60%' : '0%',
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        {!completed && !error && (
          <p className="text-center text-xs text-muted-foreground">
            预计需要 40-90 秒，请耐心等待
          </p>
        )}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex gap-2 pt-2">
          {completed ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                留在灵感页
              </Button>
              <Button className="flex-1" onClick={onViewOutline}>
                查看大纲
              </Button>
            </>
          ) : error ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                关闭
              </Button>
              <Button className="flex-1" onClick={handleGenerate}>
                <RefreshCw className="h-4 w-4 mr-1.5" />
                重试
              </Button>
            </>
          ) : (
            <p className="text-xs text-muted-foreground text-center w-full">
              生成中，请勿关闭...
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}