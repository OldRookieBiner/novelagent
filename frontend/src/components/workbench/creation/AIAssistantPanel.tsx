// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { useState } from 'react'
import { AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { chaptersApi } from '@/lib/api'
import { toast } from 'sonner'
import type { ReviewResponse } from '@/types'

interface AIAssistantPanelProps
{
  projectId?: number
  chapterNumber?: number
  chapterContent?: string
  onReviewComplete?: (result: ReviewResponse) => void
}

export function AIAssistantPanel({ projectId, chapterNumber, chapterContent, onReviewComplete }: AIAssistantPanelProps)
{
  const [reviewing, setReviewing] = useState(false)
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null)

  const handleReview = async () =>
  {
    if (!projectId || !chapterNumber) return
    setReviewing(true)
    try
    {
      const result = await chaptersApi.review(projectId, chapterNumber)
      setReviewResult(result)
      onReviewComplete?.(result)

      if (result.passed)
      {
        toast.success('审核通过')
      }
      else
      {
        toast.warning('审核未通过，请根据建议修改')
      }
    }
    catch (err)
    {
      console.error('Failed to review:', err)
      toast.error('审核失败')
    }
    finally
    {
      setReviewing(false)
    }
  }

  return (
    <div className="w-[240px] border-l bg-white flex flex-col h-full shrink-0">
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

            {/* 反馈 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-xs font-medium">反馈意见</span>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                {reviewResult.feedback}
              </p>
            </div>

            {/* 问题列表 */}
            {reviewResult.issues.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium">发现问题 ({reviewResult.issues.length})</span>
                {reviewResult.issues.map((issue, index) => (
                  <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs flex items-start gap-1.5">
                    <AlertCircle className="h-3 w-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <span className="leading-relaxed">{issue}</span>
                  </div>
                ))}
              </div>
            )}

            {/* 重新审核 */}
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
        ) : (
          <div className="space-y-3">
            {/* 引导提示 */}
            <div className="p-4 bg-muted rounded-md text-center">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
              <div className="text-xs text-muted-foreground leading-relaxed">
                {chapterContent
                  ? '点击下方按钮对当前章节进行质量审核'
                  : '请先生成章节内容后再进行审核'}
              </div>
            </div>

            {/* 审核按钮 */}
            <Button
              onClick={handleReview}
              disabled={reviewing || !chapterContent || !chapterNumber}
              size="sm"
              className="w-full text-xs"
            >
              {reviewing ? (
                <>
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  审核中...
                </>
              ) : (
                <>
                  <ShieldCheck className="h-3 w-3 mr-1" />
                  开始审核
                </>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}