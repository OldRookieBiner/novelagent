// KnowledgeTab.tsx — 知识库标签页

import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Globe, Palette, Users, Sparkles, FileText } from 'lucide-react'
import { knowledgeApi, handleApiError } from '@/lib/api'
import { characterApi, relationApi } from '@/lib/characterApi'
import type { Character, RelationWithCharacters } from '@/types/character'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { TagEditor } from '@/components/common/TagEditor'
import type { Outline, OutlineCharacter, PlotPoint } from '@/types'
import { toast } from 'sonner'
import type { StyleConstraints, WorldSetting as WorldSettingType } from '@/types/knowledge'
import { WorldSettingView } from './WorldSettingView'
import { CharactersListView } from './CharactersListView'
import { RelationsView } from './RelationsView'
import { EvolutionView } from './EvolutionView'

interface KnowledgeTabProps {
  projectId: number
}

type KnowledgeSection = 'story_seed' | 'outline' | 'world' | 'style' | 'characters'

const SECTIONS: { key: KnowledgeSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'story_seed', label: '故事种子', icon: Sparkles },
  { key: 'outline', label: '大纲', icon: FileText },
  { key: 'world', label: '世界观', icon: Globe },
  { key: 'style', label: '风格约束', icon: Palette },
  { key: 'characters', label: '角色', icon: Users },
]

