// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { useState, useRef, useEffect } from 'react'
import { AlertCircle, RefreshCw, ShieldCheck, ChevronLeft, ChevronRight, PenLine } from 'lucide-react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts'
import { Button } from '@/components/ui/button'
import { createSSEStream } from '@/lib/sseParser'
import { toast } from 'sonner'
import type { ReviewResponse, ReviewIssue } from '@/types'

// 审核评分维度中文标签
const SCORE_LABELS: Record<string, string> = {
  plot_consistency: '情节一致性',
  character_consistency: '人物一致性',
  writing_quality: '文笔质量',
  emotional_tension: '情感张力',
  ai_flavor: 'AI味程度',
  outline_deviation: '大纲偏离度',
}

interface AIAssistantPanelProps
{
  projectId?: number
  chapterNumber?: number
  chapterContent?: string
  initialReviewResult?: ReviewResponse | null
  onReviewComplete?: (result: ReviewResponse) => void
  onRewriteChunk?: (chunk: string) => void
  onRewriteDone?: (data: { chapter: { id?: number; content?: string; word_count?: number } }) => void
  onReviewCleared?: () => void
  onIssueClick?: (issue: ReviewIssue) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

export function AIAssistantPanel({
  projectId,
  chapterNumber,
  chapterContent,
  initialReviewResult,
  onReviewComplete,
  onRewriteChunk,
  onRewriteDone,
  onReviewCleared,
  onIssueClick,
  collapsed,
  onToggleCollapse,
}: AIAssistantPanelProps)
{
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(initialReviewResult ?? null)
  const [reviewing, setReviewing] = useState(false)
  const [rewriting, setRewriting] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  // 追踪 SSE 是否已设置审核结果，防止 useEffect 用 prop 数据覆盖 SSE 结果
  const sseResultSetRef = useRef(false)

  // 仅在以下情况从 prop 同步审核结果：
  // 1. 章节切换（key 变化导致组件重新挂载，ref 自动重置）
  // 2. 异步加载完成（initialReviewResult 从 null 变为非 null）
  // 不在 SSE 已设置结果后覆盖，避免本地状态与 prop 状态冲突
  const prevInitialRef = useRef(initialReviewResult)
  useEffect(() =>
  {
    if (!sseResultSetRef.current)
    {
      // 异步加载场景：prop 从 null 变为非 null 时同步
      if (!prevInitialRef.current && initialReviewResult)
      {
        setReviewResult(initialReviewResult)
      }
      // 章节切换时重置（key 变化已通过 useState 初始化处理，此处保险兜底）
      else if (prevInitialRef.current && !initialReviewResult)
      {
        setReviewResult(null)
      }
    }
    prevInitialRef.current = initialReviewResult
  }, [initialReviewResult])

  // 组件卸载时中止进行中的 SSE 流
  useEffect(() =>
  {
    return () =>
    {
      if (abortControllerRef.current)
      {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  const handleReview = async () =>
  {
    if (!projectId || !chapterNumber) return
    setReviewing(true)
    setReviewResult(null)
    sseResultSetRef.current = false

    const controller = new AbortController()
    abortControllerRef.current = controller

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${chapterNumber}/review`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'done')
          {
            sseResultSetRef.current = true
            const result = data as unknown as ReviewResponse
            setReviewResult(result)
            onReviewComplete?.(result)

            if (result.passed)
            {
              toast.success('审核通过')
            }
            else
            {
              toast.warning('审核未通过，可根据建议修改或重写')
            }
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            console.error('Review error:', errorMsg)
            toast.error(`审核失败: ${errorMsg}`)
          }
          // SSE 注释行（heartbeat）和 chunk 事件都被忽略
        },
        (error) =>
        {
          console.error('Failed to review:', error)
          toast.error('审核失败')
        }
      )
    }
    finally
    {
      setReviewing(false)
      abortControllerRef.current = null
    }
  }

  const handleRewrite = async () =>
  {
    if (!projectId || !chapterNumber) return
    setRewriting(true)
    setReviewResult(null)
    sseResultSetRef.current = false
    onReviewCleared?.()

    const controller = new AbortController()
    abortControllerRef.current = controller

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${chapterNumber}/rewrite`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'chunk')
          {
            const chunkData = data as { content: string } | string
            const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
            if (chunkText)
            {
              onRewriteChunk?.(chunkText)
            }
          }
          else if (type === 'done')
          {
            const doneData = data as { chapter?: { id?: number; content?: string; word_count?: number } }
            if (doneData?.chapter)
            {
              onRewriteDone?.({ chapter: doneData.chapter })
            }
            toast.success('重写完成，可重新审核验证效果')
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            console.error('Rewrite error:', errorMsg)
            toast.error(`重写失败: ${errorMsg}`)
          }
        },
        (error) =>
        {
          console.error('Failed to rewrite:', error)
          toast.error('重写失败')
        }
      )
    }
    finally
    {
      setRewriting(false)
      abortControllerRef.current = null
    }
  }

  const handleCancel = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      setReviewing(false)
      setRewriting(false)
      abortControllerRef.current = null
      toast.info('已取消操作')
    }
  }

  const isLoading = reviewing || rewriting

  return (
    <div className={`border-l bg-white flex flex-col h-full shrink-0 transition-all duration-300 ${collapsed ? 'w-12' : 'w-[360px]'} relative`}>
      {/* 收缩展开按钮 */}
      <button
        onClick={onToggleCollapse}
        className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>
      {!collapsed && (
        <>
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b flex-shrink-0">
        <ShieldCheck className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">审核</span>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-3">
        {reviewResult ? (
          <div className="space-y-3">
            {/* 审核结果 */}
            <div className={`p-3 rounded-md text-center ${
              reviewResult.passed ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}>
              <div className={`text-2xl font-bold ${reviewResult.passed ? 'text-green-600' : 'text-red-600'}`}>
                {reviewResult.passed ? '通过' : '未通过'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">审核结果</div>
            </div>

            {/* 修改建议 */}
            {reviewResult.feedback && (
              <div className="p-3 bg-muted rounded-md">
                <span className="text-xs font-medium">修改建议</span>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed whitespace-pre-wrap">
                  {reviewResult.feedback}
                </p>
              </div>
            )}

            {/* 评分详情 */}
            {reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <span className="text-xs font-medium text-blue-800">评分详情</span>
                <div className="mt-1.5 space-y-1">
                  {Object.entries(reviewResult.scores).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-blue-700">{SCORE_LABELS[key] || key}</span>
                      <span className={`font-medium ${
                        (key === 'ai_flavor' || key === 'outline_deviation')
                          ? (value <= 3 ? 'text-green-600' : value <= 5 ? 'text-yellow-600' : 'text-red-600')
                          : (value >= 7 ? 'text-green-600' : value >= 5 ? 'text-yellow-600' : 'text-red-600')
                      }`}>
                        {value}/10
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 质量雷达图 */}
            {reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
              <div className="p-3 bg-muted rounded-md">
                <h4 className="text-xs font-medium text-muted-foreground mb-2">质量雷达图</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <RadarChart data={[
                    { dimension: '情节', score: reviewResult.scores.plot_consistency || 0 },
                    { dimension: '人物', score: reviewResult.scores.character_consistency || 0 },
                    { dimension: '文笔', score: reviewResult.scores.writing_quality || 0 },
                    { dimension: '情感', score: reviewResult.scores.emotional_tension || 0 },
                    { dimension: '去AI味', score: 10 - (reviewResult.scores.ai_flavor || 0) },
                    { dimension: '贴合大纲', score: 10 - (reviewResult.scores.outline_deviation || 0) },
                  ]}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 10]} />
                    <Radar dataKey="score" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* 问题列表 */}
            {reviewResult.issues && reviewResult.issues.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium">发现问题 ({reviewResult.issues.length})</span>
                {reviewResult.issues.map((issue, index) =>
                {
                  const isString = typeof issue === 'string'
                  const description = isString ? issue : (issue.description || issue.suggestion)
                  const type = isString ? '' : issue.type
                  const location = isString ? '' : issue.location
                  const paragraphStart = isString ? undefined : issue.paragraph_start
                  const hasParagraph = !!paragraphStart
                  return (
                    <div
                      key={index}
                      onClick={() => !isString && onIssueClick?.(issue)}
                      className={`p-2 bg-yellow-50 border border-yellow-200 rounded text-xs flex items-start gap-1.5 ${
                        hasParagraph ? 'cursor-pointer hover:bg-yellow-100 transition-colors' : ''
                      }`}
                      title={hasParagraph ? '点击定位到问题段落' : undefined}
                    >
                      <AlertCircle className="h-3 w-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span className="leading-relaxed">
                        {type ? <span className="font-medium text-yellow-800">[{type}]</span> : ''}{type ? ' ' : ''}{location ? `${location}：` : ''}{description}
                      </span>
                      {paragraphStart && (
                        <span className="text-[10px] text-muted-foreground truncate max-w-[120px] ml-auto flex-shrink-0 self-center" title={paragraphStart}>
                          「{paragraphStart}...」
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* 操作按钮 */}
            <div className="space-y-2">
              <Button
                onClick={handleRewrite}
                disabled={rewriting}
                variant={reviewResult.passed ? 'outline' : 'default'}
                size="sm"
                className="w-full text-xs"
              >
                <PenLine className="h-3 w-3 mr-1" />
                {rewriting ? '重写中...' : '重写'}
              </Button>
              <Button
                onClick={() => { setReviewResult(null) }}
                variant="outline"
                size="sm"
                className="w-full text-xs"
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                重新审核
              </Button>
            </div>
          </div>
        ) : isLoading ? (
          <div className="space-y-3">
            <div className="p-4 bg-muted rounded-md text-center">
              <RefreshCw className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2 animate-spin" />
              <div className="text-xs text-muted-foreground">
                {reviewing ? '正在审核中...' : '正在重写中...'}
              </div>
            </div>
            <Button
              onClick={handleCancel}
              variant="destructive"
              size="sm"
              className="w-full text-xs"
            >
              取消
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="p-4 bg-muted rounded-md text-center">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
              <div className="text-xs text-muted-foreground leading-relaxed">
                {chapterContent
                  ? '点击下方按钮对当前章节进行质量审核'
                  : '请先生成章节内容后再进行审核'}
              </div>
            </div>
            <Button
              onClick={handleReview}
              disabled={!chapterContent || !chapterNumber}
              size="sm"
              className="w-full text-xs"
            >
              <ShieldCheck className="h-3 w-3 mr-1" />
              开始审核
            </Button>
          </div>
        )}
      </div>
        </>
      )}
      {collapsed && (
        <div className="flex flex-col items-center pt-4 gap-3">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </div>
  )
}