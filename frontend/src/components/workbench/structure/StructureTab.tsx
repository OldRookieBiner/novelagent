// StructureTab.tsx — 结构标签页

import { useState, useEffect, useCallback } from 'react'
import { GitBranch, BoxSelect, Network } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { TagEditor } from '@/components/common/TagEditor'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import type { PlotBlock, Subplot } from '@/types/knowledge'

interface StructureTabProps {
  projectId: number
}

type StructureSection = 'plot_blocks' | 'subplots'

const SECTIONS: { key: StructureSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'plot_blocks', label: '情节块', icon: BoxSelect },
  { key: 'subplots', label: '支线网络', icon: Network },
]



const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  hint: { text: '暗示', color: 'bg-slate-100 text-slate-600' },
  developing: { text: '发展中', color: 'bg-blue-50 text-blue-700' },
  pending_intersection: { text: '待交汇', color: 'bg-amber-50 text-amber-700' },
  resolved: { text: '已解决', color: 'bg-green-50 text-green-700' },
}

export function StructureTab({ projectId }: StructureTabProps) {
  const [activeSection, setActiveSection] = useState<StructureSection>('plot_blocks')
  const [plotBlocks, setPlotBlocks] = useState<PlotBlock[]>([])
  const [subplots, setSubplots] = useState<Subplot[]>([])
  const [loading, setLoading] = useState(false)

  const loadStructure = useCallback(async () => {
    setLoading(true)
    try {
      const [blocks, subplotsData] = await Promise.allSettled([
        knowledgeApi.getPlotBlocks(projectId),
        knowledgeApi.getSubplots(projectId),
      ])
      if (blocks.status === 'fulfilled') setPlotBlocks(blocks.value)
      if (subplotsData.status === 'fulfilled') setSubplots(subplotsData.value)
    } catch (err) {
      console.error('Failed to load structure data:', err)
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
      case 'subplots':
        return <SubplotsView data={subplots} loading={loading} projectId={projectId} onUpdate={loadStructure} plotBlocks={plotBlocks} />
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
function PlotBlocksView({ data, loading, projectId, onUpdate }: { data: PlotBlock[]; loading: boolean; projectId: number; onUpdate: () => void }) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editMood, setEditMood] = useState('')
  const [editQAnswer, setEditQAnswer] = useState<string[]>([])
  const [editQRaise, setEditQRaise] = useState<string[]>([])
  const [editMustHappen, setEditMustHappen] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const startEdit = (block: PlotBlock) => {
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
      toast.success('情节块已更新')
      setEditingId(null)
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('情节块更新失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (block: PlotBlock) => {
    if (!confirm('确认删除该情节块？关联的问题链条目将失去情节块关联。')) return
    try {
      await knowledgeApi.deletePlotBlock(projectId, block.id)
      toast.success('情节块已删除')
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('情节块删除失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  if (loading) return <LoadingSkeleton />

  // 问题链统计：所有情节块的回答/提出问题汇总
  const totalToAnswer = data.reduce((sum, b) => sum + (b.questions_to_answer?.length || 0), 0)
  const totalToRaise = data.reduce((sum, b) => sum + (b.questions_to_raise?.length || 0), 0)
  const totalQuestions = totalToAnswer + totalToRaise

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">情节块</h3>
        {totalQuestions > 0 && (
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <span>问题总数 <span className="text-foreground font-medium">{totalQuestions}</span></span>
            <span className="text-emerald-600">回答 {totalToAnswer}</span>
            <span className="text-amber-600">提出 {totalToRaise}</span>
          </div>
        )}
      </div>
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

// ========== 支线网络视图 ==========
function SubplotsView({ data, loading, projectId, onUpdate, plotBlocks }: { data: Subplot[]; loading: boolean; projectId: number; onUpdate: () => void; plotBlocks: PlotBlock[] }) {
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

  const startEdit = (s: Subplot) => {
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
      toast.success(editingId ? '支线已更新' : '支线已创建')
      cancelForm()
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('支线保存失败：' + (err instanceof Error ? err.message : '未知错误'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (s: Subplot) => {
    if (!confirm('确认删除该支线？')) return
    try {
      await knowledgeApi.deleteSubplot(projectId, s.id)
      toast.success('支线已删除')
      useWorkbenchStore.getState().incrementKnowledgeVersion()
      onUpdate()
    } catch (err) {
      toast.error('支线删除失败：' + (err instanceof Error ? err.message : '未知错误'))
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

            {/* 涉及情节块 — 交叉引用 */}
            {(() => {
              const targetChapters = [
                subplot.raised_in_chapter,
                subplot.planned_intersection_chapter,
                subplot.expected_resolution_chapter,
              ].filter((ch): ch is number => typeof ch === 'number')
              if (!targetChapters.length || !plotBlocks.length) return null
              const relatedBlocks = plotBlocks.filter((b) => {
                const start = b.chapter_start ?? 0
                const end = b.chapter_end ?? Number.MAX_SAFE_INTEGER
                return targetChapters.some((ch) => ch >= start && ch <= end)
              })
              if (!relatedBlocks.length) return null
              return (
                <div className="text-[10px] text-muted-foreground">
                  涉及情节块:{' '}
                  {relatedBlocks
                    .map((b) => `「${b.title}」(第${b.chapter_start}${b.chapter_end ? `-${b.chapter_end}` : '+'}章)`)
                    .join(' · ')}
                </div>
              )
            })()}
          </div>
        )
      })}
    </div>
  )
}


// ========== 通用组件 ==========
function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-5 w-24 bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
    </div>
  )
}
