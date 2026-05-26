// WorldSettingView.tsx — 世界观展示与编辑

import { useState } from 'react'
import { Globe, Edit3, Check, X } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'

interface WorldSettingViewProps {
  data: any
  loading: boolean
  projectId: number
  onUpdate: () => void
}

const TIER_CONFIG: Record<string, { label: string; color: string; desc: string }> = {
  red: { label: '核心设定', color: 'bg-red-50 border-red-200 text-red-800', desc: '不可违反' },
  yellow: { label: '弹性设定', color: 'bg-amber-50 border-amber-200 text-amber-800', desc: '可在情节中突破' },
  green: { label: '自由设定', color: 'bg-green-50 border-green-200 text-green-800', desc: '可在写作中自由拓展' },
}

export function WorldSettingView({ data, loading, projectId, onUpdate }: WorldSettingViewProps) {
  const [editing, setEditing] = useState(false)
  const [coreConcept, setCoreConcept] = useState('')
  const [saving, setSaving] = useState(false)

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-5 w-24 bg-muted rounded animate-pulse" />
        <div className="h-20 w-full bg-muted rounded animate-pulse" />
        <div className="h-20 w-full bg-muted rounded animate-pulse" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
        <Globe className="h-8 w-8 mb-3 text-muted-foreground/30" />
        <p>世界观尚未生成，请先完成创意孵化阶段</p>
      </div>
    )
  }

  const startEdit = () => {
    setCoreConcept(data.core_concept || '')
    setEditing(true)
  }

  const cancelEdit = () => {
    setEditing(false)
    setCoreConcept('')
  }

  const saveEdit = async () => {
    setSaving(true)
    try {
      await knowledgeApi.updateWorldSetting(projectId, { core_concept: coreConcept })
      setEditing(false)
      onUpdate()
    } catch (err) {
      console.error('Failed to save world setting:', err)
    } finally {
      setSaving(false)
    }
  }

  const tieredSettings = data.tiered_settings || {}

  return (
    <div className="space-y-5">
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">世界观</h3>
        {!editing && (
          <button onClick={startEdit} className="text-muted-foreground hover:text-foreground transition-colors">
            <Edit3 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* 核心概念 */}
      <div>
        <div className="text-[10px] text-muted-foreground mb-1">核心概念</div>
        {editing ? (
          <div className="flex gap-2">
            <textarea
              value={coreConcept}
              onChange={(e) => setCoreConcept(e.target.value)}
              className="flex-1 border rounded-md px-3 py-2 text-xs outline-none focus:border-primary resize-none"
              rows={3}
            />
            <div className="flex flex-col gap-1">
              <button onClick={saveEdit} disabled={saving} className="p-1.5 text-green-600 hover:bg-green-50 rounded">
                <Check className="h-3.5 w-3.5" />
              </button>
              <button onClick={cancelEdit} className="p-1.5 text-red-500 hover:bg-red-50 rounded">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="text-sm bg-muted/50 rounded-lg p-3 leading-relaxed">{data.core_concept}</div>
        )}
      </div>

      {/* 分级设定 */}
      {Object.entries(TIER_CONFIG).map(([tier, config]) => {
        const items = tieredSettings[tier] || []
        if (items.length === 0) return null

        return (
          <div key={tier}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${config.color}`}>
                {config.label}
              </span>
              <span className="text-[10px] text-muted-foreground">{config.desc}</span>
            </div>
            <ul className="space-y-1">
              {items.map((item: string, i: number) => (
                <li key={i} className="text-xs bg-muted/30 rounded px-3 py-1.5">{item}</li>
              ))}
            </ul>
          </div>
        )
      })}

      {/* 关键地点 */}
      {data.key_locations?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">关键地点</div>
          <div className="flex flex-wrap gap-1.5">
            {data.key_locations.map((loc: any, i: number) => (
              <span key={i} className="bg-blue-50 text-blue-700 text-[10px] px-2 py-1 rounded">
                {typeof loc === 'string' ? loc : loc.name || JSON.stringify(loc)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