export function KnowledgeTab({ projectId }: KnowledgeTabProps) {
  const [activeSection, setActiveSection] = useState<KnowledgeSection>('story_seed')
  const [storySeed, setStorySeed] = useState<string>('')
  const [outlineData, setOutlineData] = useState<Outline | null>(null)
  const [worldSetting, setWorldSetting] = useState<WorldSettingType | null>(null)
  const [styleConstraints, setStyleConstraints] = useState<StyleConstraints | null>(null)

  const [characters, setCharacters] = useState<Character[]>([])
  const [relations, setRelations] = useState<RelationWithCharacters[]>([])
  const [loading, setLoading] = useState(false)

  const loadKnowledge = useCallback(async () => {
    setLoading(true)
    try {
      const [ss, os, ws, sc, chars, rels] = await Promise.allSettled([
        knowledgeApi.getStorySeed(projectId),
        knowledgeApi.getOutlineSummary(projectId),
        knowledgeApi.getWorldSetting(projectId),
        knowledgeApi.getStyleConstraints(projectId),
        characterApi.list(projectId),
        relationApi.list(projectId),
      ])
      if (ss.status === 'fulfilled') setStorySeed(ss.value?.story_seed || '')
      if (os.status === 'fulfilled') setOutlineData((os.value?.outline as unknown as Outline) || null)
      if (ws.status === 'fulfilled') setWorldSetting(ws.value as WorldSettingType)
      if (sc.status === 'fulfilled') setStyleConstraints(sc.value as StyleConstraints)

      if (chars.status === 'fulfilled') setCharacters(chars.value?.characters || [])
      if (rels.status === 'fulfilled') setRelations(rels.value?.relations || [])
    } catch (err) {
      handleApiError(err, '加载知识库')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const knowledgeVersion = useWorkbenchStore((s) => s.knowledgeVersion)

  useEffect(() => {
    loadKnowledge()
  }, [loadKnowledge, knowledgeVersion])



  const renderContent = () => {
    switch (activeSection) {
      case 'story_seed':
        return <StorySeedView data={storySeed} loading={loading} projectId={projectId} onUpdate={loadKnowledge} />
      case 'outline':
        return <OutlineView data={outlineData} loading={loading} projectId={projectId} onUpdate={loadKnowledge} />
      case 'world':
        return <WorldSettingView data={worldSetting} loading={loading} onUpdate={loadKnowledge} projectId={projectId} />
      case 'style':
        return <StyleConstraintsView data={styleConstraints} loading={loading} projectId={projectId} onUpdate={loadKnowledge} />
      case 'characters':
        return <CharactersSection data={characters} relations={relations} loading={loading} projectId={projectId} onUpdate={loadKnowledge} />

      default:
        return null
    }
  }

  return (
    <div className="flex h-full">
      {/* 左侧导航 */}
      <div className="w-40 border-r bg-white flex-shrink-0">
        <div className="p-3 border-b">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpen className="h-4 w-4" />
            知识库
          </div>
        </div>
        <nav className="py-1">
          {SECTIONS.map((section) => {
            const Icon = section.icon
            return (
              <button
                key={section.key}
                onClick={() => setActiveSection(section.key)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors',
                  activeSection === section.key
                    ? 'bg-primary/5 text-primary font-medium border-r-2 border-primary'
                    : 'text-muted-foreground hover:bg-muted/50'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {section.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 overflow-auto p-6">
        {renderContent()}
      </div>
    </div>
  )
}

// ========== 故事种子视图 ==========
function StorySeedView({ data, loading, projectId, onUpdate }: { data: string; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)

  if (loading) return <LoadingSkeleton />
  if (!data && !editing) return <EmptyState label="故事种子尚未生成，请先完成创意孵化阶段" />

  const handleEdit = () => {
    setEditText(data)
    setEditing(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await knowledgeApi.updateStorySeed(projectId, editText)
      setEditing(false)
      onUpdate()
    } catch (err) {
      toast.error('故事种子保存失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditing(false)
    setEditText('')
  }

  if (editing) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">故事种子</h3>
        <textarea
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          className="w-full h-80 text-sm bg-muted/30 rounded-lg p-3 border focus:outline-none focus:ring-1 focus:ring-primary resize-y"
          placeholder="编辑故事种子..."
        />
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button
            onClick={handleCancel}
            className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50"
          >
            取消
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">故事种子</h3>
        <button
          onClick={handleEdit}
          className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
        >
          编辑
        </button>
      </div>
      <div className="text-sm bg-muted/50 rounded-lg p-4">
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
          >{data}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

// ========== 大纲视图 ==========
function OutlineView({ data, loading, projectId, onUpdate }: { data: Outline; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [editSummary, setEditSummary] = useState('')
  const [editPlotPoints, setEditPlotPoints] = useState<PlotPoint[]>([])
  const [saving, setSaving] = useState(false)

  if (loading) return <LoadingSkeleton />
  if (!data) return <EmptyState label="大纲尚未生成，请先完成创意孵化阶段" />

  const startEdit = () => {
    setEditSummary(data.summary || '')
    setEditPlotPoints(data.plot_points?.map((p: PlotPoint) => ({...p})) || [])
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    setSaving(true)
    try {
      const { outlineApi } = await import('@/lib/api')
      await outlineApi.update(projectId, {
        summary: editSummary,
        plot_points: editPlotPoints,
      })
      setEditing(false)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err: any) {
      if (err?.response?.status === 400) {
        toast.error('大纲已确认，无法编辑')
      } else {
        toast.error('大纲保存失败：' + (err instanceof Error ? err.message : '未知错误'))
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold">大纲</h3>
        {data.confirmed ? (
          <span className="text-[10px] bg-green-50 text-green-700 px-1.5 py-0.5 rounded">已确认</span>
        ) : !editing && (
          <button onClick={startEdit} className="text-[10px] text-muted-foreground hover:text-foreground">编辑</button>
        )}
      </div>

      {data.title && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">标题</div>
          <div className="text-sm font-medium">{data.title}</div>
        </div>
      )}

      {editing ? (
        <div className="space-y-3">
          <div>
            <div className="text-[10px] text-muted-foreground mb-1">概述</div>
            <textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              className="w-full h-40 text-sm bg-muted/30 rounded-lg p-3 border focus:outline-none focus:ring-1 focus:ring-primary resize-y"
            />
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground mb-1">情节节点</div>
            <div className="space-y-2">
              {editPlotPoints.map((point, i: number) => (
                <div key={i} className="border rounded-lg p-2 text-xs space-y-1">
                  <div className="flex gap-1">
                    <input value={point.event || ''} onChange={(e) => { const pts = [...editPlotPoints]; pts[i] = {...pts[i], event: e.target.value}; setEditPlotPoints(pts) }} placeholder="事件" className="flex-1 text-xs border rounded px-2 py-1" />
                    <input value={point.conflict || ''} onChange={(e) => { const pts = [...editPlotPoints]; pts[i] = {...pts[i], conflict: e.target.value}; setEditPlotPoints(pts) }} placeholder="冲突" className="flex-1 text-xs border rounded px-2 py-1" />
                    <input value={point.hook || ''} onChange={(e) => { const pts = [...editPlotPoints]; pts[i] = {...pts[i], hook: e.target.value}; setEditPlotPoints(pts) }} placeholder="钩子" className="flex-1 text-xs border rounded px-2 py-1" />
                    <button onClick={() => setEditPlotPoints(editPlotPoints.filter((_, idx: number) => idx !== i))} className="text-muted-foreground hover:text-red-500 px-1">×</button>
                  </div>
                </div>
              ))}
              <button onClick={() => setEditPlotPoints([...editPlotPoints, {order: editPlotPoints.length, event: '', conflict: '', hook: ''}])} className="text-[10px] text-muted-foreground hover:text-foreground">+ 添加情节节点</button>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={saveEdit} disabled={saving} className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
            <button onClick={cancelEdit} className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50">取消</button>
          </div>
        </div>
      ) : (
        <>
      {data.summary && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">概述</div>
          <div className="text-sm bg-muted/50 rounded p-3">
            <div className="markdown-content text-sm leading-relaxed">
              <ReactMarkdown
                components={{
                  h1: ({children}) => <h1 className="text-base font-bold mt-3 mb-2">{children}</h1>,
                  h2: ({children}) => <h2 className="text-sm font-semibold mt-2 mb-1">{children}</h2>,
                  p: ({children}) => <p className="mb-1.5 last:mb-0">{children}</p>,
                }}
              >{data.summary}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {data.chapter_count_suggested > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">建议章节数</div>
          <div className="text-sm">{data.chapter_count_suggested} 章</div>
        </div>
      )}

      {data.plot_points?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">情节节点</div>
          <div className="space-y-1.5">
            {data.plot_points.map((point, i: number) => (
              <div key={i} className="border rounded-lg p-3 text-xs space-y-1">
                {typeof point === 'string' ? point : (
                  <>
                    <div className="font-medium">{point.event || JSON.stringify(point)}</div>
                    {point.conflict && <div className="text-muted-foreground">冲突：{point.conflict}</div>}
                    {point.hook && <div className="text-muted-foreground">钩子：{point.hook}</div>}
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {data.emotional_curve && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">情感曲线</div>
          <div className="text-sm bg-muted/50 rounded p-3">
            <div className="markdown-content text-sm leading-relaxed">
              <ReactMarkdown>{data.emotional_curve}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {data.characters?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">角色设定（大纲中）</div>
          <div className="space-y-1">
            {data.characters.map((char: OutlineCharacter, i: number) => (
              <div key={i} className="text-xs bg-blue-50 text-blue-800 px-2 py-1 rounded">
                {typeof char === 'string' ? char : char.name || JSON.stringify(char)}
              </div>
            ))}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  )
}

// ========== 风格约束视图 ==========
function StyleConstraintsView({ data, loading, projectId, onUpdate }: { data: StyleConstraints; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [editAnchor, setEditAnchor] = useState('')
  const [editTaboo, setEditTaboo] = useState<string[]>([])
  const [editPatterns, setEditPatterns] = useState<string[]>([])
  const [editRules, setEditRules] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  if (loading) return <LoadingSkeleton />
  if (!data) return <EmptyState label="风格约束尚未生成，请先完成创意孵化阶段" />

  const startEdit = () => {
    setEditAnchor(data.style_anchor || '')
    setEditTaboo([...(data.taboo_words || [])])
    setEditPatterns([...(data.forbidden_patterns || [])])
    setEditRules([...(data.abstract_rules || [])])
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    setSaving(true)
    try {
      await knowledgeApi.updateStyleConstraints(projectId, {
        style_anchor: editAnchor,
        taboo_words: editTaboo,
        forbidden_patterns: editPatterns,
        abstract_rules: editRules,
      })
      setEditing(false)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('风格约束保存失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">风格约束</h3>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">风格锚点</div>
          <textarea
            value={editAnchor}
            onChange={(e) => setEditAnchor(e.target.value)}
            className="w-full h-32 text-sm bg-muted/30 rounded-lg p-3 border focus:outline-none focus:ring-1 focus:ring-primary resize-y"
          />
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">禁忌词</div>
          <TagEditor items={editTaboo} setItems={setEditTaboo} placeholder="输入禁忌词后回车" />
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">禁用句式</div>
          <TagEditor items={editPatterns} setItems={setEditPatterns} placeholder="输入禁用句式后回车" />
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">风格规则</div>
          <TagEditor items={editRules} setItems={setEditRules} placeholder="输入风格规则后回车" />
        </div>
        <div className="flex gap-2">
          <button onClick={saveEdit} disabled={saving} className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
          <button onClick={cancelEdit} className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50">取消</button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">风格约束</h3>
        <button onClick={startEdit} className="text-[10px] text-muted-foreground hover:text-foreground">编辑</button>
      </div>

      {data.style_anchor && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">风格锚点</div>
          <div className="text-sm bg-muted/50 rounded p-3"><div className="markdown-content text-sm leading-relaxed">
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
              >{data.style_anchor}</ReactMarkdown>
            </div></div>
        </div>
      )}

      {data.taboo_words?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">禁忌词</div>
          <div className="flex flex-wrap gap-1">
            {data.taboo_words.map((word: string, i: number) => (
              <span key={i} className="bg-red-50 text-red-700 text-[10px] px-2 py-0.5 rounded">{word}</span>
            ))}
          </div>
        </div>
      )}

      {data.forbidden_patterns?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">禁用句式</div>
          <ul className="text-xs space-y-1">
            {data.forbidden_patterns.map((pattern: string, i: number) => (
              <li key={i} className="bg-amber-50 text-amber-800 px-2 py-1 rounded">{pattern}</li>
            ))}
          </ul>
        </div>
      )}

      {data.abstract_rules?.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">风格规则</div>
          <ul className="text-xs space-y-1">
            {data.abstract_rules.map((rule: string, i: number) => (
              <li key={i} className="bg-blue-50 text-blue-800 px-2 py-1 rounded">{rule}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}


type CharacterTab = 'characters' | 'relations' | 'evolution'

function CharactersSection({ data, relations, loading, projectId, onUpdate }: { data: Character[]; relations: RelationWithCharacters[]; loading: boolean; projectId: number; onUpdate: () => void })
{
    const [activeTab, setActiveTab] = useState<CharacterTab>('characters')

    const tabs: { key: CharacterTab; label: string }[] = [
        { key: 'characters', label: '角色设定' },
        { key: 'relations', label: '关系网络' },
        { key: 'evolution', label: '关系演变' },
    ]

    return (
        <div className="space-y-4">
            {/* 标签页栏 */}
            <div className="flex border-b">
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={cn(
                            'px-4 py-2 text-xs transition-colors',
                            activeTab === tab.key
                                ? 'border-b-2 border-primary text-primary font-medium'
                                : 'text-muted-foreground hover:text-foreground'
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* 标签页内容 */}
            <div>
                {activeTab === 'characters' && (
                    <CharactersListView data={data} loading={loading} projectId={projectId} onUpdate={onUpdate} />
                )}
                {activeTab === 'relations' && (
                    <RelationsView relations={relations} characters={data} loading={loading} projectId={projectId} />
                )}
                {activeTab === 'evolution' && (
                    <EvolutionView relations={relations} projectId={projectId} />
                )}
            </div>
        </div>
    )
}

// ========== 通用占位 ==========
function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
      <BookOpen className="h-8 w-8 mb-3 text-muted-foreground/30" />
      <p>{label}</p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-5 w-24 bg-muted rounded animate-pulse" />
      <div className="h-20 w-full bg-muted rounded animate-pulse" />
      <div className="h-20 w-full bg-muted rounded animate-pulse" />
    </div>
  )
}
