// StructureTab.tsx — 结构标签页

import { useState, useEffect, useCallback } from 'react'
import { GitBranch, BoxSelect, Network, Activity } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { TagEditor } from '@/components/common/TagEditor'
import { cn } from '@/lib/utils'

interface StructureTabProps {
  projectId: number
}

type StructureSection = 'plot_blocks' | 'questions' | 'subplots' | 'rhythm'

const SECTIONS: { key: StructureSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'plot_blocks', label: '情节块', icon: BoxSelect },
  { key: 'questions', label: '问题链', icon: GitBranch },
  { key: 'subplots', label: '支线网络', icon: Network },
  { key: 'rhythm', label: '节奏曲线', icon: Activity },
]

// ========== 支线数据类型 ==========
interface SubplotItem {
  id: number
  name: string
  characters: string[]
  current_status: string
  raised_in_chapter: number | null
  planned_intersection_chapter: number | null
  expected_resolution_chapter: number | null
}

// ========== 时间线条目类型 ==========
interface TimelineItem {
  id: number
  chapter_number: number
  summary: string | null
  rhythm_score: number
  tension_score: number
  emotion_score: number
  emotion_tag: string | null
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  hint: { text: '暗示', color: 'bg-slate-100 text-slate-600' },
  developing: { text: '发展中', color: 'bg-blue-50 text-blue-700' },
  pending_intersection: { text: '待交汇', color: 'bg-amber-50 text-amber-700' },
  resolved: { text: '已解决', color: 'bg-green-50 text-green-700' },
}

