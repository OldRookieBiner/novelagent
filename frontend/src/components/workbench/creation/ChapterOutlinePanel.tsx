// frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx

import { useState, useEffect, useCallback } from 'react'
import { Save, Sparkles, Check, X, ChevronLeft, ChevronRight, ChevronDown, FileText, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { chapterOutlinesApi, volumesApi, outlineApi, chaptersApi } from '@/lib/api'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { workflowApi } from '@/lib/workflowApi'
import { toast } from 'sonner'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useShallow } from 'zustand/react/shallow'
import type { ChapterOutline, Volume, Arc } from '@/types'

interface ChapterOutlinePanelProps
{
  projectId: number
}

function getChapterStatusIcon(chapter: ChapterOutline): string
{
  if (chapter.has_content) return '📝'
  if (chapter.confirmed) return '✅'
  return ''
}

// 卷折叠行
function VolumeRow(
  { volume, expanded, onToggle }:
  {
    volume: Volume
    expanded: boolean
    onToggle: () => void
  }
)
{
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-2 bg-indigo-50 hover:bg-indigo-100 cursor-pointer select-none border-b border-indigo-100"
      onClick={onToggle}
    >
      {expanded ? <ChevronDown className="h-3.5 w-3.5 text-indigo-600" /> : <ChevronRight className="h-3.5 w-3.5 text-indigo-600" />}
      <span className="text-xs font-medium text-indigo-800 truncate">
        卷{volume.volume_number}：{volume.title || '未命名'}
      </span>
    </div>
  )
}

// 弧折叠行
function ArcRow(
  { arc, expanded, onToggle }:
  {
    arc: Arc
    expanded: boolean
    onToggle: () => void
  }
)
{
  return (
    <div
      className="flex items-center gap-1.5 pl-5 pr-2 py-1.5 bg-blue-50 hover:bg-blue-100 cursor-pointer select-none border-b border-blue-100"
      onClick={onToggle}
    >
      {expanded ? <ChevronDown className="h-3 w-3 text-blue-600" /> : <ChevronRight className="h-3 w-3 text-blue-600" />}
      <span className="text-[11px] font-medium text-blue-800 truncate">
        弧{arc.arc_number}：{arc.title || '未命名'}
      </span>
      <span className="text-[10px] text-blue-400 flex-shrink-0">({arc.chapter_count}章)</span>
    </div>
  )
}

