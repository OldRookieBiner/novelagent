// frontend/src/components/workbench/creation/useChapterOutlineGeneration.ts

import { useCallback } from 'react'
import { chapterOutlinesApi } from '@/lib/api'
import { workflowApi } from '@/lib/workflowApi'
import { toast } from 'sonner'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useShallow } from 'zustand/react/shallow'
import type { ChapterOutline } from '@/types'

interface UseChapterOutlineGenerationOptions
{
  projectId: number
  selectedModelKey: string | null
  setChapters: React.Dispatch<React.SetStateAction<ChapterOutline[]>>
  setSelectedChapter: React.Dispatch<React.SetStateAction<ChapterOutline | null>>
}

/**
 * 章节大纲生成逻辑 Hook
 * 封装批量生成、重新规划、取消生成的业务逻辑
 */
export function useChapterOutlineGeneration({
  projectId,
  selectedModelKey,
  setChapters,
  setSelectedChapter,
}: UseChapterOutlineGenerationOptions)
{
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

  /** 解析 LLM 配置 ID */
  const parseLlmConfigId = useCallback((): number | undefined =>
  {
    if (!selectedModelKey) return undefined
    const parsed = parseInt(selectedModelKey.split(':')[0])
    return isNaN(parsed) ? undefined : parsed
  }, [selectedModelKey])

  /** 从流式进度数据构建 ChapterOutline 对象 */
  const buildChapterFromStream = useCallback((chapter: {
    chapter_number: number
    title?: string
    scene?: string
    characters?: string
    plot?: string
    conflict?: string
    ending?: string
    target_words?: number
  }, id: number): ChapterOutline => ({
    id,
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
    arc_id: null,
  }), [projectId])

  /** 刷新章节列表 */
  const refreshChapters = useCallback(async (successMessage: string, fallbackMessage?: string) =>
  {
    try
    {
      const data = await chapterOutlinesApi.list(projectId)
      setChapters(data)
      toast.success(successMessage)
    }
    catch (err)
    {
      console.error('Failed to refresh chapter outlines:', err)
      toast.success(fallbackMessage || successMessage)
    }
  }, [projectId, setChapters])

  /** 批量生成所有章节大纲 */
  const handleGenerateAll = useCallback(async () =>
  {
    setChapterOutlineGenerating(true)
    setChapterOutlineProgress(null)
    const completedTitles: string[] = []
    const controller = new AbortController()
    setChapterOutlineAbortController(controller)
    const llmConfigId = parseLlmConfigId()

    try
    {
      await chapterOutlinesApi.createStream(
        projectId,
        {
          onProgress: (chapterNumber, total, chapter) =>
          {
            const newChapter = buildChapterFromStream(chapter, -(chapter.chapter_number))
            setChapters(prev =>
            {
              if (prev.some(c => c.chapter_number === chapter.chapter_number)) return prev
              return [...prev, newChapter].sort((a, b) => a.chapter_number - b.chapter_number)
            })

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
            await refreshChapters(
              `已生成 ${total} 个章节大纲`,
              `已生成 ${total} 个章节大纲，请刷新页面查看`
            )
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
  }, [projectId, parseLlmConfigId, buildChapterFromStream, refreshChapters, setChapterOutlineGenerating, setChapterOutlineProgress, setChapterOutlineAbortController, clearChapterOutlineGenerationState, setChapters])

  /** 取消生成 */
  const handleCancelGenerate = useCallback(() =>
  {
    cancelChapterOutlineGeneration()
    toast.info('已取消生成')
  }, [cancelChapterOutlineGeneration])

  /** 重新规划章节大纲 */
  const handleReplan = useCallback(async () =>
  {
    setChapterOutlineReplaning(true)
    setChapters([])  // 清除旧章节，避免流式期间新旧混合
    setSelectedChapter(null)
    setChapterOutlineProgress(null)
    const completedTitles: string[] = []

    const controller = new AbortController()
    setChapterOutlineAbortController(controller)
    const llmConfigId = parseLlmConfigId()

    try
    {
      await workflowApi.replanChapterOutlines(
        projectId,
        {
          onProgress: (data) =>
          {
            const chapter = data.chapter
            const newChapter = buildChapterFromStream(chapter, Date.now() + chapter.chapter_number)
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
            await refreshChapters(
              `已重新生成 ${data.total} 个章节大纲`,
              `已重新生成 ${data.total} 个章节大纲，请刷新页面查看`
            )
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
  }, [projectId, parseLlmConfigId, buildChapterFromStream, refreshChapters, setChapters, setSelectedChapter, setChapterOutlineReplaning, setChapterOutlineProgress, setChapterOutlineAbortController, clearChapterOutlineGenerationState])

  /** 清理残留的生成状态 */
  const clearResidualState = useCallback(() =>
  {
    const { chapterOutlineGenerating, chapterOutlineReplaning } = useWorkflowStore.getState()
    if (!chapterOutlineGenerating && !chapterOutlineReplaning)
    {
      clearChapterOutlineGenerationState()
    }
  }, [clearChapterOutlineGenerationState])

  return {
    generating,
    replaning,
    progress,
    handleGenerateAll,
    handleCancelGenerate,
    handleReplan,
    clearResidualState,
    clearChapterOutlineGenerationState,
  }
}
