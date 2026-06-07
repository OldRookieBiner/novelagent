import { Button } from '@/components/ui/button'
import { ReviewModeSelect } from '@/components/settings/ReviewModeSelect'

interface ReviewConfigPanelProps
{
  reviewMode: 'off' | 'manual' | 'auto'
  maxRewriteCount: number
  onReviewModeChange: (value: 'off' | 'manual' | 'auto') => void
  onMaxRewriteCountChange: (value: number) => void
  saving: boolean
  saved: boolean
  onSave: () => Promise<void>
}

export default function ReviewConfigPanel({
  reviewMode,
  maxRewriteCount,
  onReviewModeChange,
  onMaxRewriteCountChange,
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

      <div className="mt-6 pt-4 border-t">
        <p className="text-sm text-muted-foreground mb-4">
          创作流程由 Agent 智能引导，阶段间自动暂停确认
        </p>
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
