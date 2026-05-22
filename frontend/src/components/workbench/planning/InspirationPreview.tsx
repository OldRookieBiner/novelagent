// frontend/src/components/workbench/planning/InspirationPreview.tsx
// 灵感字段预览与编辑组件 — 展示从聊天中提取的创作参数

import { useState } from 'react'
import { Pencil } from 'lucide-react'
import { type InspirationData } from '@/lib/inspiration'

interface InspirationPreviewProps
{
  fields: Partial<InspirationData>
  missingFields: string[]
  onFieldEdit: (field: keyof InspirationData, value: string) => void
  onComplete: () => void
}

/** 字段 key → 中文标签映射 */
const FIELD_LABELS: Record<string, string> = {
  novelType: '题材',
  era: '时代',
  targetReader: '目标读者',
  targetWords: '目标字数',
  contextStrategy: '上下文策略',
  coreTheme: '核心主题',
  worldSetting: '世界观',
  stylePreference: '风格偏好',
  narrative: '叙事视角',
  wordsPerChapter: '每章字数',
  genre: '流派',
  maleLead: '男主人设',
  femaleLead: '女主人设',
  goldFinger: '金手指',
}

export function InspirationPreview({
  fields,
  missingFields,
  onFieldEdit,
  onComplete,
}: InspirationPreviewProps)
{
  const allRequiredFilled = missingFields.length === 0
  // 当前正在编辑的字段 key，null 表示未在编辑
  const [editingKey, setEditingKey] = useState<string | null>(null)
  // 编辑中的临时值
  const [editingValue, setEditingValue] = useState('')

  // 开始编辑某个字段
  const startEditing = (key: string, currentValue: string) =>
  {
    setEditingKey(key)
    setEditingValue(currentValue)
  }

  // 确认编辑
  const confirmEdit = () =>
  {
    if (editingKey && editingValue.trim())
    {
      onFieldEdit(editingKey as keyof InspirationData, editingValue.trim())
    }
    setEditingKey(null)
    setEditingValue('')
  }

  // 取消编辑
  const cancelEdit = () =>
  {
    setEditingKey(null)
    setEditingValue('')
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-muted-foreground">已提取的创作参数</h3>

      <div className="space-y-2">
        {Object.entries(FIELD_LABELS).map(([key, label]) =>
        {
          const value = fields[key as keyof InspirationData]
          const isMissing = missingFields.includes(key)
          const isEditing = editingKey === key

          return (
            <div
              key={key}
              className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${
                isMissing ? 'border-dashed border-muted-foreground/30 text-muted-foreground' : 'border-border'
              }`}
            >
              <span className="text-muted-foreground">{label}</span>
              <span className="flex items-center gap-1">
                {isEditing ? (
                  <input
                    autoFocus
                    value={editingValue}
                    onChange={(e) => setEditingValue(e.target.value)}
                    onKeyDown={(e) =>
                    {
                      if (e.key === 'Enter') confirmEdit()
                      if (e.key === 'Escape') cancelEdit()
                    }}
                    onBlur={confirmEdit}
                    className="w-24 rounded border px-1 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                ) : (
                  <>
                    {value ? String(value) : '待补充'}
                    <button
                      onClick={() => startEditing(key, String(value || ''))}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                  </>
                )}
              </span>
            </div>
          )
        })}
      </div>

      <button
        onClick={onComplete}
        disabled={!allRequiredFilled}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50"
      >
        {allRequiredFilled ? '开始创作' : `还需 ${missingFields.length} 项`}
      </button>
    </div>
  )
}
