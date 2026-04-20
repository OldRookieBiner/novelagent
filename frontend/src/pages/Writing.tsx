// frontend/src/pages/Writing.tsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import DOMPurify from 'dompurify'
import { Button } from '@/components/ui/button'
import TipTapEditor from '@/components/common/TipTapEditor'
import ErrorMessage from '@/components/common/ErrorMessage'
import StepNavigation from '@/components/project/StepNavigation'
import { projectsApi, chapterOutlinesApi, chaptersApi } from '@/lib/api'
import { getSessionToken } from '@/lib/api'
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
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')

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
    setLoading(true)
    setError(null)

    try {
      const projectData = await projectsApi.get(parseInt(id))
      setProject(projectData)

      // Ensure stage is set to chapter_writing when entering writing page
      if (projectData.stage !== 'chapter_writing' &&
          projectData.stage !== 'chapter_reviewing' &&
          projectData.stage !== 'completed') {
        await projectsApi.update(projectData.id, { stage: 'chapter_writing' })
        const updatedProject = await projectsApi.get(parseInt(id))
        setProject(updatedProject)
      }

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)

      // Find first chapter without content, or use first chapter
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
      setError(err instanceof Error ? err.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  const handleChapterSelect = async (chapter: ChapterOutline) => {
    if (isGenerating) return // 生成中不允许切换

    setCurrentChapter(chapter)
    setMode('preview')

    try {
      const chapterData = await chaptersApi.get(parseInt(id!), chapter.chapter_number)
      setContent(chapterData.content || '')
      setWordCount(chapterData.word_count || 0)
    } catch {
      setContent('')
      setWordCount(0)
    }
  }

  const handleGenerate = async () => {
    if (!id || !currentChapter || isGenerating) return

    setIsGenerating(true)
    setContent('')
    setWordCount(0)
    setError(null)

    // Create abort controller for streaming
    abortControllerRef.current = new AbortController()

    try {
      const token = getSessionToken()
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      }
      if (token) {
        const credentials = btoa(`${token}:`)
        headers['Authorization'] = `Basic ${credentials}`
      }

      const response = await fetch(`/api/projects/${id}/chapters/${currentChapter.chapter_number}/generate`, {
        method: 'POST',
        headers,
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: '生成失败' }))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法获取数据流')

      const decoder = new TextDecoder()
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)

        // Parse SSE events properly
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (line.startsWith('data:')) {
            const data = line.slice(5).trim()
            if (data && data !== '[DONE]') {
              // Decode JSON to preserve newlines from backend
              try {
                const decoded = JSON.parse(data)
                accumulated += decoded
              } catch {
                accumulated += data
              }
              // Store as plain text for preview
              setContent(accumulated)
              setWordCount(accumulated.length)
            }
          } else if (line.startsWith('event:')) {
            // Handle event type (done, error, etc.)
            const eventType = line.slice(6).trim()
            if (eventType === 'done') {
              // Generation complete
            }
          } else if (!line.startsWith(':') && line.trim()) {
            // Plain text chunk (fallback for non-SSE format)
            accumulated += line
            setContent(accumulated)
            setWordCount(accumulated.length)
          }
        }
      }

      // Refresh chapter list to update has_content status
      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Failed to generate:', err)
        setError(err instanceof Error ? err.message : '生成失败')
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
    setError(null)
    try {
      await chaptersApi.update(parseInt(id), currentChapter.chapter_number, { content })
      // Refresh chapter list to update has_content status
      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
    } catch (err) {
      console.error('Failed to save:', err)
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setIsSaving(false)
    }
  }

  const handleContentChange = (newContent: string) => {
    setContent(newContent)
    // Calculate word count from HTML content (strip tags for count)
    const textContent = newContent.replace(/<[^>]*>/g, '')
    setWordCount(textContent.length)
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  if (!project || !currentChapter) {
    return (
      <div className="max-w-4xl mx-auto">
        <ErrorMessage message="项目或章节不存在" />
      </div>
    )
  }

  return (
    <div>
      {/* Step Navigation */}
      <StepNavigation
        currentStage={project.stage}
        viewingStep={null}
        onViewStep={(stepIndex) => navigate(`/project/${id}?viewStep=${stepIndex}`)}
      />

      <div className="flex min-h-[calc(100vh-80px)]">
        {/* 左侧章节列表 */}
        <div className="w-[200px] border-r bg-background shrink-0">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm">章节列表</h2>
        </div>
        <div className="overflow-y-auto max-h-[calc(100vh-140px)]">
          {chapterOutlines.map((chapter) => (
            <div
              key={chapter.id}
              onClick={() => handleChapterSelect(chapter)}
              className={`px-4 py-3 text-sm cursor-pointer border-b ${
                currentChapter.id === chapter.id
                  ? 'bg-secondary font-medium'
                  : 'hover:bg-muted'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="truncate">
                  第{chapter.chapter_number}章：{chapter.title || '未命名'}
                </span>
                {chapter.has_content && (
                  <span className="text-green-600 text-xs ml-1">✓</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 右侧区域 */}
      <div className="flex-1 flex flex-col">
        {/* 右上：章节大纲 */}
        <div className="border-b p-4 bg-background">
          <h3 className="font-semibold mb-3">
            第{currentChapter.chapter_number}章：{currentChapter.title || '未命名'}
          </h3>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div><span className="text-muted-foreground">场景：</span>{currentChapter.scene || '-'}</div>
            <div><span className="text-muted-foreground">人物：</span>{currentChapter.characters || '-'}</div>
            <div className="col-span-2"><span className="text-muted-foreground">情节：</span>{currentChapter.plot || '-'}</div>
            <div><span className="text-muted-foreground">冲突：</span>{currentChapter.conflict || '-'}</div>
            <div><span className="text-muted-foreground">结局：</span>{currentChapter.ending || '-'}</div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="px-4 py-2 bg-destructive/10 border-b">
            <ErrorMessage message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* 右下：内容区域 */}
        <div className="flex-1 flex flex-col">
          {/* 状态栏 */}
          <div className="px-4 py-2 border-b bg-muted/30 flex justify-between items-center">
            <div className="flex items-center gap-2">
              {isGenerating ? (
                <>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-sm text-green-600">正在生成...</span>
                </>
              ) : wordCount > 0 ? (
                <>
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span className="text-sm text-green-600">生成完成</span>
                </>
              ) : (
                <span className="text-sm text-muted-foreground">未生成</span>
              )}
            </div>
            <span className="text-sm text-muted-foreground">
              {wordCount > 0 ? `共 ${wordCount} 字` : ''}
            </span>
          </div>

          {/* 内容区：预览或编辑 */}
          <div className="flex-1 overflow-y-auto p-6 bg-background">
            {mode === 'edit' ? (
              <TipTapEditor
                content={content}
                onChange={handleContentChange}
                placeholder="开始写作..."
              />
            ) : (
              <div className="prose max-w-none">
                {(() => {
                  // Use regex to detect actual HTML tags (avoids false positives like "a < b")
                  const hasHtmlTags = /<[a-zA-Z][^>]*>/.test(content)
                  const sanitizedContent = hasHtmlTags ? DOMPurify.sanitize(content) : content

                  return sanitizedContent ? (
                    hasHtmlTags ? (
                      <div
                        className="prose-content"
                        dangerouslySetInnerHTML={{ __html: sanitizedContent }}
                      />
                    ) : (
                      sanitizedContent.split('\n').filter(p => p.trim()).map((paragraph, i) => (
                        <p key={i} className="mb-4 leading-relaxed" style={{ textIndent: '2em' }}>
                          {paragraph}
                        </p>
                      ))
                    )
                  ) : (
                    <p className="text-muted-foreground">点击下方按钮生成内容</p>
                  )
                })()}
              </div>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="px-4 py-3 border-t bg-muted/30 flex gap-2">
            {mode === 'edit' ? (
              <>
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? '保存中...' : '保存'}
                </Button>
                <Button variant="outline" onClick={() => setMode('preview')}>
                  返回预览
                </Button>
              </>
            ) : isGenerating ? (
              <Button variant="destructive" onClick={handleStop}>
                停止生成
              </Button>
            ) : (
              <>
                <Button onClick={handleGenerate}>AI 生成</Button>
                {wordCount > 0 && (
                  <>
                    <Button variant="outline" onClick={() => setMode('edit')}>
                      编辑
                    </Button>
                    <Button variant="outline" onClick={handleGenerate}>
                      重新生成
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => navigate(`/project/${id}/read/${currentChapter.chapter_number}`)}
                    >
                      审核
                    </Button>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
  )
}