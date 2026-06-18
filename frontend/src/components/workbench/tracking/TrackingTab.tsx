// TrackingTab.tsx — 追踪标签页

import { useState, useEffect, useCallback } from 'react'
import { BarChart3, Map, GitBranch, Activity } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useProjectStore } from '@/stores/projectStore'
import { toast } from 'sonner'
import type { Foreshadowing, TimelineEntry, StyleSnapshot, PlotBlock } from '@/types/knowledge'

interface TrackingTabProps {
  projectId: number
}

type TrackingSection = 'foreshadowing' | 'timeline' | 'style' | 'rhythm'

const SECTIONS: { key: TrackingSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'foreshadowing', label: '伏笔追踪', icon: Map },
  { key: 'timeline', label: '时间线', icon: GitBranch },
  { key: 'style', label: '风格偏差', icon: Activity },
  { key: 'rhythm', label: '节奏对比', icon: BarChart3 },
]

// 情绪标签 → 数值映射（用于节奏对比预期曲线插值）
const MOOD_NUMERIC: Record<string, number> = {
  '日常': 1,
  '舒缓': 1.5,
  '悬念': 2.5,
  '转折': 3.5,
  '紧张': 4,
  '高潮': 5,
  '悲伤': 3,
}

export function TrackingTab({ projectId }: TrackingTabProps) {
  const [activeSection, setActiveSection] = useState<TrackingSection>('foreshadowing')
  const [foreshadowings, setForeshadowings] = useState<Foreshadowing[]>([])
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [styleSnapshots, setStyleSnapshots] = useState<StyleSnapshot[]>([])
  const [plotBlocks, setPlotBlocks] = useState<PlotBlock[]>([])
  const [loading, setLoading] = useState(false)

  const loadTracking = useCallback(async () => {
    setLoading(true)
    try {
      const [fs, tl, ss, pb] = await Promise.allSettled([
        knowledgeApi.getForeshadowings(projectId),
        knowledgeApi.getTimeline(projectId),
        knowledgeApi.getStyleSnapshots(projectId, 20),
        knowledgeApi.getPlotBlocks(projectId),
      ])
      if (fs.status === 'fulfilled') setForeshadowings(fs.value)
      if (tl.status === 'fulfilled') setTimeline(tl.value)
      if (ss.status === 'fulfilled') setStyleSnapshots(ss.value)
      if (pb.status === 'fulfilled') setPlotBlocks(pb.value)
    } catch (err) {
      console.error('Failed to load tracking data:', err)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const knowledgeVersion = useWorkbenchStore((s) => s.knowledgeVersion)

  useEffect(() => {
    loadTracking()
  }, [loadTracking, knowledgeVersion])

  const renderContent = () => {
    switch (activeSection) {
      case 'foreshadowing':
        return <ForeshadowingTrackView data={foreshadowings} loading={loading} projectId={projectId} onUpdate={loadTracking} />
      case 'timeline':
        return <TimelineTrackView data={timeline} loading={loading} />
      case 'style':
        return <StyleTrackView data={styleSnapshots} loading={loading} />
      case 'rhythm':
        return <RhythmTrackView timeline={timeline} plotBlocks={plotBlocks} loading={loading} />
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
function ForeshadowingTrackView({ data, loading, projectId, onUpdate }: { data: Foreshadowing[]; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  // 编辑表单字段（不含 status）
  const [editContent, setEditContent] = useState('')
  const [editLevel, setEditLevel] = useState('hint')
  const [editPlanted, setEditPlanted] = useState<number | ''>('')
  const [editExpected, setEditExpected] = useState<number | ''>('')
  const [editRelated, setEditRelated] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const currentChapterNum = useProjectStore((s) => s.currentChapterNum)

  const resetForm = () => {
    setEditContent(''); setEditLevel('hint'); setEditPlanted(''); setEditExpected(''); setEditRelated([])
  }

  const startCreate = () => {
    resetForm(); setEditingId(null); setShowCreateForm(true)
  }

  const startEdit = (f: Foreshadowing) => {
    setEditContent(f.content); setEditLevel(f.level)
    setEditPlanted(f.planted_chapter ?? ''); setEditExpected(f.expected_resolve_chapter ?? '')
    setEditRelated([...(f.related_characters || [])]); setEditingId(f.id); setShowCreateForm(true)
  }

  const cancelForm = () => { setShowCreateForm(false); setEditingId(null); resetForm() }

  const saveForm = async () => {
    setSaving(true)
    try {
      const payload = {
        content: editContent,
        level: editLevel,
        planted_chapter: editPlanted || null,
        expected_resolve_chapter: editExpected || null,
        related_characters: editRelated,
      }
      if (editingId) {
        await knowledgeApi.updateForeshadowing(projectId, editingId, payload)
        toast.success('伏笔已更新')
      } else {
        await knowledgeApi.createForeshadowing(projectId, { ...payload, status: 'active' })
        toast.success('伏笔已创建')
      }
      cancelForm()
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err: any) {
      toast.error('操作失败：' + (err.message || '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  // 状态流转
  const transitionStatus = async (f: Foreshadowing, newStatus: string) => {
    try {
      const payload: Record<string, unknown> = { status: newStatus }
      if (newStatus === 'reclaimed') {
        payload.resolved_chapter = currentChapterNum
      }
      await knowledgeApi.updateForeshadowing(projectId, f.id, payload)
      toast.success(newStatus === 'pending_reclaim' ? '已标记待回收' : '已确认回收')
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err: any) {
      toast.error('状态流转失败：' + (err.message || '未知错误'))
    }
  }

  if (loading) return <LoadingSkeleton />

  // 按状态分组
  const pendingReclaim = data.filter((f) => f.status === 'pending_reclaim')
  const active = data.filter((f) => f.status === 'active')
  const reclaimed = data.filter((f) => f.status === 'reclaimed')

  const renderGroup = (items: Foreshadowing[], label: string, color: string) => {
    if (!items.length) return null
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded', color)}>{label}</span>
          <span className="text-[10px] text-muted-foreground">{items.length} 条</span>
        </div>
        {items.map((item) => {
          const isOverdue = item.status === 'pending_reclaim' && item.expected_resolve_chapter && item.expected_resolve_chapter < currentChapterNum
          const isReclaimed = item.status === 'reclaimed'
          return (
            <div key={item.id} className={cn('border rounded-lg p-3 space-y-1', isReclaimed && 'opacity-60')}>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">第{item.planted_chapter}章埋设</span>
                {item.expected_resolve_chapter && (
                  <>
                    <span className="text-muted-foreground">→</span>
                    <span className={cn(isOverdue ? 'text-red-600 font-medium' : 'text-muted-foreground')}>
                      预计第{item.expected_resolve_chapter}章回收
                    </span>
                  </>
                )}
                {isOverdue && (
                  <span className="text-[10px] text-red-600 font-medium">⚠ 已逾期</span>
                )}
                {item.resolved_chapter && (
                  <span className="text-green-600">第{item.resolved_chapter}章已回收</span>
                )}
                {/* 级别标签 */}
                <span className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded',
                  item.level === 'hint' ? 'bg-slate-50 text-slate-600' :
                  item.level === 'strengthened' ? 'bg-blue-50 text-blue-700' :
                  'bg-violet-50 text-violet-700'
                )}>
                  {item.level === 'hint' ? '暗示' : item.level === 'strengthened' ? '强化' : '揭示'}
                </span>
              </div>
              <div className={cn('text-xs', isReclaimed && 'line-through')}>{item.content}</div>
              {item.related_characters?.length > 0 && (
                <div className="flex gap-1">
                  {item.related_characters.map((c: string, i: number) => (
                    <span key={i} className="bg-muted text-[10px] px-1.5 py-0.5 rounded">{c}</span>
                  ))}
                </div>
              )}
              {/* 操作按钮 */}
              <div className="flex items-center gap-2 pt-1">
                <button onClick={() => startEdit(item)} className="text-[10px] text-muted-foreground hover:text-foreground">编辑</button>
                {item.status === 'active' && (
                  <button onClick={() => transitionStatus(item, 'pending_reclaim')} className="text-[10px] text-amber-600 hover:text-amber-700">⏱ 标记待回收</button>
                )}
                {item.status === 'pending_reclaim' && (
                  <button onClick={() => transitionStatus(item, 'reclaimed')} className="text-[10px] text-green-600 hover:text-green-700">✓ 确认已回收</button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">伏笔追踪</h3>
        <button onClick={startCreate} className="text-[10px] text-muted-foreground hover:text-foreground">+ 新增伏笔</button>
      </div>

      {/* 创建/编辑表单 */}
      {showCreateForm && (
        <div className="border rounded-lg p-3 space-y-2 bg-muted/10">
          <div className="text-xs font-medium">{editingId ? '编辑伏笔' : '新增伏笔'}</div>
          <div className="space-y-2">
            <div>
              <div className="text-[10px] text-muted-foreground">内容</div>
              <textarea value={editContent} onChange={(e) => setEditContent(e.target.value)} className="w-full text-xs border rounded px-2 py-1 min-h-[60px]" placeholder="伏笔内容" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <div className="text-[10px] text-muted-foreground">级别</div>
                <select value={editLevel} onChange={(e) => setEditLevel(e.target.value)} className="w-full text-xs border rounded px-2 py-1">
                  <option value="hint">暗示</option>
                  <option value="strengthened">强化</option>
                  <option value="revealed">揭示</option>
                </select>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">埋设章节</div>
                <input type="number" value={editPlanted} onChange={(e) => setEditPlanted(e.target.value ? parseInt(e.target.value) : '')} className="w-full text-xs border rounded px-2 py-1" />
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">预计回收章节</div>
                <input type="number" value={editExpected} onChange={(e) => setEditExpected(e.target.value ? parseInt(e.target.value) : '')} className="w-full text-xs border rounded px-2 py-1" />
              </div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">关联角色</div>
              <div className="flex flex-wrap gap-1 mb-1">
                {editRelated.map((c, i) => (
                  <span key={i} className="flex items-center gap-0.5 bg-muted text-[10px] px-1.5 py-0.5 rounded">
                    {c}
                    <button onClick={() => setEditRelated(editRelated.filter((_, idx) => idx !== i))} className="text-muted-foreground hover:text-red-500 ml-0.5">×</button>
                  </span>
                ))}
              </div>
              <input
                placeholder="输入角色名后回车"
                className="w-full text-xs border rounded px-2 py-1"
                onKeyDown={(e) => {
                  const val = (e.target as HTMLInputElement).value.trim()
                  if (e.key === 'Enter' && val) {
                    setEditRelated([...editRelated, val])
                    ;(e.target as HTMLInputElement).value = ''
                    e.preventDefault()
                  }
                }}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={saveForm} disabled={saving || !editContent.trim()} className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
            <button onClick={cancelForm} className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50">取消</button>
          </div>
        </div>
      )}

      {renderGroup(pendingReclaim, '待回收', 'bg-amber-50 text-amber-700')}
      {renderGroup(active, '活跃', 'bg-green-50 text-green-700')}
      {renderGroup(reclaimed, '已回收', 'bg-blue-50 text-blue-700')}
    </div>
  )
}

// ========== 时间线追踪视图 ==========
function TimelineTrackView({ data, loading }: { data: TimelineEntry[]; loading: boolean }) {
  const [chapterStart, setChapterStart] = useState<number | ''>('')
  const [chapterEnd, setChapterEnd] = useState<number | ''>('')
  const [filteredData, setFilteredData] = useState<TimelineEntry[]>(data)

  useEffect(() => {
    let filtered = [...data]
    if (chapterStart !== '') {
      filtered = filtered.filter((e) => e.chapter_number >= chapterStart)
    }
    if (chapterEnd !== '') {
      filtered = filtered.filter((e) => e.chapter_number <= chapterEnd)
    }
    filtered.sort((a, b) => a.chapter_number - b.chapter_number)
    setFilteredData(filtered)
  }, [data, chapterStart, chapterEnd])

  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="时间线将在写作过程中自动生成" />

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">时间线</h3>

      {/* 章节范围筛选 */}
      <div className="flex items-center gap-2 text-[10px]">
        <span className="text-muted-foreground">章节范围</span>
        <input
          type="number"
          value={chapterStart}
          onChange={(e) => setChapterStart(e.target.value ? parseInt(e.target.value) : '')}
          placeholder="起始"
          className="w-16 text-xs border rounded px-2 py-0.5"
        />
        <span className="text-muted-foreground">-</span>
        <input
          type="number"
          value={chapterEnd}
          onChange={(e) => setChapterEnd(e.target.value ? parseInt(e.target.value) : '')}
          placeholder="结束"
          className="w-16 text-xs border rounded px-2 py-0.5"
        />
      </div>

      <div className="relative">
        {filteredData.map((entry, i) => (
          <div key={entry.id} className="flex gap-3 pb-3">
            {/* 时间线竖线 */}
            <div className="flex flex-col items-center w-8 shrink-0">
              <div className="w-2.5 h-2.5 rounded-full bg-primary border-2 border-primary/20" />
              {i < filteredData.length - 1 && <div className="w-0.5 flex-1 bg-primary/20" />}
            </div>
            {/* 内容 */}
            <div className="flex-1 space-y-1 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-medium text-primary">第{entry.chapter_number}章</span>
                {entry.emotion_tag && (
                  <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{entry.emotion_tag}</span>
                )}
              </div>
              {/* ScoreBar */}
              <div className="flex items-center gap-3 text-[9px]">
                <ScoreBar label="节奏" value={entry.rhythm_score} max={5} />
                <ScoreBar label="张力" value={entry.tension_score} max={5} />
                <ScoreBar label="情绪" value={entry.emotion_score} max={5} />
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

// 评分条组件
function ScoreBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min((value / max) * 100, 100)
  const color = value <= 2 ? 'bg-emerald-400' : value <= 3 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-1">
      <span className="text-muted-foreground w-5">{label}</span>
      <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-muted-foreground">{value.toFixed(1)}</span>
    </div>
  )
}

// ========== 风格偏差视图 ==========
function StyleTrackView({ data, loading }: { data: StyleSnapshot[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="风格偏差将在写作过程中自动计算" />

  // 计算各指标的统计范围（均值 ± 1σ）
  const metrics: { key: keyof StyleSnapshot; label: string }[] = [
    { key: 'dialogue_ratio', label: '对话占比' },
    { key: 'avg_sentence_length', label: '平均句长' },
    { key: 'avg_paragraph_length', label: '平均段长' },
    { key: 'paragraph_count', label: '段落数' },
    { key: 'ai_marker_density', label: 'AI 味密度' },
    { key: 'sentence_variety', label: '句长变异性' },
  ]
  const stats: Record<string, { mean: number; std: number }> = {}
  for (const { key } of metrics) {
    const vals = data.map((d) => (d[key] as number | undefined) ?? 0)
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length
    const std = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length)
    stats[key] = { mean, std }
  }

  // 检查某值是否偏离
  const isDeviant = (metric: string, value: number): boolean => {
    const { mean, std } = stats[metric]
    if (std === 0) return false
    return Math.abs(value - mean) > std
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">风格偏差</h3>

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
              <th className="text-right py-1.5 px-2 text-muted-foreground">AI 味密度</th>
              <th className="text-right py-1.5 px-2 text-muted-foreground">句长变异性</th>
              <th className="text-center py-1.5 px-2 text-muted-foreground">偏差</th>
            </tr>
          </thead>
          <tbody>
            {data.map((snapshot) => {
              const aiMarker = snapshot.ai_marker_density ?? 0
              const sentenceVar = snapshot.sentence_variety ?? 0
              const deviantMetrics: string[] = []
              if (isDeviant('paragraph_count', snapshot.paragraph_count)) deviantMetrics.push('段落数')
              if (isDeviant('avg_paragraph_length', snapshot.avg_paragraph_length)) deviantMetrics.push('平均段长')
              if (isDeviant('dialogue_ratio', snapshot.dialogue_ratio)) deviantMetrics.push('对话占比')
              if (isDeviant('avg_sentence_length', snapshot.avg_sentence_length)) deviantMetrics.push('平均句长')
              if (isDeviant('ai_marker_density', aiMarker)) deviantMetrics.push('AI 味密度')
              if (isDeviant('sentence_variety', sentenceVar)) deviantMetrics.push('句长变异性')
              const hasDeviation = deviantMetrics.length > 0

              return (
                <tr key={snapshot.id} className="border-b border-muted/50">
                  <td className="py-1.5 px-2">{snapshot.chapter_number}</td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('paragraph_count', snapshot.paragraph_count) && 'bg-red-50')}>
                    {snapshot.paragraph_count}
                  </td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('avg_paragraph_length', snapshot.avg_paragraph_length) && 'bg-red-50')}>
                    {snapshot.avg_paragraph_length.toFixed(1)}
                  </td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('dialogue_ratio', snapshot.dialogue_ratio) && 'bg-red-50')}>
                    {(snapshot.dialogue_ratio * 100).toFixed(0)}%
                  </td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('avg_sentence_length', snapshot.avg_sentence_length) && 'bg-red-50')}>
                    {snapshot.avg_sentence_length.toFixed(1)}
                  </td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('ai_marker_density', aiMarker) && 'bg-red-50')}>
                    {(aiMarker * 100).toFixed(2)}%
                  </td>
                  <td className={cn('text-right py-1.5 px-2', isDeviant('sentence_variety', sentenceVar) && 'bg-red-50')}>
                    {sentenceVar.toFixed(1)}
                  </td>
                  <td className="text-center py-1.5 px-2">
                    {hasDeviation ? (
                      <span className="text-red-600 cursor-help" title={`偏差项: ${deviantMetrics.join(', ')}`}>
                        ⚠ {deviantMetrics.length}
                      </span>
                    ) : (
                      <span className="text-green-600">✓</span>
                    )}
                  </td>
                </tr>
              )
            })}
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

// ========== 节奏对比视图 ==========
function RhythmTrackView({ timeline, plotBlocks, loading }: { timeline: TimelineEntry[]; plotBlocks: PlotBlock[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!timeline.length && !plotBlocks.length) return <EmptyState label="节奏对比需要情节块和时间线数据" />

  const sortedTimeline = [...timeline].sort((a, b) => a.chapter_number - b.chapter_number)

  // 预期曲线插值：从情节块的 expected_mood 映射到每章的数值
  const maxChapter = sortedTimeline.length > 0 ? sortedTimeline[sortedTimeline.length - 1].chapter_number : 0
  const expectedCurve: { chapter: number; value: number }[] = []

  if (plotBlocks.length > 0 && maxChapter > 0) {
    // 为每章计算预期值
    const blockIntervals = plotBlocks
      .filter((b) => b.chapter_start != null && b.expected_mood)
      .sort((a, b) => a.chapter_start - b.chapter_start)

    for (let ch = 1; ch <= maxChapter; ch++) {
      // 找到包含此章的情节块
      const containingBlock = blockIntervals.find((b) => {
        const start = b.chapter_start
        const end = b.chapter_end || maxChapter
        return ch >= start && ch <= end
      })

      if (containingBlock) {
        expectedCurve.push({ chapter: ch, value: MOOD_NUMERIC[containingBlock.expected_mood] || 3 })
      } else {
        // 未覆盖章节：用最近块的值延伸
        let nearest: PlotBlock | null = null
        let minDist = Infinity
        for (const b of blockIntervals) {
          const mid = (b.chapter_start + (b.chapter_end || maxChapter)) / 2
          const dist = Math.abs(ch - mid)
          if (dist < minDist) { minDist = dist; nearest = b }
        }
        expectedCurve.push({ chapter: ch, value: nearest ? (MOOD_NUMERIC[nearest.expected_mood] || 3) : 3 })
      }
    }
  }

  // 偏差计算
  const deviations: { chapter: number; expected: number; actual: number; diff: number }[] = []
  for (const entry of sortedTimeline) {
    const expected = expectedCurve.find((e) => e.chapter === entry.chapter_number)
    if (expected) {
      const diff = Math.abs(entry.tension_score - expected.value)
      deviations.push({ chapter: entry.chapter_number, expected: expected.value, actual: entry.tension_score, diff })
    }
  }

  // 偏差阈值（均值 + 1σ）
  const avgDiff = deviations.length > 0 ? deviations.reduce((a, d) => a + d.diff, 0) / deviations.length : 0
  const stdDiff = deviations.length > 0
    ? Math.sqrt(deviations.reduce((a, d) => a + (d.diff - avgDiff) ** 2, 0) / deviations.length)
    : 0
  const deviationThreshold = avgDiff + stdDiff

  // SVG 绘图参数
  const chartWidth = Math.max(sortedTimeline.length * 30, 200)
  const chartHeight = 80
  const padding = { top: 5, bottom: 15 }
  const plotHeight = chartHeight - padding.top - padding.bottom

  // 生成 SVG 路径点
  const scaleX = (i: number) => i * (chartWidth / Math.max(sortedTimeline.length - 1, 1))
  const scaleY = (v: number) => padding.top + plotHeight - (v / 5) * plotHeight

  const actualPoints = sortedTimeline.map((d, i) => `${scaleX(i)},${scaleY(d.tension_score)}`).join(' ')
  const expectedPoints = expectedCurve.map((e, i) => `${scaleX(i)},${scaleY(e.value)}`).join(' ')

  // 偏差最大章节（取 top 3）
  const topDeviations = [...deviations].sort((a, b) => b.diff - a.diff).slice(0, 3)

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">节奏对比</h3>

      {/* 叠加曲线图 */}
      {(sortedTimeline.length > 0 || expectedCurve.length > 0) && (
        <div className="border rounded-lg p-3 bg-muted/5">
          <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="text-primary">
            {/* 实际曲线（实线） */}
            {sortedTimeline.length > 1 && (
              <polyline
                points={actualPoints}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
              />
            )}

            {/* 预期曲线（虚线） */}
            {expectedCurve.length > 1 && (
              <polyline
                points={expectedPoints}
                fill="none"
                stroke="#94a3b8"
                strokeWidth="1.5"
                strokeDasharray="4 3"
                strokeLinejoin="round"
              />
            )}

            {/* 偏差高亮点 */}
            {deviations.filter((d) => d.diff > deviationThreshold).map((d) => {
              const idx = sortedTimeline.findIndex((t) => t.chapter_number === d.chapter)
              if (idx < 0) return null
              return (
                <circle
                  key={d.chapter}
                  cx={scaleX(idx)}
                  cy={scaleY(d.actual)}
                  r="4"
                  fill="#f97316"
                  opacity="0.8"
                />
              )
            })}

            {/* 章节标签 */}
            {sortedTimeline.length > 0 && (
              <>
                <text x="0" y={chartHeight} fontSize="8" fill="#94a3b8">{sortedTimeline[0].chapter_number}</text>
                <text x={chartWidth - 15} y={chartHeight} fontSize="8" fill="#94a3b8">{sortedTimeline[sortedTimeline.length - 1].chapter_number}</text>
              </>
            )}
          </svg>

          {/* 图例 */}
          <div className="flex items-center gap-4 text-[10px] text-muted-foreground mt-2">
            <div className="flex items-center gap-1">
              <div className="w-4 h-0.5 bg-current" />
              <span>实际张力</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-0.5 border-t border-dashed border-slate-400" />
              <span>预期节奏</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-orange-500" />
              <span>偏差高亮</span>
            </div>
          </div>
        </div>
      )}

      {/* 偏差预警卡片 */}
      {topDeviations.length > 0 && topDeviations[0].diff > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">偏差最大的章节</div>
          <div className="space-y-1">
            {topDeviations.map((d) => (
              <div key={d.chapter} className="flex items-center gap-2 text-xs border rounded px-3 py-1.5 bg-amber-50/50">
                <span className="font-medium">第{d.chapter}章</span>
                <span className="text-muted-foreground">预期 {d.expected.toFixed(1)}</span>
                <span className="text-muted-foreground">→</span>
                <span className="text-muted-foreground">实际 {d.actual.toFixed(1)}</span>
                <span className={cn('font-medium', d.diff > deviationThreshold ? 'text-red-600' : 'text-amber-600')}>
                  偏差 {d.diff.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 情绪标签分布 */}
      {sortedTimeline.length > 0 && (
        <div>
          <div className="text-[10px] text-muted-foreground mb-1">情绪分布</div>
          <div className="flex flex-wrap gap-1">
            {sortedTimeline.map((d) => (
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
      )}
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
