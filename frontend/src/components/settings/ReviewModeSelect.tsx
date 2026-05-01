import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'

interface ReviewModeSelectProps {
  value: 'off' | 'manual' | 'auto'
  maxRewriteCount: number
  onValueChange: (value: 'off' | 'manual' | 'auto') => void
  onMaxRewriteChange: (value: number) => void
}

const reviewModeOptions = [
  {
    value: 'off' as const,
    label: '关闭审核',
    description: '生成后直接保存，不进行审核'
  },
  {
    value: 'manual' as const,
    label: '手动审核',
    description: '生成后展示审核结果，由您决定是否重写'
  },
  {
    value: 'auto' as const,
    label: '自动审核',
    description: '自动审核，不通过则重写（最多指定次数）'
  }
]

export function ReviewModeSelect({
  value,
  maxRewriteCount,
  onValueChange,
  onMaxRewriteChange
}: ReviewModeSelectProps) {
  return (
    <div className="space-y-4">
      <div>
        <Label className="text-base font-medium">审核模式</Label>
        <p className="text-sm text-muted-foreground mt-1">
          选择章节生成后的审核方式
        </p>
      </div>

      <RadioGroup value={value} onValueChange={onValueChange}>
        {reviewModeOptions.map((option) => (
          <div
            key={option.value}
            className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-accent/50 transition-colors"
          >
            <RadioGroupItem value={option.value} id={option.value} className="mt-0.5" />
            <div className="flex-1">
              <Label
                htmlFor={option.value}
                className="font-medium cursor-pointer"
              >
                {option.label}
              </Label>
              <p className="text-sm text-muted-foreground">
                {option.description}
              </p>
            </div>
          </div>
        ))}
      </RadioGroup>

      {value === 'auto' && (
        <div className="ml-6 space-y-2">
          <Label htmlFor="max-rewrite">最大重写次数</Label>
          <Select
            value={maxRewriteCount.toString()}
            onValueChange={(v: string) => onMaxRewriteChange(parseInt(v))}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 次</SelectItem>
              <SelectItem value="2">2 次</SelectItem>
              <SelectItem value="3">3 次</SelectItem>
              <SelectItem value="5">5 次</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            超过次数后即使不通过也会保存
          </p>
        </div>
      )}
    </div>
  )
}
