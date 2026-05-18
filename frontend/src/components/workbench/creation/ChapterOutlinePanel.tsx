// frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx

import { useState, useEffect, useCallback } from 'react'
import { Save, Sparkles, Check, X, ChevronLeft, ChevronRight, FileText, RotateCcw, ChevronDown, Pencil, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { chapterOutlinesApi, volumesApi, outlineApi } from '@/lib/api'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { workflowApi } from '@/lib/workflowApi'
import { toast } from 'sonner'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useShallow } from 'zustand/react/shallow'
import type { ChapterOutline, Arc, Volume } from '@/types'

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

  // ========== 长篇小说状态 ==========
  const [novelLength, setNovelLength] = useState<'short' | 'medium' | 'long'>('short')
  const [volumes, setVolumes] = useState<Volume[]>([])
  const [expandedVolumes, setExpandedVolumes] = useState<Set<number>>(new Set())
  const [expandedArcs, setExpandedArcs] = useState<Set<number>>(new Set())
  const [editingArcOutline, setEditingArcOutline] = useState<number | null>(null)
  const [arcOutlineEditValue, setArcOutlineEditValue] = useState('')
  const [arcOutlineSaving, setArcOutlineSaving] = useState<number | null>(null)
  const [generatingArcChapters, setGeneratingArcChapters] = useState<number | null>(null)

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

  // 弧纲流式相关状态
  const {
    arcOutlineGenerating,
    arcOutlineStreamingContent,
    arcOutlineStreamingArcIndex,
    arcChapterGenerating,
    arcChapterStreamingContent,
    arcChapterProgress,
    setArcOutlineGenerating,
    appendArcOutlineChunk,
    setArcOutlineStreamingContent,
    setArcOutlineStreamingArcIndex,
    clearArcOutlineState,
    updateArc,
    setArcChapterGenerating,
    appendArcChapterChunk,
    setArcChapterStreamingChapterNumber,
    setArcChapterProgress,
    clearArcChapterState,
    addChapterOutline,
  } = useWorkflowStore(useShallow(s => ({
    arcOutlineGenerating: s.arcOutlineGenerating,
    arcOutlineStreamingContent: s.arcOutlineStreamingContent,
    arcOutlineStreamingArcIndex: s.arcOutlineStreamingArcIndex,
    arcChapterGenerating: s.arcChapterGenerating,
    arcChapterStreamingContent: s.arcChapterStreamingContent,
    arcChapterProgress: s.arcChapterProgress,
    setArcOutlineGenerating: s.setArcOutlineGenerating,
    appendArcOutlineChunk: s.appendArcOutlineChunk,
    setArcOutlineStreamingContent: s.setArcOutlineStreamingContent,
    setArcOutlineStreamingArcIndex: s.setArcOutlineStreamingArcIndex,
    clearArcOutlineState: s.clearArcOutlineState,
    updateArc: s.updateArc,
    setArcChapterGenerating: s.setArcChapterGenerating,
    appendArcChapterChunk: s.appendArcChapterChunk,
    setArcChapterStreamingChapterNumber: s.setArcChapterStreamingChapterNumber,
    setArcChapterProgress: s.setArcChapterProgress,
    clearArcChapterState: s.clearArcChapterState,
    addChapterOutline: s.addChapterOutline,
  })))

  const { selectedModelKey } = useWorkbenchStore()

  // ========== 数据加载 ==========
  useEffect(() =>
  {
    const fetchData = async () =>
    {
      try
      {
        // 获取小说长度信息
        const outline = await outlineApi.get(projectId)
        const length = outline.collected_info?.novelLength || 'short'
        setNovelLength(length)

        // 获取章节大纲
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0)
        {
          setSelectedChapter(data[0])
        }

        // 长篇小说加载卷/弧结构
        if (length === 'long')
        {
          const volumesData = await volumesApi.listVolumes(projectId)
          setVolumes(volumesData)
        }
      }
      catch (err)
      {
        console.error('Failed to fetch data:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchData()

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
    }
  }, [selectedChapter])

  // ========== 通用保存/确认 ==========
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

  // ========== 短篇/中篇：批量生成章节大纲 ==========
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

  // ========== 短篇/中篇：重新生成章节大纲 ==========
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

  // ========== 长篇小说：弧纲操作 ==========
  /** 运行工作流生成弧纲 */
  const handleGenerateArcOutlines = async () =>
  {
    setArcOutlineGenerating(true)
    setArcOutlineStreamingContent('')
    setArcOutlineStreamingArcIndex(null)

    // 解析模型配置 ID
    let llmConfigId: number | undefined
    if (selectedModelKey)
    {
      const parsed = parseInt(selectedModelKey.split(':')[0])
      if (!isNaN(parsed)) llmConfigId = parsed
    }

    const controller = new AbortController()

    try
    {
      await workflowApi.runWorkflow(
        projectId,
        {
          onNodeStart: (_nodeName) =>
          {
            // 节点开始
          },
          onNodeDone: (_nodeName) =>
          {
            // 节点完成
          },
          onArcOutlineChunk: (content, arcIndex) =>
          {
            appendArcOutlineChunk(content)
            setArcOutlineStreamingArcIndex(arcIndex)
          },
          onArcOutlineDone: (_arcIndex, outline, arcNumber) =>
          {
            // 查找对应弧并更新
            const { arcs } = useWorkflowStore.getState()
            const arc = arcs.find(a => a.arc_number === arcNumber)
            if (arc)
            {
              updateArc(arc.id, { outline, outline_confirmed: false })
            }
            // 重新加载卷/弧数据以获取后端持久化的结果
            volumesApi.listVolumes(projectId).then(setVolumes).catch(console.error)
            clearArcOutlineState()
          },
          onWaiting: (confirmationType) =>
          {
            clearArcOutlineState()
            toast.info(`等待确认: ${confirmationType}`)
          },
          onDone: () =>
          {
            clearArcOutlineState()
            // 重新加载卷/弧数据
            volumesApi.listVolumes(projectId).then(setVolumes).catch(console.error)
          },
          onError: (error) =>
          {
            clearArcOutlineState()
            toast.error(`弧纲生成失败: ${error}`)
          },
        },
        { signal: controller.signal, llmConfigId }
      )
    }
    catch (err)
    {
      clearArcOutlineState()
      toast.error('弧纲生成失败')
    }
  }

  /** 确认弧纲 */
  const handleConfirmArcOutline = async (arc: Arc) =>
  {
    setArcOutlineSaving(arc.id)
    try
    {
      await volumesApi.confirmArcOutline(projectId, arc.id)
      // 更新本地状态
      setVolumes(prev => prev.map(v => ({
        ...v,
        arcs: v.arcs.map(a =>
          a.id === arc.id ? { ...a, outline_confirmed: true } : a
        )
      })))
      toast.success('弧纲已确认')
    }
    catch (err)
    {
      console.error('Failed to confirm arc outline:', err)
      toast.error('确认弧纲失败')
    }
    finally
    {
      setArcOutlineSaving(null)
    }
  }

  /** 保存弧纲编辑 */
  const handleSaveArcOutline = async (arc: Arc) =>
  {
    setArcOutlineSaving(arc.id)
    try
    {
      await volumesApi.updateArc(projectId, arc.id, { outline: arcOutlineEditValue })
      // 更新本地状态
      setVolumes(prev => prev.map(v => ({
        ...v,
        arcs: v.arcs.map(a =>
          a.id === arc.id ? { ...a, outline: arcOutlineEditValue } : a
        )
      })))
      setEditingArcOutline(null)
      toast.success('弧纲已保存')
    }
    catch (err)
    {
      console.error('Failed to save arc outline:', err)
      toast.error('保存弧纲失败')
    }
    finally
    {
      setArcOutlineSaving(null)
    }
  }

  /** 生成本弧章节大纲 */
  const handleGenerateArcChapters = async (arc: Arc) =>
  {
    setGeneratingArcChapters(arc.id)
    setArcChapterGenerating(true)
    setArcChapterStreamingChapterNumber(null)

    // 解析模型配置 ID
    let llmConfigId: number | undefined
    if (selectedModelKey)
    {
      const parsed = parseInt(selectedModelKey.split(':')[0])
      if (!isNaN(parsed)) llmConfigId = parsed
    }

    const controller = new AbortController()

    try
    {
      await workflowApi.runWorkflow(
        projectId,
        {
          onChapterOutlineChunk: (content, chapterNumber, _arcIndex) =>
          {
            appendArcChapterChunk(content)
            setArcChapterStreamingChapterNumber(chapterNumber)
          },
          onChapterOutlineProgress: (chapterNumber, totalInArc, arcIndex, chapter) =>
          {
            clearArcChapterState()
            setArcChapterProgress({
              arcIndex,
              currentChapter: chapterNumber,
              totalInArc,
            })
            // 添加章节到列表
            if (chapter && typeof chapter === 'object')
            {
              const ch = chapter as Record<string, unknown>
              addChapterOutline({
                id: Date.now() + chapterNumber,
                project_id: projectId,
                chapter_number: chapterNumber,
                title: (ch.title as string) || '',
                scene: (ch.scene as string) || '',
                characters: (ch.characters as string) || '',
                plot: (ch.plot as string) || '',
                conflict: (ch.conflict as string) || '',
                ending: (ch.ending as string) || '',
                target_words: (ch.target_words as number) || 3000,
                confirmed: false,
                has_content: false,
                created_at: new Date().toISOString(),
              })
            }
          },
          onWaiting: (_confirmationType) =>
          {
            clearArcChapterState()
          },
          onDone: async () =>
          {
            clearArcChapterState()
            setGeneratingArcChapters(null)
            // 重新加载章节和卷/弧数据
            try
            {
              const [chapterData, volumesData] = await Promise.all([
                chapterOutlinesApi.list(projectId),
                volumesApi.listVolumes(projectId),
              ])
              setChapters(chapterData)
              setVolumes(volumesData)
              toast.success('弧章节大纲生成完成')
            }
            catch (err)
            {
              console.error('Failed to refresh data:', err)
            }
          },
          onError: (error) =>
          {
            clearArcChapterState()
            setGeneratingArcChapters(null)
            toast.error(`弧章节大纲生成失败: ${error}`)
          },
        },
        { signal: controller.signal, llmConfigId }
      )
    }
    catch (err)
    {
      clearArcChapterState()
      setGeneratingArcChapters(null)
      toast.error('弧章节大纲生成失败')
    }
  }

  // ========== 卷/弧展开/折叠 ==========
  const toggleVolume = (volumeNumber: number) =>
  {
    setExpandedVolumes(prev =>
    {
      const next = new Set(prev)
      if (next.has(volumeNumber)) next.delete(volumeNumber)
      else next.add(volumeNumber)
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

  // ========== 长篇小说渲染 ==========
  if (novelLength === 'long')
  {
    return (
      <div className="flex h-full">
        {/* 左侧卷/弧树 */}
        <div className="w-64 border-r bg-white flex flex-col">
          <div className="p-2.5 border-b flex items-center justify-between">
            <span className="text-xs font-medium">卷/弧结构</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={handleGenerateArcOutlines}
              disabled={arcOutlineGenerating}
              title="生成弧纲"
            >
              <Sparkles className="h-3.5 w-3.5 mr-1" />
              {arcOutlineGenerating ? '生成中...' : '生成弧纲'}
            </Button>
          </div>

          {/* 弧纲流式生成显示 */}
          {arcOutlineGenerating && arcOutlineStreamingContent && (
            <div className="p-2 border-b bg-amber-50">
              <div className="text-[10px] text-amber-700 font-medium mb-1">
                ⏳ 生成弧纲中 (弧 {typeof arcOutlineStreamingArcIndex === 'number' ? arcOutlineStreamingArcIndex + 1 : '...'})
              </div>
              <div className="text-xs text-amber-800 whitespace-pre-wrap max-h-24 overflow-auto">
                {arcOutlineStreamingContent}
              </div>
            </div>
          )}

          {/* 按弧生成章节大纲进度 */}
          {arcChapterGenerating && arcChapterProgress && (
            <div className="p-2 border-b bg-blue-50">
              <div className="text-[10px] text-blue-700 font-medium mb-1">
                ⏳ 生成弧章节大纲 ({arcChapterProgress.currentChapter}/{arcChapterProgress.totalInArc})
              </div>
              <div className="h-1.5 bg-blue-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all"
                  style={{ width: `${(arcChapterProgress.currentChapter / arcChapterProgress.totalInArc) * 100}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex-1 overflow-auto">
            {volumes.map((volume) =>
            {
              const isVolumeExpanded = expandedVolumes.has(volume.volume_number)
              return (
                <div key={volume.id}>
                  {/* 卷标题行 */}
                  <button
                    onClick={() => toggleVolume(volume.volume_number)}
                    className="w-full px-2.5 py-2 text-left text-xs font-medium border-b bg-muted/30 hover:bg-muted/50 transition-colors flex items-center gap-1.5"
                  >
                    {isVolumeExpanded
                      ? <ChevronDown className="h-3 w-3 flex-shrink-0" />
                      : <ChevronRight className="h-3 w-3 flex-shrink-0" />
                    }
                    <span className="truncate">卷{volume.volume_number}{volume.title ? `：${volume.title}` : ''}</span>
                    <span className="text-[10px] text-muted-foreground ml-auto flex-shrink-0">
                      {volume.arcs.length} 弧
                    </span>
                  </button>

                  {/* 弧列表 */}
                  {isVolumeExpanded && volume.arcs.map((arc) =>
                  {
                    const isArcExpanded = expandedArcs.has(arc.id)
                    const isStreamingThisArc = arcOutlineGenerating && arcOutlineStreamingArcIndex !== null
                      && volumes.flatMap(v => v.arcs).indexOf(arc) === arcOutlineStreamingArcIndex
                    const isGeneratingThisArcChapters = generatingArcChapters === arc.id

                    return (
                      <div key={arc.id}>
                        {/* 弧标题行 */}
                        <button
                          onClick={() => toggleArc(arc.id)}
                          className={`w-full px-2.5 py-1.5 text-left text-xs border-b hover:bg-muted/50 transition-colors flex items-center gap-1.5 pl-6 ${
                            isStreamingThisArc ? 'bg-amber-50' : ''
                          }`}
                        >
                          {isArcExpanded
                            ? <ChevronDown className="h-3 w-3 flex-shrink-0" />
                            : <ChevronRight className="h-3 w-3 flex-shrink-0" />
                          }
                          <span className="truncate">弧{arc.arc_number}{arc.title ? `：${arc.title}` : ''}</span>
                          {arc.outline_confirmed && <span className="text-[10px] text-green-600 flex-shrink-0">✅</span>}
                          {!arc.outline && !arc.outline_confirmed && <span className="text-[10px] text-amber-500 flex-shrink-0">待生成</span>}
                          {arc.outline && !arc.outline_confirmed && <span className="text-[10px] text-blue-500 flex-shrink-0">待确认</span>}
                        </button>

                        {/* 弧展开内容 */}
                        {isArcExpanded && (
                          <div className="border-b bg-gray-50/50 px-3 py-2 pl-9 space-y-2">
                            {/* 弧纲内容 */}
                            {arc.outline && editingArcOutline !== arc.id && (
                              <div>
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-[10px] text-muted-foreground font-medium">弧纲</span>
                                  <div className="flex items-center gap-1">
                                    {/* 编辑按钮 */}
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-5 px-1.5 text-[10px]"
                                      onClick={() =>
                                      {
                                        setEditingArcOutline(arc.id)
                                        setArcOutlineEditValue(arc.outline || '')
                                      }}
                                      disabled={arc.outline_confirmed}
                                      title="编辑弧纲"
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </Button>
                                    {/* 确认按钮（未确认时显示） */}
                                    {!arc.outline_confirmed && (
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-5 px-1.5 text-[10px] text-green-600 hover:text-green-700"
                                        onClick={() => handleConfirmArcOutline(arc)}
                                        disabled={arcOutlineSaving === arc.id}
                                        title="确认弧纲"
                                      >
                                        <Check className="h-3 w-3 mr-0.5" />
                                        确认
                                      </Button>
                                    )}
                                  </div>
                                </div>
                                <div className={`text-xs whitespace-pre-wrap p-2 rounded border ${
                                  arc.outline_confirmed ? 'bg-green-50 border-green-200 text-green-800' : 'bg-white border-gray-200'
                                }`}>
                                  {arc.outline}
                                </div>
                              </div>
                            )}

                            {/* 弧纲编辑模式 */}
                            {editingArcOutline === arc.id && (
                              <div>
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-[10px] text-muted-foreground font-medium">编辑弧纲</span>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-5 px-1.5 text-[10px]"
                                      onClick={() =>
                                      {
                                        setEditingArcOutline(null)
                                      }}
                                    >
                                      <X className="h-3 w-3" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-5 px-1.5 text-[10px] text-blue-600"
                                      onClick={() => handleSaveArcOutline(arc)}
                                      disabled={arcOutlineSaving === arc.id}
                                    >
                                      <Save className="h-3 w-3 mr-0.5" />
                                      保存
                                    </Button>
                                  </div>
                                </div>
                                <Textarea
                                  value={arcOutlineEditValue}
                                  onChange={(e) => setArcOutlineEditValue(e.target.value)}
                                  rows={5}
                                  className="text-xs"
                                />
                              </div>
                            )}

                            {/* 弧纲流式生成中 */}
                            {isStreamingThisArc && arcOutlineStreamingContent && !arc.outline && (
                              <div>
                                <div className="text-[10px] text-amber-700 font-medium mb-1">生成中...</div>
                                <div className="text-xs whitespace-pre-wrap p-2 rounded border bg-amber-50 border-amber-200 text-amber-800 max-h-32 overflow-auto">
                                  {arcOutlineStreamingContent}
                                </div>
                              </div>
                            )}

                            {/* 弧纲已确认，可生成本弧章节大纲 */}
                            {arc.outline_confirmed && (
                              <div className="pt-1">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="w-full text-xs h-6"
                                  onClick={() => handleGenerateArcChapters(arc)}
                                  disabled={isGeneratingThisArcChapters || arcChapterGenerating}
                                >
                                  <Play className="h-3 w-3 mr-1" />
                                  {isGeneratingThisArcChapters ? '生成中...' : '生成本弧章节大纲'}
                                </Button>
                                {/* 按弧生成时的流式显示 */}
                                {isGeneratingThisArcChapters && arcChapterStreamingContent && (
                                  <div className="mt-1 text-xs whitespace-pre-wrap p-2 rounded border bg-blue-50 border-blue-200 text-blue-800 max-h-24 overflow-auto">
                                    {arcChapterStreamingContent}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* 无弧纲时提示 */}
                            {!arc.outline && !isStreamingThisArc && (
                              <div className="text-[10px] text-muted-foreground">
                                请先点击上方"生成弧纲"按钮
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}

            {volumes.length === 0 && !arcOutlineGenerating && (
              <div className="p-4 text-center text-xs text-muted-foreground">
                <p>请先生成大纲并确认卷/弧结构</p>
                <p className="mt-1 text-[10px]">工作流将自动创建卷和弧</p>
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

        {/* 中间编辑区（复用短篇/中篇的编辑逻辑） */}
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
                <p>请在左侧选择弧并生成章节大纲</p>
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
                    <div className="font-medium text-blue-800">章节大纲统计</div>
                    <div className="text-blue-700">已确认：{confirmedCount} / {chapters.length}</div>
                    <div className="text-blue-700">已写正文：{hasContentCount} 章</div>
                    <div className="text-blue-700">总目标字数：{totalTargetWords.toLocaleString()}</div>
                    <div className="text-blue-700">卷数：{volumes.length}</div>
                    <div className="text-blue-700">弧数：{volumes.reduce((s, v) => s + v.arcs.length, 0)}</div>
                  </div>

                  {selectedChapter.confirmed && (
                    <div className="p-2.5 bg-green-50 rounded-md border border-green-200 text-xs">
                      <p className="font-medium text-green-700">章节已确认</p>
                      <p className="text-green-600 mt-1">可以进行章节写作</p>
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
      </div>
    )
  }

  // ========== 短篇/中篇渲染（保留原有逻辑） ==========
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
                  <div className="font-medium text-blue-800">章节大纲统计</div>
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
