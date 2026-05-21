// frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx

import { useState, useEffect, useCallback } from 'react'
import { chapterOutlinesApi } from '@/lib/api'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { toast } from 'sonner'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { ChapterOutlineFlatList, type ChapterOutlineProgress } from './ChapterOutlineFlatList'
import { ChapterOutlineEditor } from './ChapterOutlineEditor'
import { ChapterDetailPanel } from './ChapterDetailPanel'
import { useChapterOutlineGeneration } from './useChapterOutlineGeneration'
import type { ChapterOutline } from '@/types'

interface ChapterOutlinePanelProps
{
  projectId: number
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

  const { selectedModelKey } = useWorkbenchStore()

  // 生成相关逻辑（批量生成、重新规划、取消）
  const {
    generating,
    replaning,
    progress,
    handleGenerateAll,
    handleCancelGenerate,
    handleReplan,
    clearResidualState,
  } = useChapterOutlineGeneration({
    projectId,
    selectedModelKey,
    setChapters,
    setSelectedChapter,
  })

  // ==================== 数据获取 ====================

  useEffect(() =>
  {
    const fetchChapters = async () =>
    {
      try
      {
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0) setSelectedChapter(data[0])
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
    clearResidualState()
  }, [projectId, clearResidualState])

  // 选中章节变更时同步编辑字段
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

  // ==================== 编辑操作 ====================

  const handleSave = useCallback(async () =>
  {
    if (!selectedChapter) return
    setSaving(true)
    try
    {
      const updated = await chapterOutlinesApi.update(
        projectId, selectedChapter.chapter_number,
        { title: editingTitle, scene: editingScene, plot: editingPlot, target_words: editingTargetWords }
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
    if (unconfirmed.length === 0) { toast.info('所有章节已确认'); return }

    let successCount = 0
    for (const chapter of unconfirmed)
    {
      try
      {
        await chapterOutlinesApi.confirm(projectId, chapter.chapter_number)
        setChapters(prev => prev.map(c => c.id === chapter.id ? { ...c, confirmed: true } : c))
        successCount++
      }
      catch (err)
      {
        console.error(`Failed to confirm chapter ${chapter.chapter_number}:`, err)
      }
    }
    if (successCount > 0) toast.success(`已确认 ${successCount} 个章节`)
  }

  // Ctrl+S 快捷键
  useEffect(() =>
  {
    const handleKeyDown = (e: KeyboardEvent) =>
    {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); handleSave() }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  // ==================== 计算属性 ====================

  const confirmedCount = chapters.filter(c => c.confirmed).length
  const unconfirmedCount = chapters.filter(c => !c.confirmed).length
  const hasContentCount = chapters.filter(c => c.has_content).length
  const totalTargetWords = chapters.reduce((sum, c) => sum + (c.target_words || 3000), 0)

  // ==================== 渲染 ====================

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <ChapterOutlineFlatList
        chapters={chapters}
        selectedChapterId={selectedChapter?.id ?? null}
        onSelectChapter={setSelectedChapter}
        generating={generating}
        replaning={replaning}
        progress={progress as ChapterOutlineProgress | null}
        onGenerate={handleGenerateAll}
        onCancelGenerate={handleCancelGenerate}
        onReplan={() => setShowReplanDialog(true)}
        unconfirmedCount={unconfirmedCount}
        onConfirmAll={handleConfirmAll}
      />

      {/* 中间编辑区 */}
      <ChapterOutlineEditor
        selectedChapter={selectedChapter}
        editingTitle={editingTitle}
        editingScene={editingScene}
        editingPlot={editingPlot}
        editingTargetWords={editingTargetWords}
        saving={saving}
        chaptersLength={chapters.length}
        generating={generating}
        onTitleChange={setEditingTitle}
        onSceneChange={setEditingScene}
        onPlotChange={setEditingPlot}
        onTargetWordsChange={setEditingTargetWords}
        onConfirm={handleConfirm}
        onSave={handleSave}
        onGenerate={handleGenerateAll}
      />

      {/* 右侧详情面板 */}
      <ChapterDetailPanel
        selectedChapter={selectedChapter}
        collapsed={rightCollapsed}
        onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
        confirmedCount={confirmedCount}
        hasContentCount={hasContentCount}
        totalChapters={chapters.length}
        totalTargetWords={totalTargetWords}
      />

      {/* 重新生成确认对话框 */}
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
            <AlertDialogAction onClick={handleReplan}>
              确认重新生成
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
