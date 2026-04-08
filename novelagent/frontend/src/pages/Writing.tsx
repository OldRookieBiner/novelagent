// frontend/src/pages/Writing.tsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import TipTapEditor from '@/components/common/TipTapEditor'
import { projectsApi, chapterOutlinesApi, chaptersApi } from '@/lib/api'
import type { ProjectDetail, ChapterOutline } from '@/types'

export default function Writing() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [currentChapter, setCurrentChapter] = useState<ChapterOutline | null>(null)
  const [content, setContent] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [wordCount, setWordCount] = useState(0)

  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    fetchData()
    return () => {
      // Cancel any ongoing stream
      abortControllerRef.current?.abort()
    }
  }, [id])

  const fetchData = async () => {
    if (!id) return

    try {
      const projectData = await projectsApi.get(parseInt(id))
      setProject(projectData)

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)

      // Find first chapter without content
      const nextChapter = chaptersData.find(c => !c.has_content) || chaptersData[0]
      if (nextChapter) {
        setCurrentChapter(nextChapter)
        // Load existing content if any
        try {
          const chapter = await chaptersApi.get(parseInt(id), nextChapter.chapter_number)
          setContent(chapter.content || '')
          setWordCount(chapter.word_count || 0)
        } catch {
          setContent('')
          setWordCount(0)
        }
      }
    } catch (err) {
      console.error('Failed to fetch data:', err)
    }
  }

  const handleGenerate = async () => {
    if (!id || !currentChapter || isGenerating) return

    setIsGenerating(true)
    setContent('')
    setWordCount(0)

    // Create abort controller for streaming
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`/api/projects/${id}/chapters/${currentChapter.chapter_number}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) throw new Error('Failed to generate')

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        accumulated += chunk
        setContent(accumulated)
        setWordCount(accumulated.length)
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Failed to generate:', err)
      }
    } finally {
      setIsGenerating(false)
    }
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsGenerating(false)
  }

  const handleSave = async () => {
    if (!id || !currentChapter) return

    setIsSaving(true)
    try {
      await chaptersApi.update(parseInt(id), currentChapter.chapter_number, { content })
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setIsSaving(false)
    }
  }

  const handleContentChange = (newContent: string) => {
    setContent(newContent)
    setWordCount(newContent.length)
  }

  if (!project || !currentChapter) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">
          第 {currentChapter.chapter_number} 章：{currentChapter.title || '未命名'}
        </h1>
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>预计 {currentChapter.target_words} 字</span>
          <span>已写 {wordCount} 字</span>
        </div>
      </div>

      {/* Chapter Outline Summary */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">章节大纲</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>{currentChapter.plot}</p>
        </CardContent>
      </Card>

      {/* Editor */}
      <div className="mb-4">
        <TipTapEditor
          content={content}
          onChange={handleContentChange}
          placeholder={isGenerating ? '正在生成...' : '点击下方按钮生成内容，或直接开始写作...'}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {isGenerating ? (
          <Button variant="destructive" onClick={handleStop}>
            停止生成
          </Button>
        ) : (
          <Button onClick={handleGenerate}>AI 生成</Button>
        )}
        <Button variant="outline" onClick={handleSave} disabled={isSaving}>
          {isSaving ? '保存中...' : '保存'}
        </Button>
        {wordCount > 0 && (
          <Button
            variant="outline"
            onClick={() => navigate(`/project/${id}/read/${currentChapter.chapter_number}`)}
          >
            阅读/审核
          </Button>
        )}
      </div>
    </div>
  )
}