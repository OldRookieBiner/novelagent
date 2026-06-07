// frontend/src/components/workbench/creation/hooks/useChapterGeneration.ts
// 章节正文 SSE 生成逻辑，从 WritingPanel 中提取

import { useRef, useCallback } from 'react'
import { createSSEStream } from '@/lib/sseParser'
import { chaptersApi } from '@/lib/api'
import { useWorkflowStore } from '@/stores/workflowStore'
import { toast } from 'sonner'
import type { ChapterOutline } from '@/types'

interface UseChapterGenerationOptions
{
  projectId: number
  onContentUpdate: (html: string) => void
  onChapterSaved: (chapterId: number) => void
}

interface UseChapterGenerationReturn
{
  generating: boolean
  generatingChapterId: number | null
  handleGenerate: (chapter: ChapterOutline, canGenerate: boolean) => void
  handleCancelGenerate: () => void
}

/** 将原始文本转为 HTML 段落 */
function textToHtml(raw: string): string
{
  if (!raw) return ''
  if (raw.includes('<p>')) return raw
  return raw.split('\n').filter(p => p.trim()).map(p => `<p>${p}</p>`).join('')
}

export function useChapterGeneration({
  projectId,
  onContentUpdate,
  onChapterSaved,
}: UseChapterGenerationOptions): UseChapterGenerationReturn
{
  const abortControllerRef = useRef<AbortController | null>(null)

  const {
    writingChapterGenerating: generating,
    writingGeneratingChapterId: generatingChapterId,
    setWritingChapterGenerating,
    setWritingGeneratingChapterId,
    clearWritingGenerationState,
  } = useWorkflowStore()

  const handleGenerate = useCallback(async (
    chapter: ChapterOutline,
    canGenerate: boolean,
  ) =>
  {
    if (!chapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }

    if (!canGenerate)
    {
      toast.error('请先生成前一章的正文')
      return
    }

    setWritingChapterGenerating(true)
    setWritingGeneratingChapterId(chapter.id)
    onContentUpdate('')

    const controller = new AbortController()
    abortControllerRef.current = controller
    const accumulated: string[] = []

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${chapter.chapter_number}/generate`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'chunk')
          {
            const chunkData = data as { content: string } | string
            const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
            if (chunkText)
            {
              accumulated.push(chunkText)
              onContentUpdate(textToHtml(accumulated.join('')))
            }
          }
          else if (type === 'done')
          {
            const doneData = data as { chapter?: { word_count?: number }; word_count?: number }
            const wordCount = doneData?.chapter?.word_count ?? doneData?.word_count
            toast.success(wordCount ? `AI 生成完成，共 ${wordCount} 字` : 'AI 生成完成')
            onChapterSaved(chapter.id)
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            toast.error(`生成失败: ${errorMsg}`)
          }
          else if (type === 'message' && typeof data === 'string')
          {
            accumulated.push(data)
            onContentUpdate(textToHtml(accumulated.join('')))
          }
        },
        () =>
        {
          toast.error('生成失败，已保留生成内容')
        }
      )

      // 刷新 API 数据确保一致性
      try
      {
        const result = await chaptersApi.get(projectId, chapter.chapter_number)
        if (result.content)
        {
          onContentUpdate(textToHtml(result.content))
        }
      }
      catch { /* 流式内容已显示 */ }
    }
    finally
    {
      clearWritingGenerationState()
      abortControllerRef.current = null
    }
  }, [projectId, onContentUpdate, onChapterSaved])

  const handleCancelGenerate = useCallback(() =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    clearWritingGenerationState()
    toast.info('已取消生成')
  }, [])

  return {
    generating,
    generatingChapterId,
    handleGenerate,
    handleCancelGenerate,
  }
}
