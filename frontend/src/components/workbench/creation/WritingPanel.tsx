// frontend/src/components/workbench/creation/WritingPanel.tsx

import { useState, useEffect, useMemo, useRef } from 'react'
import { Save, ChevronLeft, ChevronRight, Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { chapterOutlinesApi, chaptersApi } from '@/lib/api'
import { createSSEStream } from '@/lib/sseParser'
import { AIAssistantPanel } from './AIAssistantPanel'
import type { ChapterOutline, Chapter } from '@/types'
import { toast } from 'sonner'

interface WritingPanelProps
{
  projectId: number
}

// 正确的字数统计：中文字符 + 英文单词
function getWordCount(text: string): number
{
  if (!text) return 0
  const chineseChars = (text.match(/[\u4e00-\u9fa5]/g) || []).length
  const englishWords = text
    .replace(/[\u4e00-\u9fa5]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 0).length
  return chineseChars + englishWords
}

export function WritingPanel({ projectId }: WritingPanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [chapterContent, setChapterContent] = useState<Chapter | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

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
  }, [projectId])

  // 加载章节内容
  useEffect(() =>
  {
    if (!selectedChapter) return

    const loadContent = async () =>
    {
      setLoadingContent(true)
      try
      {
        const chapter = await chaptersApi.get(projectId, selectedChapter.chapter_number)
        setChapterContent(chapter)
        setContent(chapter.content || '')
      }
      catch
      {
        // 章节内容不存在，清空内容
        setChapterContent(null)
        setContent('')
      }
      finally
      {
        setLoadingContent(false)
      }
    }
    loadContent()
  }, [projectId, selectedChapter])

  // 清理 SSE 请求
  useEffect(() =>
  {
    return () =>
    {
      if (abortControllerRef.current)
      {
        abortControllerRef.current.abort()
      }
    }
  }, [])

  // 保存章节内容
  const handleSave = async () =>
  {
    if (!selectedChapter) return
    setSaving(true)
    try
    {
      // 如果章节不存在，先创建
      if (!chapterContent)
      {
        const created = await chaptersApi.create(projectId, selectedChapter.chapter_number)
        setChapterContent(created)
      }
      const updated = await chaptersApi.update(
        projectId,
        selectedChapter.chapter_number,
        { content }
      )
      setChapterContent(updated)
      toast.success('保存成功')
    }
    catch (err)
    {
      console.error('Failed to save chapter:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSaving(false)
    }
  }

  // AI 生成章节内容（SSE 流式）
  const handleGenerate = async () =>
  {
    if (!selectedChapter) return

    // 检查章节大纲是否已确认
    if (!selectedChapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }

    setGenerating(true)
    setContent('') // 清空内容准备生成

    const controller = new AbortController()
    abortControllerRef.current = controller

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${selectedChapter.chapter_number}/generate`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'done')
          {
            // data 包含生成后的字数
            const wordCount = typeof data === 'number' ? data : (data as { word_count?: number })?.word_count
            if (wordCount)
            {
              toast.success(`AI 生成完成，共 ${wordCount} 字`)
            }
            else
            {
              toast.success('AI 生成完成')
            }
          }
          else if (typeof data === 'string')
          {
            // 流式文本内容
            setContent(prev => prev + data)
          }
        },
        (error) =>
        {
          console.error('Failed to generate:', error)
          toast.error('生成失败')
        }
      )
    }
    finally
    {
      setGenerating(false)
      abortControllerRef.current = null
    }
  }

  // 取消 AI 生成
  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      toast.info('已取消生成')
    }
  }

  const navigateChapter = (direction: 'prev' | 'next') =>
  {
    if (!selectedChapter) return
    const currentIndex = chapters.findIndex(c => c.id === selectedChapter.id)
    if (direction === 'prev' && currentIndex > 0)
    {
      setSelectedChapter(chapters[currentIndex - 1])
    }
    else if (direction === 'next' && currentIndex < chapters.length - 1)
    {
      setSelectedChapter(chapters[currentIndex + 1])
    }
  }

  // 计算字数
  const wordCount = useMemo(() => getWordCount(content), [content])

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className="w-44 border-r bg-white">
        <div className="p-3 border-b">
          <span className="text-sm font-medium">章节列表</span>
        </div>
        <div className="overflow-auto">
          {chapters.map((chapter) => (
            <button
              key={chapter.id}
              onClick={() => setSelectedChapter(chapter)}
              className={`w-full px-3 py-2 text-left text-sm border-b hover:bg-muted/50 ${
                selectedChapter?.id === chapter.id ? 'bg-primary/10 border-l-2 border-l-primary' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">{chapter.chapter_number}.</span>
                <span className="truncate">{chapter.title || '未命名'}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 中间写作区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-6 overflow-auto">
          {selectedChapter ? (
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">{selectedChapter.title || `第 ${selectedChapter.chapter_number} 章`}</h2>
                <div className="flex gap-2">
                  {generating ? (
                    <Button size="sm" variant="destructive" onClick={handleCancelGenerate}>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      取消生成
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" onClick={handleGenerate}>
                      <Sparkles className="h-4 w-4 mr-2" />
                      AI 生成
                    </Button>
                  )}
                  <Button size="sm" onClick={handleSave} disabled={saving || generating}>
                    {saving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        保存中
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        保存
                      </>
                    )}
                  </Button>
                </div>
              </div>
              {loadingContent ? (
                <div className="flex items-center justify-center h-[calc(100vh-200px)]">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="开始写作..."
                  className="w-full h-[calc(100vh-200px)] p-4 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              选择章节开始写作
            </div>
          )}
        </div>

        {/* 底部导航 */}
        <div className="border-t p-3 flex items-center justify-between bg-white">
          <div className="text-sm text-muted-foreground">
            字数: {wordCount}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigateChapter('prev')}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              上一章
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigateChapter('next')}>
              下一章
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      {/* 右侧 AI 助手（含审核功能） */}
      <AIAssistantPanel
        projectId={projectId}
        chapterNumber={selectedChapter?.chapter_number}
        chapterContent={content}
        onReviewComplete={() =>
        {
          // 审核结果回调 - 后续可扩展
        }}
      />
    </div>
  )
}
