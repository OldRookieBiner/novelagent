// KnowledgeTab.tsx — 知识库标签页

import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Globe, Palette, Users, GitBranch, Map } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { WorldSettingView } from './WorldSettingView'
import { cn } from '@/lib/utils'

interface KnowledgeTabProps {
  projectId: number
}

type KnowledgeSection = 'world' | 'style' | 'characters' | 'foreshadowing' | 'timeline'

const SECTIONS: { key: KnowledgeSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'world', label: '世界观', icon: Globe },
  { key: 'style', label: '风格约束', icon: Palette },
  { key: 'characters', label: '角色', icon: Users },
  { key: 'foreshadowing', label: '伏笔地图', icon: Map },
  { key: 'timeline', label: '时间线', icon: GitBranch },
]

export function KnowledgeTab({ projectId }: KnowledgeTabProps) {
  const [activeSection, setActiveSection] = useState<KnowledgeSection>('world')
  const [worldSetting, setWorldSetting] = useState<any>(null)
  const [styleConstraints, setStyleConstraints] = useState<any>(null)
  const [foreshadowings, setForeshadowings] = useState<any[]>([])
  const [timeline, setTimeline] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const loadKnowledge = useCallback(async () => {
    setLoading(true)
    try {
      const [ws, sc, fs, tl] = await Promise.allSettled([
        knowledgeApi.getWorldSetting(projectId),
        knowledgeApi.getStyleConstraints(projectId),
        knowledgeApi.getForeshadowings(projectId),
        knowledgeApi.getTimeline(projectId),
      ])
      if (ws.status === 'fulfilled') setWorldSetting(ws.value)
      if (sc.status === 'fulfilled') setStyleConstraints(sc.value)
      if (fs.status === 'fulfilled') setForeshadowings(fs.value)
      if (tl.status === 'fulfilled') setTimeline(tl.value)
    } catch (err) {
      console.error('Failed to load knowledge:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    loadKnowledge()
  }, [loadKnowledge])

  const renderContent = () => {
    switch (activeSection) {
      case 'world':
        return <WorldSettingView data={worldSetting} loading={loading} onUpdate={loadKnowledge} projectId={projectId} />
      case 'style':
        return <StyleConstraintsView data={styleConstraints} loading={loading} />
      case 'characters':
        return <PlaceholderView label="角色设定" loading={loading} />
      case 'foreshadowing':
        return <ForeshadowingView data={foreshadowings} loading={loading} />
      case 'timeline':
        return <TimelineView data={timeline} loading={loading} />
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

// ========== 世界观视图 ==========
// (moved to WorldSettingView.tsx)

// ========== 风格约束视图 ==========
function StyleConstraintsView({ data, loading }: { data: any; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data) return <EmptyState label="风格约束尚未生成，请先完成创意孵化阶段" />

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">风格约束</h3>

      {data.style_anchor && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">风格锚点</div>
          <div className="text-sm bg-muted/50 rounded p-3">{data.style_anchor}</div>
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

// ========== 伏笔地图视图 ==========
function ForeshadowingView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="伏笔地图尚未生成，请先完成创意孵化阶段" />

  const statusLabel: Record<string, { text: string; color: string }> = {
    active: { text: '活跃', color: 'bg-green-50 text-green-700' },
    pending_reclaim: { text: '待回收', color: 'bg-amber-50 text-amber-700' },
    reclaimed: { text: '已回收', color: 'bg-blue-50 text-blue-700' },
  }
  const levelLabel: Record<string, { text: string; color: string }> = {
    hint: { text: '暗示', color: 'bg-gray-50 text-gray-600' },
    strengthened: { text: '强化', color: 'bg-indigo-50 text-indigo-700' },
    revealed: { text: '揭示', color: 'bg-purple-50 text-purple-700' },
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">伏笔地图</h3>
      {data.map((item) => {
        const st = statusLabel[item.status] || { text: item.status, color: 'bg-gray-50 text-gray-600' }
        const lv = levelLabel[item.level] || { text: item.level, color: 'bg-gray-50 text-gray-600' }
        return (
          <div key={item.id} className="border rounded-lg p-3 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className={cn('text-[10px] px-1.5 py-0.5 rounded', st.color)}>{st.text}</span>
              <span className={cn('text-[10px] px-1.5 py-0.5 rounded', lv.color)}>{lv.text}</span>
              {item.planted_chapter && <span className="text-[10px] text-muted-foreground">第{item.planted_chapter}章埋设</span>}
              {item.expected_resolve_chapter && <span className="text-[10px] text-muted-foreground">→ 预计第{item.expected_resolve_chapter}章回收</span>}
            </div>
            <div className="text-xs">{item.content}</div>
            {item.related_characters?.length > 0 && (
              <div className="flex gap-1">
                {item.related_characters.map((c: string, i: number) => (
                  <span key={i} className="bg-muted text-[10px] px-1.5 py-0.5 rounded">{c}</span>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ========== 时间线视图 ==========
function TimelineView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="时间线将在写作过程中自动生成" />

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">时间线</h3>
      {data.map((entry) => (
        <div key={entry.id} className="flex gap-3 border-l-2 border-primary/20 pl-3 py-1">
          <div className="text-[10px] text-muted-foreground w-14 shrink-0">第{entry.chapter_number}章</div>
          <div className="flex-1 space-y-1">
            <div className="text-xs">{entry.summary}</div>
            <div className="flex gap-2">
              {entry.emotion_tag && <span className="text-[10px] text-muted-foreground">{entry.emotion_tag}</span>}
              {entry.causal_chain && <span className="text-[10px] text-muted-foreground">因果: {entry.causal_chain}</span>}
            </div>
            <div className="flex gap-1">
              <ScoreBar label="节奏" value={entry.rhythm_score} />
              <ScoreBar label="张力" value={entry.tension_score} />
              <ScoreBar label="情绪" value={entry.emotion_score} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-0.5">
      <span className="text-[9px] text-muted-foreground">{label}</span>
      <div className="w-8 h-1 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full bg-primary rounded-full" style={{ width: `${(value / 5) * 100}%` }} />
      </div>
    </div>
  )
}

// ========== 通用占位 ==========
function PlaceholderView({ label, loading }: { label: string; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  return <EmptyState label={`${label}将在创意孵化阶段生成`} />
}

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
