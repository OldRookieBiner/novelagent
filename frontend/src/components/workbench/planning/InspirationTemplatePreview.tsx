// 灵感 Prompt 预览组件

import { useState, useCallback } from 'react'
import { Copy, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'

interface InspirationTemplatePreviewProps
{
  template: string
  manuallyEdited: boolean
  onTemplateChange: (value: string) => void
  onResetTemplate: () => void
}

export function InspirationTemplatePreview({
  template, manuallyEdited, onTemplateChange, onResetTemplate,
}: InspirationTemplatePreviewProps)
{
  const [expanded, setExpanded] = useState(false)

  const handleCopy = useCallback(() =>
  {
    navigator.clipboard.writeText(template).then(
      () => toast.success('Prompt 已复制到剪贴板'),
      () => toast.error('复制失败')
    )
  }, [template])

  return (
    <div className="rounded-lg border border-gray-200 bg-slate-50 overflow-hidden">
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-100">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">生成预览</span>
          <span className="text-[9px] text-slate-400">
            {manuallyEdited ? '手动编辑中 · 表单修改不再自动更新' : '自动生成 · 点击可编辑'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {manuallyEdited && (
            <button onClick={onResetTemplate} className="text-[9px] px-2 py-1 border rounded hover:bg-white text-slate-500">
              <RotateCcw className="h-3 w-3 inline mr-0.5" />重置
            </button>
          )}
          <button onClick={handleCopy} className="text-[9px] px-2 py-1 border rounded hover:bg-white text-slate-500">
            <Copy className="h-3 w-3 inline mr-0.5" />复制
          </button>
          <button onClick={() => setExpanded(!expanded)} className="text-[9px] px-2 py-1 text-slate-400 hover:text-slate-600">
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>
      <div className={`px-3.5 ${expanded ? 'py-2' : 'py-1.5'}`}>
        <Textarea
          value={template}
          onChange={(e) => onTemplateChange(e.target.value)}
          placeholder="选择灵感选项后，此处将自动生成创作 Prompt..."
          className={`w-full font-mono text-xs leading-relaxed resize-none border-none shadow-none focus-visible:ring-0 bg-transparent ${expanded ? 'h-64' : 'h-16'}`}
        />
      </div>
    </div>
  )
}
