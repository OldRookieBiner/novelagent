import { Slider } from '@/components/ui/slider'
import type { ModelItem } from '@/types'

/** 思考强度选项 */
const REASONING_EFFORT_OPTIONS = [
  { value: 'none', label: '关闭' },
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'xhigh', label: '最强' },
] as const

interface ModelCardProps
{
  model: ModelItem
  onTemperatureChange: (val: number) => void
  onReasoningEffortChange: (val: string) => void
  onRemove: () => void
}

export default function ModelCard({
  model,
  onTemperatureChange,
  onReasoningEffortChange,
  onRemove,
}: ModelCardProps)
{
  // 防御性读取，null/undefined 时使用默认值
  const temperature = model.temperature ?? 0.7
  const reasoningEffort = model.reasoning_effort ?? 'none'

  return (
    <div className="border border-slate-200 rounded-lg p-2.5 mb-2 bg-white">
      {/* 头部：模型名称 + 移除按钮 */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium truncate">{model.name}</span>
        <button
          type="button"
          onClick={onRemove}
          className="text-red-500 text-xs hover:text-red-700 hover:underline shrink-0 ml-2"
        >
          移除
        </button>
      </div>

      {/* 温度滑块 */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-0.5">
          <span className="text-[11px] text-slate-500">温度</span>
          <span className="text-[11px] text-blue-500 font-semibold bg-blue-50 px-1.5 rounded-sm">
            {temperature.toFixed(1)}
          </span>
        </div>
        <Slider
          value={[temperature]}
          onValueChange={(val) => onTemperatureChange(val[0])}
          min={0}
          max={2}
          step={0.1}
        />
      </div>

      {/* 思考强度选择器 */}
      <div>
        <span className="text-[11px] text-slate-500 block mb-1">思考强度</span>
        <div className="flex gap-0.5">
          {REASONING_EFFORT_OPTIONS.map((option) =>
          {
            const isSelected = reasoningEffort === option.value
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => onReasoningEffortChange(option.value)}
                className={`flex-1 text-center py-0.5 px-0.5 rounded text-[10px] border-2 transition-colors ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50 text-blue-500 font-medium'
                    : 'border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-500'
                }`}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