export function ChapterOutlinePanel({ projectId }: ChapterOutlinePanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingTitle, setEditingTitle] = useState('')
  const [editingScene, setEditingScene] = useState('')
  const [editingPlot, setEditingPlot] = useState('')
  const [editingTargetWords, setEditingTargetWords] = useState(3000)
  const [saving, setSaving] = useState(false)
  const [showReplanDialog, setShowReplanDialog] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [chapterSummary, setChapterSummary] = useState<string | null>(null)

  // 长篇模式：卷/弧三级折叠树
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [expandedVolumes, setExpandedVolumes] = useState<Set<number>>(new Set())
  const [expandedArcs, setExpandedArcs] = useState<Set<number>>(new Set())
  const [novelLength, setNovelLength] = useState<'short' | 'medium' | 'long'>('short')

  // 从 workflowStore 读取生成相关状态（使用 useShallow 避免不必要的重渲染）
  const {
    chapterOutlineGenerating: generating,
    chapterOutlineReplaning: replaning,
    chapterOutlineProgress: progress,
    setChapterOutlineGenerating,
    setChapterOutlineReplaning,
    setChapterOutlineProgress,
    setChapterOutlineAbortController,
    cancelChapterOutlineGeneration,
    clearChapterOutlineGenerationState,
  } = useWorkflowStore(useShallow(s => ({
    chapterOutlineGenerating: s.chapterOutlineGenerating,
    chapterOutlineReplaning: s.chapterOutlineReplaning,
    chapterOutlineProgress: s.chapterOutlineProgress,
    setChapterOutlineGenerating: s.setChapterOutlineGenerating,
    setChapterOutlineReplaning: s.setChapterOutlineReplaning,
    setChapterOutlineProgress: s.setChapterOutlineProgress,
    setChapterOutlineAbortController: s.setChapterOutlineAbortController,
    cancelChapterOutlineGeneration: s.cancelChapterOutlineGeneration,
    clearChapterOutlineGenerationState: s.clearChapterOutlineGenerationState,
  })))
  const { selectedModelKey } = useWorkbenchStore()

  // 加载篇幅类型和卷/弧数据
  useEffect(() =>
  {
    const loadMeta = async () =>
    {
      try
      {
        const outline = await outlineApi.get(projectId)
        const nl = (outline.collected_info as Record<string, unknown>)?.novelLength
        if (nl === 'short' || nl === 'medium' || nl === 'long')
        {
          setNovelLength(nl)
        }
      }
      catch
      {
        // outline 不存在（新项目），使用默认 short
      }
    }
    loadMeta()
  }, [projectId])

  useEffect(() =>
  {
    if (novelLength === 'long')
    {
      volumesApi.list(projectId).then(setVolumes).catch(console.error)
    }
  }, [projectId, novelLength])

  const toggleVolume = (volumeId: number) =>
  {
    setExpandedVolumes(prev =>
    {
      const next = new Set(prev)
      if (next.has(volumeId)) next.delete(volumeId)
      else next.add(volumeId)
      return next
    })
  }

  const toggleArc = (arcId: number) =>
  {
    setExpandedArcs(prev =>
    {
      const next = new Set(prev)
      if (next.has(arcId)) next.delete(arcId)
      else next.add(arcId)
      return next
    })
  }

  // 获取属于指定弧的章节
  const getChaptersForArc = (arc: Arc): ChapterOutline[] =>
  {
    return chapters.filter(c => c.arc_id === arc.id)
  }

  // 获取不属于任何弧的章节（非长篇或未分配弧的情况）
  const getUnassignedChapters = (): ChapterOutline[] =>
  {
    return chapters.filter(c => c.arc_id === null)
  }

  useEffect(() =>
  {
    const fetchChapters = async () =>
    {
      try
      {
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0)
        {
          setSelectedChapter(data[0])
        }
      }
      catch (err)
      {
        console.error('Failed to fetch chapters:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchChapters()

    // 如果 store 中没有正在生成的状态，清理可能残留的进度
    const { chapterOutlineGenerating, chapterOutlineReplaning } = useWorkflowStore.getState()
    if (!chapterOutlineGenerating && !chapterOutlineReplaning)
    {
      clearChapterOutlineGenerationState()
    }
  }, [projectId])

  useEffect(() =>
  {
    if (selectedChapter)
    {
      setEditingTitle(selectedChapter.title || '')
      setEditingScene(selectedChapter.scene || '')
      setEditingPlot(selectedChapter.plot || '')
      setEditingTargetWords(selectedChapter.target_words || 3000)

      // 长篇模式：加载章节摘要
      if (novelLength === 'long' && selectedChapter.has_content)
      {
        chaptersApi.get(projectId, selectedChapter.chapter_number)
          .then(ch => setChapterSummary(ch.summary ?? null))
          .catch(() => setChapterSummary(null))
      }
      else
      {
        setChapterSummary(null)
      }
    }
  }, [selectedChapter, projectId, novelLength])

  const handleSave = useCallback(async () =>
  {
    if (!selectedChapter) return
    setSaving(true)
    try
    {
      const updated = await chapterOutlinesApi.update(
        projectId,
        selectedChapter.chapter_number,
        {
          title: editingTitle,
          scene: editingScene,
          plot: editingPlot,
          target_words: editingTargetWords
        }
      )
      setChapters(chapters.map(c => c.id === updated.id ? updated : c))
      setSelectedChapter(updated)
      toast.success('保存成功')
    }
    catch (err)
    {
      console.error('Failed to save chapter outline:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSaving(false)
    }
  }, [selectedChapter, editingTitle, editingScene, editingPlot, editingTargetWords, projectId, chapters])

  const handleConfirm = async () =>
  {
    if (!selectedChapter) return
    try
    {
      await chapterOutlinesApi.confirm(projectId, selectedChapter.chapter_number)
      const updatedChapter = { ...selectedChapter, confirmed: true }
      setChapters(chapters.map(c => c.id === selectedChapter.id ? updatedChapter : c))
      setSelectedChapter(updatedChapter)
      toast.success('章节已确认')
    }
    catch (err)
    {
      console.error('Failed to confirm chapter:', err)
      toast.error('确认失败')
    }
  }

  const handleConfirmAll = async () =>
  {
    const unconfirmed = chapters.filter(c => !c.confirmed)
    if (unconfirmed.length === 0)
    {
      toast.info('所有章节已确认')
      return
    }
    let successCount = 0
    for (const chapter of unconfirmed)
    {
      try
      {
        await chapterOutlinesApi.confirm(projectId, chapter.chapter_number)
        setChapters(prev => prev.map(c =>
          c.id === chapter.id ? { ...c, confirmed: true } : c
        ))
        successCount++
      }
      catch (err)
      {
        console.error(`Failed to confirm chapter ${chapter.chapter_number}:`, err)
      }
    }
    if (successCount > 0)
    {
      toast.success(`已确认 ${successCount} 个章节`)
    }
  }

  const handleGenerateAll = async () =>
  {
    setChapterOutlineGenerating(true)
    setChapterOutlineProgress(null)
    const completedTitles: string[] = []
    const controller = new AbortController()
    setChapterOutlineAbortController(controller)

    // 从 store 解析模型配置 ID
    let llmConfigId: number | undefined
    if (selectedModelKey)
    {
      const configIdStr = selectedModelKey.split(':')[0]
      const parsed = parseInt(configIdStr)
      if (!isNaN(parsed)) llmConfigId = parsed
    }

    try
    {
      await chapterOutlinesApi.createStream(
        projectId,
        {
          onProgress: (chapterNumber, total, chapter) =>
          {
            // 将已生成章节添加到列表（使用后端返回的完整数据）
            const tempId = -(chapter.chapter_number)
            const newChapter: ChapterOutline = {
              id: tempId,
              project_id: projectId,
              chapter_number: chapter.chapter_number,
              arc_id: null,
              title: chapter.title || '',
              scene: chapter.scene || '',
              characters: chapter.characters || '',
              plot: chapter.plot || '',
              conflict: chapter.conflict || '',
              ending: chapter.ending || '',
              target_words: chapter.target_words || 3000,
              confirmed: false,
              has_content: false,
              created_at: new Date().toISOString(),
            }
            setChapters(prev =>
            {
              // 避免重复添加
              if (prev.some(c => c.chapter_number === chapter.chapter_number)) return prev
              return [...prev, newChapter].sort((a, b) => a.chapter_number - b.chapter_number)
            })

            // 更新进度条
            completedTitles.push(chapter.title || `第${chapter.chapter_number}章`)
            setChapterOutlineProgress({
              current: chapterNumber,
              total,
              currentTitle: chapter.title || `第${chapter.chapter_number}章`,
              completed: [...completedTitles]
            })
          },
          onDone: async (total) =>
          {
            clearChapterOutlineGenerationState()
            // 重新获取完整数据以确保显示正确
            try
            {
              const data = await chapterOutlinesApi.list(projectId)
              setChapters(data)
              // 长篇模式：同时刷新卷/弧数据
              if (novelLength === 'long')
              {
                volumesApi.list(projectId).then(setVolumes).catch(console.error)
              }
              toast.success(`已生成 ${total} 个章节大纲`)
            }
            catch (err)
            {
              console.error('Failed to refresh chapter outlines:', err)
              toast.success(`已生成 ${total} 个章节大纲，请刷新页面查看`)
            }
          },
          onError: (error) =>
          {
            clearChapterOutlineGenerationState()
            toast.error(`生成失败: ${error}`)
          }
        },
        { signal: controller.signal },
        llmConfigId
      )
    }
    catch (err)
    {
      clearChapterOutlineGenerationState()
      toast.error('生成失败')
    }
  }

  const handleCancelGenerate = () =>
  {
    cancelChapterOutlineGeneration()
    toast.info('已取消生成')
  }

  const handleReplanChapterOutlines = async () =>
  {
    setShowReplanDialog(false)
    setChapterOutlineReplaning(true)
    setChapters([])  // 清除旧章节，避免流式期间新旧混合
    setChapterOutlineProgress(null)
    const completedTitles: string[] = []

    const controller = new AbortController()
    setChapterOutlineAbortController(controller)

    // 解析模型配置 ID
    let llmConfigId: number | undefined
    if (selectedModelKey)
    {
      const parsed = parseInt(selectedModelKey.split(':')[0])
      if (!isNaN(parsed)) llmConfigId = parsed
    }

    try
    {
      await workflowApi.replanChapterOutlines(
        projectId,
        {
          onProgress: (data) =>
          {
            const chapter = data.chapter
            const newChapter: ChapterOutline = {
              id: Date.now() + chapter.chapter_number,
              project_id: projectId,
              chapter_number: chapter.chapter_number,
              arc_id: null,
              title: chapter.title || '',
              scene: chapter.scene || '',
              characters: chapter.characters || '',
              plot: chapter.plot || '',
              conflict: chapter.conflict || '',
              ending: chapter.ending || '',
              target_words: chapter.target_words || 3000,
              confirmed: false,
              has_content: false,
              created_at: new Date().toISOString(),
            }
            setChapters(prev =>
            {
              if (prev.some(c => c.chapter_number === chapter.chapter_number)) return prev
              return [...prev, newChapter].sort((a, b) => a.chapter_number - b.chapter_number)
            })

            completedTitles.push(chapter.title || `第${chapter.chapter_number}章`)
            setChapterOutlineProgress({
              current: data.chapter_number,
              total: data.total,
              currentTitle: chapter.title || `第${chapter.chapter_number}章`,
              completed: [...completedTitles]
            })
          },
          onDone: async (data) =>
          {
            clearChapterOutlineGenerationState()
            try
            {
              const refreshedData = await chapterOutlinesApi.list(projectId)
              setChapters(refreshedData)
              // 长篇模式：同时刷新卷/弧数据
              if (novelLength === 'long')
              {
                volumesApi.list(projectId).then(setVolumes).catch(console.error)
              }
              toast.success(`已重新生成 ${data.total} 个章节大纲`)
            }
            catch (err)
            {
              toast.success(`已重新生成 ${data.total} 个章节大纲，请刷新页面查看`)
            }
          },
          onError: (error) =>
          {
            clearChapterOutlineGenerationState()
            toast.error(`重新生成失败: ${error}`)
          }
        },
        { signal: controller.signal, llmConfigId }
      )
    }
    catch (err)
    {
      clearChapterOutlineGenerationState()
      toast.error('重新生成失败')
    }
  }

  useEffect(() =>
  {
    const handleKeyDown = (e: KeyboardEvent) =>
    {
      if ((e.metaKey || e.ctrlKey) && e.key === 's')
      {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  const confirmedCount = chapters.filter(c => c.confirmed).length
  const unconfirmedCount = chapters.filter(c => !c.confirmed).length
  const hasContentCount = chapters.filter(c => c.has_content).length
  const totalTargetWords = chapters.reduce((sum, c) => sum + (c.target_words || 3000), 0)

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className="w-40 border-r bg-white flex flex-col">
        <div className="p-2.5 border-b flex items-center justify-between">
          <span className="text-xs font-medium">章节 ({chapters.length})</span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={generating || replaning ? handleCancelGenerate : handleGenerateAll}
              disabled={replaning}
              title={generating ? '取消生成' : '批量生成所有章节大纲'}
            >
              {generating ? <X className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
            </Button>
            {chapters.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => setShowReplanDialog(true)}
                disabled={generating || replaning}
                title="重新生成章节大纲"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
        {/* 进度条 */}
        {progress && (
          <div className="px-2 py-2 bg-blue-50 border-b">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-blue-700 font-medium">
                ⏳ {progress.currentTitle}
              </span>
              <span className="text-[10px] text-blue-600">{progress.current}/{progress.total}</span>
            </div>
            <div className="h-1.5 bg-blue-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
            {progress.completed && progress.completed.length > 0 && (
              <div className="text-[9px] text-blue-400 mt-1 truncate">
                已完成：{progress.completed.join('、')}
              </div>
            )}
          </div>
        )}
        <div className="flex-1 overflow-auto">
          {volumes.length > 0 ? (
            // 长篇模式：三级折叠树（卷 > 弧 > 章节）
            <div>
              {volumes.map(volume => (
                <div key={volume.id}>
                  <VolumeRow
                    volume={volume}
                    expanded={expandedVolumes.has(volume.id)}
                    onToggle={() => toggleVolume(volume.id)}
                  />
                  {expandedVolumes.has(volume.id) && volume.arcs?.map(arc => (
                    <div key={arc.id}>
                      <ArcRow
                        arc={arc}
                        expanded={expandedArcs.has(arc.id)}
                        onToggle={() => toggleArc(arc.id)}
                      />
                      {expandedArcs.has(arc.id) && getChaptersForArc(arc).map(chapter =>
                      {
                        const icon = getChapterStatusIcon(chapter)
                        const isActive = selectedChapter?.id === chapter.id
                        return (
                          <button
                            key={chapter.id}
                            onClick={() => setSelectedChapter(chapter)}
                            className={`w-full pl-8 pr-2.5 py-1.5 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                              isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                            }`}
                          >
                            <div className="flex items-center gap-1.5">
                              <span className="text-muted-foreground text-[10px] min-w-[16px]">{chapter.chapter_number}.</span>
                              <span className="truncate flex-1">{chapter.title || '未命名'}</span>
                              {icon && <span className="text-[10px] flex-shrink-0">{icon}</span>}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  ))}
                </div>
              ))}
              {/* 不属于任何弧的章节 */}
              {getUnassignedChapters().map(chapter =>
              {
                const icon = getChapterStatusIcon(chapter)
                const isActive = selectedChapter?.id === chapter.id
                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                      isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground text-[10px] min-w-[16px]">{chapter.chapter_number}.</span>
                      <span className="truncate flex-1">{chapter.title || '未命名'}</span>
                      {icon && <span className="text-[10px] flex-shrink-0">{icon}</span>}
                    </div>
                  </button>
                )
              })}
            </div>
          ) : (
            // 短/中篇模式：原有平铺列表
            <div>
              {chapters.map((chapter) =>
              {
                const icon = getChapterStatusIcon(chapter)
                const isActive = selectedChapter?.id === chapter.id

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                      isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground text-[10px] min-w-[16px]">{chapter.chapter_number}.</span>
                      <span className="truncate flex-1">{chapter.title || '未命名'}</span>
                      {icon && <span className="text-[10px] flex-shrink-0">{icon}</span>}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        {/* 一键确认 */}
        {unconfirmedCount > 0 && (
          <div className="border-t p-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full text-xs text-green-600 border-green-300 hover:bg-green-50"
              onClick={handleConfirmAll}
            >
              <Check className="h-3 w-3 mr-1" />
              一键确认 ({unconfirmedCount})
            </Button>
          </div>
        )}
      </div>

      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        {selectedChapter ? (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">第 {selectedChapter.chapter_number} 章</h2>
              <div className="flex gap-2">
                {!selectedChapter.confirmed && (
                  <Button variant="outline" size="sm" onClick={handleConfirm}>
                    <Check className="h-4 w-4 mr-1.5" />
                    确认
                  </Button>
                )}
                <Button size="sm" onClick={handleSave} disabled={saving} title="Ctrl+S">
                  <Save className="h-4 w-4 mr-1.5" />
                  {saving ? '保存中...' : '保存'}
                </Button>
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">章节标题</label>
              <Input
                value={editingTitle}
                onChange={(e) => setEditingTitle(e.target.value)}
                placeholder="输入章节标题"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">场景设定</label>
              <Textarea
                value={editingScene}
                onChange={(e) => setEditingScene(e.target.value)}
                placeholder="描述本章场景"
                rows={2}
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">情节概要</label>
              <Textarea
                value={editingPlot}
                onChange={(e) => setEditingPlot(e.target.value)}
                placeholder="描述本章主要情节"
                rows={4}
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">目标字数</label>
              <Input
                type="number"
                value={editingTargetWords}
                onChange={(e) => setEditingTargetWords(parseInt(e.target.value) || 3000)}
                className="w-32"
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
            <Sparkles className="h-8 w-8 text-muted-foreground/40" />
            {chapters.length === 0 ? (
              <>
                <p>请先生成小说大纲，再生成章节大纲</p>
                <Button onClick={handleGenerateAll} disabled={generating}>
                  <Sparkles className="h-4 w-4 mr-1.5" />
                  {generating ? '生成中...' : '生成章节大纲'}
                </Button>
              </>
            ) : (
              <p>选择章节查看大纲</p>
            )}
          </div>
        )}
      </div>

      {/* 右侧详情面板 */}
      <div className={`border-l bg-white shrink-0 transition-all duration-300 ${rightCollapsed ? 'w-12' : 'w-[360px]'} relative ${rightCollapsed ? '' : 'p-3'}`}>
        {/* 收缩展开按钮 */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
        >
          {rightCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
        {!rightCollapsed && (
          <>
            <h3 className="text-xs font-medium mb-3">章节详情</h3>
            {selectedChapter ? (
              <div className="space-y-3">
                <Card>
                  <CardContent className="pt-3 pb-3">
                    <div className="text-xs">
                      <span className="text-muted-foreground">状态：</span>
                      <span className={selectedChapter.confirmed ? 'text-green-600 font-medium' : 'text-amber-600'}>
                        {selectedChapter.confirmed ? '已确认' : '草稿'}
                      </span>
                    </div>
                    {selectedChapter.has_content && (
                      <div className="text-xs mt-1">
                        <span className="text-muted-foreground">已写正文：</span>
                        <span className="text-blue-600 font-medium">是</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <div className="p-3 bg-blue-50 rounded-md border border-blue-200 text-xs space-y-1.5">
                  <div className="font-medium text-blue-800">📊 章节大纲统计</div>
                  <div className="text-blue-700">已确认：{confirmedCount} / {chapters.length}</div>
                  <div className="text-blue-700">已写正文：{hasContentCount} 章</div>
                  <div className="text-blue-700">总目标字数：{totalTargetWords.toLocaleString()}</div>
                </div>

                {selectedChapter.confirmed && (
                  <div className="p-2.5 bg-green-50 rounded-md border border-green-200 text-xs">
                    <p className="font-medium text-green-700">章节已确认</p>
                    <p className="text-green-600 mt-1">可以进行章节写作</p>
                  </div>
                )}

                {/* 长篇模式：章节摘要 */}
                {novelLength === 'long' && chapterSummary && (
                  <div className="p-2.5 bg-purple-50 rounded-md border border-purple-200">
                    <div className="text-xs font-medium text-purple-800 mb-1">章节摘要</div>
                    <div className="text-xs text-purple-700 whitespace-pre-wrap leading-relaxed">{chapterSummary}</div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-32 text-center">
                <p className="text-xs text-muted-foreground">选择章节查看详情</p>
              </div>
            )}
          </>
        )}
        {rightCollapsed && (
          <div className="flex flex-col items-center pt-4 gap-3">
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
      </div>
      <AlertDialog open={showReplanDialog} onOpenChange={setShowReplanDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>重新生成章节大纲</AlertDialogTitle>
            <AlertDialogDescription>
              重新生成将清除所有章节大纲和已写正文，基于当前大纲重新规划章节结构。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleReplanChapterOutlines}>
              确认重新生成
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}