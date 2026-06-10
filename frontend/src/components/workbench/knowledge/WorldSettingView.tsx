// WorldSettingView.tsx — 世界观展示与编辑

import { useState } from 'react'
import { Globe, Edit3 } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { TagEditor } from '@/components/common/TagEditor'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import type { WorldSetting as WorldSettingType } from '@/types/knowledge'
import ReactMarkdown from 'react-markdown'

interface WorldSettingViewProps {
  data: WorldSettingType | null
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
  const [editRed, setEditRed] = useState<string[]>([])
  const [editYellow, setEditYellow] = useState<string[]>([])
  const [editGreen, setEditGreen] = useState<string[]>([])
  const [editLocations, setEditLocations] = useState<string[]>([])
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

  // 过滤来自 Outline.world_setting 的旧格式数据（含 era/core_rules/power_system）
  // 正确的 WorldSetting 数据应包含 core_concept/tiered_settings/key_locations
  const isOldFormat = data && ('era' in data || 'core_rules' in data || 'power_system' in data) && !data.core_concept

  if (!data || isOldFormat) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
        <Globe className="h-8 w-8 mb-3 text-muted-foreground/30" />
        <p>世界观尚未生成，请先完成创意孵化阶段</p>
      </div>
    )
  }

  const startEdit = () => {
    setCoreConcept(data.core_concept || '')
    const ts = data.tiered_settings || {}
    setEditRed([...(ts.red || [])])
    setEditYellow([...(ts.yellow || [])])
    setEditGreen([...(ts.green || [])])
    setEditLocations((data.key_locations || []).map((l: any) => typeof l === 'string' ? l : l.name || ''))
    setEditing(true)
  }

  const cancelEdit = () => {
    setEditing(false)
    setCoreConcept('')
  }

  const saveEdit = async () => {
    setSaving(true)
    try {
      await knowledgeApi.updateWorldSetting(projectId, {
        core_concept: coreConcept,
        tiered_settings: { red: editRed, yellow: editYellow, green: editGreen },
        key_locations: editLocations,
      })
      setEditing(false)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('世界观保存失败：' + (err instanceof Error ? err.message : '未知错误'))
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

      {/* 核心概念 - 支持 Markdown */}
      <div>
        <div className="text-[10px] text-muted-foreground mb-1">核心概念</div>
        {editing ? (
          <textarea
            value={coreConcept}
            onChange={(e) => setCoreConcept(e.target.value)}
            className="w-full border rounded-md px-3 py-2 text-xs outline-none focus:border-primary resize-none"
            rows={3}
          />
        ) : data.core_concept ? (
          <div className="text-sm bg-muted/50 rounded-lg p-3 leading-relaxed">
            <div className="markdown-content text-sm leading-relaxed">
              <ReactMarkdown
                components={{
                  h1: ({children}) => <h1 className="text-base font-bold mt-3 mb-2">{children}</h1>,
                  h2: ({children}) => <h2 className="text-sm font-semibold mt-2 mb-1">{children}</h2>,
                  h3: ({children}) => <h3 className="text-xs font-medium mt-2 mb-1">{children}</h3>,
                  p: ({children}) => <p className="mb-1.5 last:mb-0">{children}</p>,
                  ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>,
                  ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>,
                  li: ({children}) => <li className="text-xs">{children}</li>,
                  strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                }}
              >{data.core_concept}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground bg-muted/30 rounded-lg p-3">
            核心概念尚未填写，点击右上角编辑按钮添加
          </div>
        )}
      </div>

      {/* 分级设定 */}
      {!editing && Object.entries(TIER_CONFIG).map(([tier, config]) => {
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
                <li key={i} className="text-xs bg-muted/30 rounded px-3 py-1.5">
                  {/* 支持 Markdown 列表项 */}
                  <ReactMarkdown
              components={{
                p: ({children}) => <>{children}</>,
                ul: ({children}) => <ul className="list-disc list-inside mb-0 space-y-0.5">{children}</ul>,
                ol: ({children}) => <ol className="list-decimal list-inside mb-0 space-y-0.5">{children}</ol>,
                li: ({children}) => <li className="text-xs">{children}</li>,
                strong: ({children}) => <strong className="font-semibold">{children}</strong>,
              }}
            >{item}</ReactMarkdown>
                </li>
              ))}
            </ul>
          </div>
        )
      })}

      {/* 关键地点 */}
      {(editing || (!editing && data.key_locations?.length > 0)) && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">关键地点</div>
          {editing ? (
            <TagEditor items={editLocations} setItems={setEditLocations} placeholder="输入地点后回车" />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {data.key_locations.map((loc: any, i: number) => (
                <span key={i} className="bg-blue-50 text-blue-700 text-[10px] px-2 py-1 rounded">
                  {typeof loc === 'string' ? loc : loc.name || JSON.stringify(loc)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 编辑模式下的分级设定编辑 */}
      {editing && Object.entries(TIER_CONFIG).map(([tier, config]) => {
        const items = tier === 'red' ? editRed : tier === 'yellow' ? editYellow : editGreen
        const setItems = tier === 'red' ? setEditRed : tier === 'yellow' ? setEditYellow : setEditGreen
        return (
          <div key={tier}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${config.color}`}>
                {config.label}
              </span>
              <span className="text-[10px] text-muted-foreground">{config.desc}</span>
            </div>
            <TagEditor items={items} setItems={setItems} placeholder={`输入${config.label}后回车`} />
          </div>
        )
      })}

      {/* 编辑模式下的保存/取消按钮 */}
      {editing && (
        <div className="flex gap-2 pt-2">
          <button onClick={saveEdit} disabled={saving} className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
          <button onClick={cancelEdit} className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50">取消</button>
        </div>
      )}
    </div>
  )
}
