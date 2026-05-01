import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ReviewModeSelect } from '@/components/settings/ReviewModeSelect'
import type { WorkflowMode } from '@/types'

interface ReviewConfigPanelProps
{
  reviewMode: 'off' | 'manual' | 'auto'
  maxRewriteCount: number
  onReviewModeChange: (value: 'off' | 'manual' | 'auto') => void
  onMaxRewriteCountChange: (value: number) => void
  workflowMode: WorkflowMode
  onWorkflowModeChange: (value: WorkflowMode) => void
  saving: boolean
  saved: boolean
  onSave: () => Promise<void>
}

export default function ReviewConfigPanel({
  reviewMode,
  maxRewriteCount,
  onReviewModeChange,
  onMaxRewriteCountChange,
  workflowMode,
  onWorkflowModeChange,
  saving,
  saved,
  onSave,
}: ReviewConfigPanelProps)
{
  return (
    <div id="review-panel" role="tabpanel" className="max-w-xl">
      <h3 className="text-lg font-semibold mb-1">审核设置</h3>
      <p className="text-muted-foreground text-sm mb-6">配置章节审核行为</p>

      <ReviewModeSelect
        value={reviewMode}
        maxRewriteCount={maxRewriteCount}
        onValueChange={onReviewModeChange}
        onMaxRewriteChange={onMaxRewriteCountChange}
      />

      {/* 工作流模式设置 */}
      <div className="mt-8 pt-6 border-t">
        <h4 className="font-medium mb-1">工作流模式</h4>
        <p className="text-muted-foreground text-sm mb-4">选择小说创作的自动化程度</p>

        <RadioGroup
          value={workflowMode}
          onValueChange={(value) => onWorkflowModeChange(value as WorkflowMode)}
          className="space-y-3"
        >
          {/* 逐步确认模式 */}
          <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="step_by_step" id="step_by_step" className="mt-0.5" />
            <div className="space-y-1">
              <Label htmlFor="step_by_step" className="cursor-pointer font-medium">
                逐步确认模式
              </Label>
              <p className="text-sm text-muted-foreground">
                每个步骤完成后暂停，等待您确认后继续
              </p>
            </div>
          </div>

          {/* 智能混合模式（推荐） */}
          <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="hybrid" id="hybrid" className="mt-0.5" />
            <div className="space-y-1">
              <Label htmlFor="hybrid" className="cursor-pointer font-medium">
                智能混合模式（推荐）
              </Label>
              <p className="text-sm text-muted-foreground">
                大纲和章节大纲需要确认，正文自动生成
              </p>
            </div>
          </div>

          {/* 全自动模式 */}
          <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="auto" id="auto" className="mt-0.5" />
            <div className="space-y-1">
              <Label htmlFor="auto" className="cursor-pointer font-medium">
                全自动模式
              </Label>
              <p className="text-sm text-muted-foreground">
                一键完成，仅在审核不通过时暂停
              </p>
            </div>
          </div>
        </RadioGroup>
      </div>

      <div className="mt-6 pt-4 border-t">
        <div className="flex items-center gap-4">
          <Button onClick={onSave} disabled={saving}>
            {saving ? '保存中...' : '保存设置'}
          </Button>
          {saved && (
            <span className="text-sm text-green-600">已保存</span>
          )}
        </div>
      </div>
    </div>
  )
}
