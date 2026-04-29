// frontend/src/components/writing/hooks/useWriting.ts
import { useState, useEffect, useRef, useCallback } from 'react'
import { projectsApi, chapterOutlinesApi, chaptersApi, workflowApi } from '@/lib/api'
import { createSSEStream } from '@/lib/sseParser'
import type { ProjectDetail, ChapterOutline } from '@/types'

/**
 * 写作页面自定义 Hook
 * 管理项目数据、章节状态、AI 生成等逻辑
 */
export function useWriting(projectId: string | undefined)
{
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [currentChapter, setCurrentChapter] = useState<ChapterOutline | null>(null)
  const [content, setContent] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [wordCount, setWordCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')

  const abortControllerRef = useRef<AbortController | null>(null)

  // 组件卸载时取消流式请求
  useEffect(() =>
  {
    fetchData()
    return () =>
    {
      abortControllerRef.current?.abort()
    }
  }, [projectId])

  // 获取项目、章节大纲、章节内容
  const fetchData = useCallback(async () =>
  {
    if (!projectId) return
    setLoading(true)
    setError(null)

    try
    {
      const projectData = await projectsApi.get(parseInt(projectId))
      setProject(projectData)

      // 进入写作页面时确保 stage 为 writing
      const currentStage = projectData.workflow_state?.stage
      if (currentStage !== 'writing' &&
          currentStage !== 'review' &&
          currentStage !== 'complete')
      {
        await workflowApi.updateStage(projectData.id, 'writing')
        const updatedProject = await projectsApi.get(parseInt(projectId))
        setProject(updatedProject)
      }

      const chaptersData = await chapterOutlinesApi.list(parseInt(projectId))
      setChapterOutlines(chaptersData)

      // 优先选择未生成内容的章节
      const nextChapter = chaptersData.find(c => !c.has_content) || chaptersData[0]
      if (nextChapter)
      {
        setCurrentChapter(nextChapter)
        try
        {
          const chapter = await chaptersApi.get(parseInt(projectId), nextChapter.chapter_number)
          setContent(chapter.content || '')
          setWordCount(chapter.word_count || 0)
        }
        catch
        {
          setContent('')
          setWordCount(0)
        }
      }
    }
    catch (err)
    {
      console.error('Failed to fetch data:', err)
      setError(err instanceof Error ? err.message : '加载数据失败')
    }
    finally
    {
      setLoading(false)
    }
  }, [projectId])

  // 切换章节
  const handleChapterSelect = useCallback(async (chapter: ChapterOutline) =>
  {
    if (isGenerating) return

    setCurrentChapter(chapter)
    setMode('preview')

    try
    {
      const chapterData = await chaptersApi.get(parseInt(projectId!), chapter.chapter_number)
      setContent(chapterData.content || '')
      setWordCount(chapterData.word_count || 0)
    }
    catch
    {
      setContent('')
      setWordCount(0)
    }
  }, [projectId, isGenerating])

  // AI 生成章节内容
  const handleGenerate = useCallback(async () =>
  {
    if (!projectId || !currentChapter || isGenerating) return

    setIsGenerating(true)
    setContent('')
    setWordCount(0)
    setError(null)

    const controller = new AbortController()
    abortControllerRef.current = controller

    let accumulated = ''

    await createSSEStream(
      {
        url: `/api/projects/${projectId}/chapters/${currentChapter.chapter_number}/generate`,
        method: 'POST',
        signal: controller.signal,
      },
      (type, data) =>
      {
        if (type === 'message' || !type || type === 'chunk')
        {
          const decoded = typeof data === 'string' ? data : ''
          accumulated += decoded
          setContent(accumulated)
          setWordCount(accumulated.length)
        }
        else if (type === 'done')
        {
          chapterOutlinesApi.list(parseInt(projectId!)).then(chaptersData =>
          {
            setChapterOutlines(chaptersData)
          }).catch(() => {})
        }
      },
      (err) =>
      {
        setError(err)
        setIsGenerating(false)
      }
    )

    setIsGenerating(false)
  }, [projectId, currentChapter, isGenerating])

  // 停止生成
  const handleStop = useCallback(() =>
  {
    abortControllerRef.current?.abort()
    setIsGenerating(false)
  }, [])

  // 保存编辑内容
  const handleSave = useCallback(async () =>
  {
    if (!projectId || !currentChapter) return

    setIsSaving(true)
    setError(null)
    try
    {
      await chaptersApi.update(parseInt(projectId), currentChapter.chapter_number, { content })
      // 刷新章节列表以更新 has_content 状态
      const chaptersData = await chapterOutlinesApi.list(parseInt(projectId))
      setChapterOutlines(chaptersData)
    }
    catch (err)
    {
      console.error('Failed to save:', err)
      setError(err instanceof Error ? err.message : '保存失败')
    }
    finally
    {
      setIsSaving(false)
    }
  }, [projectId, currentChapter, content])

  // 编辑器内容变更
  const handleContentChange = useCallback((newContent: string) =>
  {
    setContent(newContent)
    // 从 HTML 内容中剥离标签计算字数
    const textContent = newContent.replace(/<[^>]*>/g, '')
    setWordCount(textContent.length)
  }, [])

  // 清除错误
  const clearError = useCallback(() =>
  {
    setError(null)
  }, [])

  return {
    // 状态
    project,
    chapterOutlines,
    currentChapter,
    content,
    isGenerating,
    isSaving,
    wordCount,
    error,
    loading,
    mode,
    // 操作
    handleChapterSelect,
    handleGenerate,
    handleStop,
    handleSave,
    handleContentChange,
    setMode,
    clearError,
    refreshChapters: fetchData,
  }
}