export function StructureTab({ projectId }: StructureTabProps) {
  const [activeSection, setActiveSection] = useState<StructureSection>('plot_blocks')
  const [plotBlocks, setPlotBlocks] = useState<any[]>([])
  const [subplots, setSubplots] = useState<SubplotItem[]>([])
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [loading, setLoading] = useState(false)

  const loadStructure = useCallback(async () => {
    setLoading(true)
    try {
      const [blocks, subplotsData, timelineData] = await Promise.all([
        knowledgeApi.getPlotBlocks(projectId),
        knowledgeApi.getSubplots(projectId).catch(() => []),
        knowledgeApi.getTimeline(projectId).catch(() => []),
      ])
      setPlotBlocks(blocks)
      setSubplots(subplotsData)
      setTimeline(timelineData)
    } catch {
      setPlotBlocks([])
      setSubplots([])
      setTimeline([])
    } finally {
      setLoading(false)
    }
  }, [projectId])

  const knowledgeVersion = useWorkbenchStore((s) => s.knowledgeVersion)

  useEffect(() => {
    loadStructure()
  }, [loadStructure, knowledgeVersion])

  const renderContent = () => {
    switch (activeSection) {
      case 'plot_blocks':
        return <PlotBlocksView data={plotBlocks} loading={loading} projectId={projectId} onUpdate={loadStructure} />
      case 'questions':
        return <QuestionsView data={plotBlocks} loading={loading} />
      case 'subplots':
        return <SubplotsView data={subplots} loading={loading} projectId={projectId} onUpdate={loadStructure} />
      case 'rhythm':
        return <RhythmView blocks={plotBlocks} timeline={timeline} loading={loading} />
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
            <GitBranch className="h-4 w-4" />
            结构
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

// ========== 情节块视图 ==========
function PlotBlocksView({ data, loading, projectId, onUpdate }: { data: any[]; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editMood, setEditMood] = useState('')
  const [editQAnswer, setEditQAnswer] = useState<string[]>([])
  const [editQRaise, setEditQRaise] = useState<string[]>([])
  const [editMustHappen, setEditMustHappen] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const startEdit = (block: any) => {
    setEditingId(block.id)
    setEditTitle(block.title || '')
    setEditMood(block.expected_mood || '')
    setEditQAnswer([...(block.questions_to_answer || [])])
    setEditQRaise([...(block.questions_to_raise || [])])
    setEditMustHappen([...(block.must_happen || [])])
  }

  const cancelEdit = () => setEditingId(null)

  const saveEdit = async () => {
    if (!editingId) return
    setSaving(true)
    try {
      await knowledgeApi.updatePlotBlock(projectId, editingId, {
        title: editTitle,
        expected_mood: editMood,
        questions_to_answer: editQAnswer,
        questions_to_raise: editQRaise,
        must_happen: editMustHappen,
      })
      setEditingId(null)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      console.error('Failed to update plot block:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (block: any) => {
    if (!confirm('确认删除该情节块？关联的问题链条目将失去情节块关联。')) return
    try {
      await knowledgeApi.deletePlotBlock(projectId, block.id)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      console.error('Failed to delete plot block:', err)
    }
  }

  if (loading) return <LoadingSkeleton />

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">情节块</h3>
      {data.map((block, index) => (
        <div key={block.id} className="border rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className="bg-primary/10 text-primary text-[10px] font-medium px-2 py-0.5 rounded">
              块 {index + 1}
            </span>
            {editingId === block.id ? (
              <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="flex-1 text-sm border rounded px-2 py-0.5" />
            ) : (
              <span className="text-sm font-medium">{block.title}</span>
            )}
            {editingId === block.id ? (
              <input value={editMood} onChange={(e) => setEditMood(e.target.value)} placeholder="预期情绪" className="text-[10px] border rounded px-1.5 py-0.5 w-20" />
            ) : block.expected_mood && (
              <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                {block.expected_mood}
              </span>
            )}
            <div className="ml-auto flex gap-1">
              {editingId === block.id ? (
                <>
                  <button onClick={saveEdit} disabled={saving} className="text-[10px] text-primary hover:underline disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
                  <button onClick={cancelEdit} className="text-[10px] text-muted-foreground hover:text-foreground">取消</button>
                </>
              ) : (
                <>
                  <button onClick={() => startEdit(block)} className="text-[10px] text-muted-foreground hover:text-foreground">编辑</button>
                  <button onClick={() => handleDelete(block)} className="text-[10px] text-muted-foreground hover:text-red-500">删除</button>
                </>
              )}
            </div>
          </div>

          {block.chapter_start && (
            <div className="text-[10px] text-muted-foreground">
              第 {block.chapter_start}{block.chapter_end ? `-${block.chapter_end}` : '+'} 章
            </div>
          )}

          {editingId === block.id ? (
            <div className="space-y-3">
              <div>
                <div className="text-[10px] text-muted-foreground mb-0.5">回答的问题</div>
                <TagEditor items={editQAnswer} setItems={setEditQAnswer} placeholder="输入问题后回车" />
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground mb-0.5">提出的问题</div>
                <TagEditor items={editQRaise} setItems={setEditQRaise} placeholder="输入问题后回车" />
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground mb-0.5">必须事件</div>
                <TagEditor items={editMustHappen} setItems={setEditMustHappen} placeholder="输入事件后回车" />
              </div>
            </div>
          ) : (
            <>
              {block.questions_to_answer?.length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-0.5">回答的问题</div>
                  <ul className="space-y-0.5">
                    {block.questions_to_answer.map((q: string, i: number) => (
                      <li key={i} className="text-xs flex items-start gap-1">
                        <span className="text-green-500 mt-0.5">✓</span>
                        {q}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {block.questions_to_raise?.length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-0.5">提出的问题</div>
                  <ul className="space-y-0.5">
                    {block.questions_to_raise.map((q: string, i: number) => (
                      <li key={i} className="text-xs flex items-start gap-1">
                        <span className="text-amber-500 mt-0.5">?</span>
                        {q}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {block.must_happen?.length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-0.5">必须事件</div>
                  <ul className="space-y-0.5">
                    {block.must_happen.map((evt: string, i: number) => (
                      <li key={i} className="text-xs flex items-start gap-1">
                        <span className="text-red-500 mt-0.5">!</span>
                        {evt}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {block.completion_summary && (
            <div className="bg-muted/30 rounded px-3 py-2 text-xs text-muted-foreground">
              {block.completion_summary}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ========== 问题链视图 ==========
function QuestionsView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="问题链将随情节块一起生成" />

  const questions: { text: string; type: 'answer' | 'raise'; blockTitle: string }[] = []
  for (const block of data) {
    for (const q of block.questions_to_answer || []) {
      questions.push({ text: q, type: 'answer', blockTitle: block.title })
    }
    for (const q of block.questions_to_raise || []) {
      questions.push({ text: q, type: 'raise', blockTitle: block.title })
    }
  }

  if (!questions.length) return <EmptyState label="问题链将随情节块一起生成" />

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">问题链</h3>
      {questions.map((q, i) => (
        <div key={i} className="flex items-start gap-2 border-l-2 pl-3 py-1"
          style={{ borderColor: q.type === 'answer' ? '#22c55e' : '#f59e0b' }}>
          <span className={cn(
            'text-[10px] px-1.5 py-0.5 rounded shrink-0',
            q.type === 'answer' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
          )}>
            {q.type === 'answer' ? '回答' : '提出'}
          </span>
          <div className="flex-1">
            <div className="text-xs">{q.text}</div>
            <div className="text-[10px] text-muted-foreground">{q.blockTitle}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ========== 支线网络视图 ==========
function SubplotsView({ data, loading, projectId, onUpdate }: { data: SubplotItem[]; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editStatus, setEditStatus] = useState('hint')
  const [editRaised, setEditRaised] = useState<number | ''>('')
  const [editIntersection, setEditIntersection] = useState<number | ''>('')
  const [editResolution, setEditResolution] = useState<number | ''>('')
  const [saving, setSaving] = useState(false)

  const resetForm = () => {
    setEditName(''); setEditStatus('hint'); setEditRaised(''); setEditIntersection(''); setEditResolution('')
  }

  const startCreate = () => {
    resetForm(); setEditingId(null); setShowCreateForm(true)
  }

  const startEdit = (s: SubplotItem) => {
    setEditName(s.name); setEditStatus(s.current_status)
    setEditRaised(s.raised_in_chapter ?? ''); setEditIntersection(s.planned_intersection_chapter ?? '')
    setEditResolution(s.expected_resolution_chapter ?? ''); setEditingId(s.id); setShowCreateForm(true)
  }

  const cancelForm = () => { setShowCreateForm(false); setEditingId(null); resetForm() }

  const saveForm = async () => {
    setSaving(true)
    try {
      const payload = {
        name: editName,
        current_status: editStatus,
        raised_in_chapter: editRaised || null,
        planned_intersection_chapter: editIntersection || null,
        expected_resolution_chapter: editResolution || null,
      }
      if (editingId) {
        await knowledgeApi.updateSubplot(projectId, editingId, payload)
      } else {
        await knowledgeApi.createSubplot(projectId, payload)
      }
      cancelForm()
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      console.error('Failed to save subplot:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (s: SubplotItem) => {
    if (!confirm('确认删除该支线？')) return
    try {
      await knowledgeApi.deleteSubplot(projectId, s.id)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      console.error('Failed to delete subplot:', err)
    }
  }

  if (loading) return <LoadingSkeleton />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">支线网络</h3>
        <button onClick={startCreate} className="text-[10px] text-muted-foreground hover:text-foreground">+ 新增支线</button>
      </div>

      {/* 创建/编辑表单 */}
      {showCreateForm && (
        <div className="border rounded-lg p-3 space-y-2 bg-muted/10">
          <div className="text-xs font-medium">{editingId ? '编辑支线' : '新增支线'}</div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-[10px] text-muted-foreground">名称</div>
              <input value={editName} onChange={(e) => setEditName(e.target.value)} className="w-full text-xs border rounded px-2 py-1" placeholder="支线名称" />
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">状态</div>
              <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)} className="w-full text-xs border rounded px-2 py-1">
                <option value="hint">暗示</option>
                <option value="developing">发展中</option>
                <option value="pending_intersection">待交汇</option>
                <option value="resolved">已解决</option>
              </select>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">提出章节</div>
              <input type="number" value={editRaised} onChange={(e) => setEditRaised(e.target.value ? parseInt(e.target.value) : '')} className="w-full text-xs border rounded px-2 py-1" />
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">交汇章节</div>
              <input type="number" value={editIntersection} onChange={(e) => setEditIntersection(e.target.value ? parseInt(e.target.value) : '')} className="w-full text-xs border rounded px-2 py-1" />
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">解决章节</div>
              <input type="number" value={editResolution} onChange={(e) => setEditResolution(e.target.value ? parseInt(e.target.value) : '')} className="w-full text-xs border rounded px-2 py-1" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={saveForm} disabled={saving} className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50">{saving ? '保存中...' : '保存'}</button>
            <button onClick={cancelForm} className="text-xs px-3 py-1.5 border rounded hover:bg-muted/50">取消</button>
          </div>
        </div>
      )}

      {data.map((subplot) => {
        const statusInfo = STATUS_LABELS[subplot.current_status] || STATUS_LABELS.hint
        return (
          <div key={subplot.id} className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{subplot.name}</span>
              <span className={cn('text-[10px] px-1.5 py-0.5 rounded', statusInfo.color)}>
                {statusInfo.text}
              </span>
              <div className="ml-auto flex gap-1">
                <button onClick={() => startEdit(subplot)} className="text-[10px] text-muted-foreground hover:text-foreground">编辑</button>
                <button onClick={() => handleDelete(subplot)} className="text-[10px] text-muted-foreground hover:text-red-500">删除</button>
              </div>
            </div>

            {/* 涉及角色 */}
            {subplot.characters?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {subplot.characters.map((c: string, i: number) => (
                  <span key={i} className="text-[10px] bg-primary/5 text-primary px-1.5 py-0.5 rounded">
                    {c}
                  </span>
                ))}
              </div>
            )}

            {/* 章节规划 */}
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              {subplot.raised_in_chapter && (
                <span>提出: 第{subplot.raised_in_chapter}章</span>
              )}
              {subplot.planned_intersection_chapter && (
                <span>交汇: 第{subplot.planned_intersection_chapter}章</span>
              )}
              {subplot.expected_resolution_chapter && (
                <span>解决: 第{subplot.expected_resolution_chapter}章</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ========== 节奏曲线视图 ==========
function RhythmView({ blocks, timeline, loading }: { blocks: any[]; timeline: TimelineItem[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />

  const hasTimeline = timeline.length > 0
  const hasBlocks = blocks.length > 0

  if (!hasTimeline && !hasBlocks) {
    return <EmptyState label="节奏曲线需要情节块或已写章节的时间线数据" />
  }

  return (
    <div className="space-y-6">
      {/* 预期节奏（来自情节块的 expected_mood） */}
      {hasBlocks && (
        <div>
          <h3 className="text-sm font-semibold mb-3">预期节奏</h3>
          <div className="space-y-2">
            {blocks.map((block, index) => (
              <div key={block.id} className="flex items-center gap-3">
                <span className="text-[10px] text-muted-foreground w-16 shrink-0">
                  {block.chapter_start
                    ? `${block.chapter_start}-${block.chapter_end || '…'}`
                    : `块${index + 1}`}
                </span>
                <div className="flex-1 h-6 relative">
                  <div
                    className="h-full rounded bg-primary/10 border border-primary/20"
                    style={{ width: '100%' }}
                  >
                    <div className="absolute inset-0 flex items-center px-2">
                      <span className="text-[10px] font-medium text-primary truncate">
                        {block.title}
                      </span>
                    </div>
                  </div>
                </div>
                {block.expected_mood && (
                  <MoodTag mood={block.expected_mood} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 实际节奏（来自时间线的评分数据） */}
      {hasTimeline && (
        <div>
          <h3 className="text-sm font-semibold mb-3">实际节奏</h3>
          <RhythmChart data={timeline} />
        </div>
      )}
    </div>
  )
}

// 节奏曲线简易柱状图
function RhythmChart({ data }: { data: TimelineItem[] }) {
  // 按 chapter_number 升序
  const sorted = [...data].sort((a, b) => a.chapter_number - b.chapter_number)
  const maxScore = 5

  return (
    <div className="space-y-2">
      <div className="flex items-end gap-1 h-32">
        {sorted.map((entry) => (
          <div key={entry.id} className="flex-1 flex flex-col items-center gap-0.5 min-w-[24px]">
            {/* 张力柱 */}
            <div className="w-full flex flex-col items-center justify-end" style={{ height: '100px' }}>
              <div
                className="w-3 rounded-t"
                style={{
                  height: `${(entry.tension_score / maxScore) * 100}%`,
                  backgroundColor: tensionColor(entry.tension_score),
                }}
              />
            </div>
            <span className="text-[9px] text-muted-foreground">
              {entry.chapter_number}
            </span>
          </div>
        ))}
      </div>

      {/* 图例 */}
      <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded bg-emerald-400" />
          <span>低张力</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded bg-amber-400" />
          <span>中张力</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-2 rounded bg-red-400" />
          <span>高张力</span>
        </div>
      </div>

      {/* 逐章情绪标签 */}
      <div className="flex flex-wrap gap-1 mt-2">
        {sorted.map((entry) => (
          entry.emotion_tag && (
            <span
              key={entry.id}
              className="text-[9px] px-1.5 py-0.5 rounded bg-muted"
            >
              {entry.chapter_number}章: {entry.emotion_tag}
            </span>
          )
        ))}
      </div>
    </div>
  )
}

// 预期情绪标签
function MoodTag({ mood }: { mood: string }) {
  const colorMap: Record<string, string> = {
    '悬念': 'bg-violet-50 text-violet-700',
    '紧张': 'bg-red-50 text-red-700',
    '温暖': 'bg-orange-50 text-orange-700',
    '悲伤': 'bg-blue-50 text-blue-700',
    '转折': 'bg-amber-50 text-amber-700',
    '日常': 'bg-slate-50 text-slate-700',
    '高潮': 'bg-rose-50 text-rose-700',
    '舒缓': 'bg-teal-50 text-teal-700',
  }
  const color = colorMap[mood] || 'bg-gray-50 text-gray-700'
  return (
    <span className={cn('text-[10px] px-1.5 py-0.5 rounded shrink-0', color)}>
      {mood}
    </span>
  )
}

// 张力值 → 颜色
function tensionColor(score: number): string {
  if (score <= 2) return '#34d399' // emerald-400
  if (score <= 3) return '#fbbf24' // amber-400
  return '#f87171' // red-400
}

// ========== 通用组件 ==========
function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
      <GitBranch className="h-8 w-8 mb-3 text-muted-foreground/30" />
      <p>{label}</p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-5 w-24 bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
    </div>
  )
}
