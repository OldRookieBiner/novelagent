// TrackingTab.tsx — 追踪标签页

import { useState, useEffect, useCallback } from 'react'
import { BarChart3, Map, GitBranch, Activity } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { cn } from '@/lib/utils'

interface TrackingTabProps {
  projectId: number
}

type TrackingSection = 'foreshadowing' | 'timeline' | 'style' | 'rhythm'

const SECTIONS: { key: TrackingSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'foreshadowing', label: '伏笔追踪', icon: Map },
  { key: 'timeline', label: '时间线', icon: GitBranch },
  { key: 'style', label: '风格统计', icon: Activity },
  { key: 'rhythm', label: '节奏分析', icon: BarChart3 },
]

export function TrackingTab({ projectId }: TrackingTabProps) {
  const [activeSection, setActiveSection] = useState<TrackingSection>('foreshadowing')
  const [foreshadowings, setForeshadowings] = useState<any[]>([])
  const [timeline, setTimeline] = useState<any[]>([])
  const [styleSnapshots, setStyleSnapshots] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const loadTracking = useCallback(async () => {
    setLoading(true)
    try {
      const [fs, tl, ss] = await Promise.allSettled([
        knowledgeApi.getForeshadowings(projectId),
        knowledgeApi.getTimeline(projectId),
        knowledgeApi.getStyleSnapshots(projectId, 20),
      ])
      if (fs.status === 'fulfilled') setForeshadowings(fs.value)
      if (tl.status === 'fulfilled') setTimeline(tl.value)
      if (ss.status === 'fulfilled') setStyleSnapshots(ss.value)
    } catch (err) {
      console.error('Failed to load tracking data:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    loadTracking()
  }, [loadTracking])

  const renderContent = () => {
    switch (activeSection) {
      case 'foreshadowing':
        return <ForeshadowingTrackView data={foreshadowings} loading={loading} />
      case 'timeline':
        return <TimelineTrackView data={timeline} loading={loading} />
      case 'style':
        return <StyleTrackView data={styleSnapshots} loading={loading} />
      case 'rhythm':
        return <RhythmTrackView data={timeline} loading={loading} />
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
            <BarChart3 className="h-4 w-4" />
            追踪
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

// ========== 伏笔追踪视图 ==========
function ForeshadowingTrackView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="伏笔追踪将在写作过程中自动更新" />

  const active = data.filter((f) => f.status === 'active')
  const pendingReclaim = data.filter((f) => f.status === 'pending_reclaim')
  const reclaimed = data.filter((f) => f.status === 'reclaimed')

  const renderGroup = (items: any[], label: string, color: string) => {
    if (!items.length) return null
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded', color)}>{label}</span>
          <span className="text-[10px] text-muted-foreground">{items.length} 条</span>
        </div>
        {items.map((item) => (
          <div key={item.id} className="border rounded-lg p-3 space-y-1">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">第{item.planted_chapter}章埋设</span>
              {item.expected_resolve_chapter && (
                <>
                  <span className="text-muted-foreground">→</span>
                  <span className={item.expected_resolve_chapter < (item.resolved_chapter || 999)
                    ? 'text-amber-600' : 'text-muted-foreground'}>
                    预计第{item.expected_resolve_chapter}章回收
                  </span>
                </>
              )}
              {item.resolved_chapter && (
                <span className="text-green-600">第{item.resolved_chapter}章已回收</span>
              )}
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
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold">伏笔追踪</h3>
      {renderGroup(pendingReclaim, '待回收', 'bg-amber-50 text-amber-700')}
      {renderGroup(active, '活跃', 'bg-green-50 text-green-700')}
      {renderGroup(reclaimed, '已回收', 'bg-blue-50 text-blue-700')}
    </div>
  )
}

// ========== 时间线追踪视图 ==========
function TimelineTrackView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="时间线将在写作过程中自动生成" />

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">时间线</h3>
      <div className="relative">
        {data.map((entry, i) => (
          <div key={entry.id} className="flex gap-3 pb-3">
            {/* 时间线竖线 */}
            <div className="flex flex-col items-center w-8 shrink-0">
              <div className="w-2.5 h-2.5 rounded-full bg-primary border-2 border-primary/20" />
              {i < data.length - 1 && <div className="w-0.5 flex-1 bg-primary/20" />}
            </div>
            {/* 内容 */}
            <div className="flex-1 space-y-1 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-medium text-primary">第{entry.chapter_number}章</span>
                {entry.emotion_tag && (
                  <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{entry.emotion_tag}</span>
                )}
              </div>
              <div className="text-xs">{entry.summary}</div>
              {entry.causal_chain && (
                <div className="text-[10px] text-muted-foreground">因果链: {entry.causal_chain}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ========== 风格统计视图 ==========
function StyleTrackView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="风格统计将在写作过程中自动生成" />

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">风格统计</h3>

      {/* 统计表格 */}
      <div className="overflow-x-auto">
        <table className="text-[10px] w-full">
          <thead>
            <tr className="border-b">
              <th className="text-left py-1.5 px-2 text-muted-foreground">章节</th>
              <th className="text-right py-1.5 px-2 text-muted-foreground">段落数</th>
              <th className="text-right py-1.5 px-2 text-muted-foreground">平均段长</th>
              <th className="text-right py-1.5 px-2 text-muted-foreground">对话占比</th>
              <th className="text-right py-1.5 px-2 text-muted-foreground">平均句长</th>
            </tr>
          </thead>
          <tbody>
            {data.map((snapshot) => (
              <tr key={snapshot.id} className="border-b border-muted/50">
                <td className="py-1.5 px-2">{snapshot.chapter_number}</td>
                <td className="text-right py-1.5 px-2">{snapshot.paragraph_count}</td>
                <td className="text-right py-1.5 px-2">{snapshot.avg_paragraph_length.toFixed(1)}</td>
                <td className="text-right py-1.5 px-2">{(snapshot.dialogue_ratio * 100).toFixed(0)}%</td>
                <td className="text-right py-1.5 px-2">{snapshot.avg_sentence_length.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 对话占比趋势 */}
      {data.length > 1 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">对话占比趋势</div>
          <svg width="100%" height="40" viewBox={`0 0 ${data.length * 30} 40`} className="text-primary">
            <polyline
              points={data
                .map((s, i) => `${i * 30 + 15},${40 - s.dialogue_ratio * 40}`)
                .join(' ')}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
          </svg>
        </div>
      )}
    </div>
  )
}

// ========== 节奏分析视图 ==========
function RhythmTrackView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="节奏分析将在写作过程中自动生成" />

  const maxTension = Math.max(...data.map((d) => d.tension_score), 1)

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">节奏分析</h3>

      {/* 张力曲线 */}
      <div>
        <div className="text-[10px] text-muted-foreground mb-1">张力曲线</div>
        <svg width="100%" height="60" viewBox={`0 0 ${data.length * 30} 60`} className="text-primary">
          <polyline
            points={data
              .map((d, i) => `${i * 30 + 15},${60 - (d.tension_score / maxTension) * 55}`)
              .join(' ')}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          />
          {data.map((d, i) => (
            <circle
              key={i}
              cx={i * 30 + 15}
              cy={60 - (d.tension_score / maxTension) * 55}
              r="3"
              fill="currentColor"
            />
          ))}
        </svg>
        <div className="flex justify-between text-[9px] text-muted-foreground mt-1">
          <span>第{data[0]?.chapter_number}章</span>
          <span>第{data[data.length - 1]?.chapter_number}章</span>
        </div>
      </div>

      {/* 情绪标签分布 */}
      <div>
        <div className="text-[10px] text-muted-foreground mb-1">情绪分布</div>
        <div className="flex flex-wrap gap-1">
          {data.map((d) => (
            <span
              key={d.id}
              className={cn(
                'text-[10px] px-2 py-0.5 rounded',
                d.emotion_score >= 4 ? 'bg-red-50 text-red-700' :
                d.emotion_score >= 3 ? 'bg-amber-50 text-amber-700' :
                'bg-blue-50 text-blue-700'
              )}
            >
              {d.emotion_tag || `第${d.chapter_number}章`}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ========== 通用组件 ==========
function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
      <BarChart3 className="h-8 w-8 mb-3 text-muted-foreground/30" />
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
