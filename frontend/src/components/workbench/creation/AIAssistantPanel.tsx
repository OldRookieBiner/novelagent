// frontend/src/components/workbench/creation/AIAssistantPanel.tsx

import { useState } from 'react'
import { Sparkles, AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
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
  const [activeTab, setActiveTab] = useState<'assist' | 'review'>('assist')
  // 审核状态
  const [reviewing, setReviewing] = useState(false)
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null)

  // 处理审核
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
    <div className="w-[350px] border-l bg-white flex flex-col h-full">
      {/* Tab 切换 */}
      <div className="flex border-b flex-shrink-0">
        <button
          onClick={() => setActiveTab('assist')}
          className={cn(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'assist'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Sparkles className="h-4 w-4 inline mr-1" />
          写作辅助
        </button>
        <button
          onClick={() => setActiveTab('review')}
          className={cn(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'review'
              ? 'text-primary border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <AlertCircle className="h-4 w-4 inline mr-1" />
          质量检测
        </button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'assist' ? (
          <div className="space-y-4">
            {/* 情节建议 */}
            <div className="p-3 bg-muted rounded-md">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">情节建议</span>
                <Button variant="ghost" size="sm">
                  <RefreshCw className="h-3 w-3" />
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                可以在本章加入一个意外转折，让读者对后续情节产生期待...
              </p>
              <Button variant="outline" size="sm" className="mt-2">
                采纳建议
              </Button>
            </div>

            {/* 续写建议 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-sm font-medium">续写建议</span>
              <p className="text-sm text-muted-foreground mt-1">
                接下来可以描写主角的内心挣扎...
              </p>
            </div>

            {/* 角色提示 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-sm font-medium">角色提示</span>
              <p className="text-sm text-muted-foreground mt-1">
                李星河在第3章表现出勇敢的性格，保持一致性
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {reviewResult ? (
              <>
                {/* 审核结果 */}
                <div className="p-4 bg-muted rounded-md text-center">
                  <div className="text-3xl font-bold text-primary">
                    {reviewResult.passed ? '通过' : '未通过'}
                  </div>
                  <div className="text-sm text-muted-foreground">审核结果</div>
                </div>

                {/* 反馈 */}
                <div className="p-3 bg-muted rounded-md">
                  <span className="text-sm font-medium">反馈</span>
                  <p className="text-sm text-muted-foreground mt-1">
                    {reviewResult.feedback}
                  </p>
                </div>

                {/* 问题列表 */}
                {reviewResult.issues.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-sm font-medium">发现问题</span>
                    {reviewResult.issues.map((issue, index) => (
                      <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
                        <AlertCircle className="h-4 w-4 inline text-yellow-600 mr-1" />
                        <span>{issue}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* 重新审核按钮 */}
                <Button
                  onClick={() => { setReviewResult(null) }}
                  variant="outline"
                  className="w-full"
                >
                  <RefreshCw className="h-4 w-4 mr-1" />
                  重新审核
                </Button>
              </>
            ) : (
              <>
                {/* 开始审核提示 */}
                <div className="p-4 bg-muted rounded-md text-center">
                  <div className="text-sm text-muted-foreground">
                    {chapterContent ? '点击下方按钮开始审核当前章节' : '当前章节无内容，无法审核'}
                  </div>
                </div>

                {/* 审核按钮 */}
                <Button
                  onClick={handleReview}
                  disabled={reviewing || !chapterContent || !chapterNumber}
                  className="w-full"
                >
                  {reviewing ? '审核中...' : '开始审核'}
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {/* 底部输入框 - 仅在写作辅助Tab显示 */}
      {activeTab === 'assist' && (
        <div className="border-t p-3 bg-white flex-shrink-0">
          <Textarea placeholder="向 AI 提问..." rows={2} className="resize-none" />
          <Button size="sm" className="mt-2 w-full">
            发送
          </Button>
        </div>
      )}
    </div>
  )
}
