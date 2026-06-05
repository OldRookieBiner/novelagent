// frontend/src/components/workbench/creation/WritingPanel.tsx

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Save, ChevronLeft, ChevronRight, Sparkles, Loader2, Eye, Pencil, PanelLeftClose, PanelLeft } from 'lucide-react'
import DOMPurify from 'dompurify'
import { Button } from '@/components/ui/button'
import Skeleton from '@/components/ui/skeleton'
import { chapterOutlinesApi, chaptersApi } from '@/lib/api'
import { createSSEStream } from '@/lib/sseParser'
import { ChapterNodePanel } from './ChapterNodePanel'
import type { ChapterNode } from './ChapterNodePanel'
import TipTapEditor from '@/components/common/TipTapEditor'
import type { ChapterOutline, Chapter } from '@/types'
import { toast } from 'sonner'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useShallow } from 'zustand/react/shallow'

interface WritingPanelProps
{
  projectId: number
}

function stripHtml(html: string): string
{
  if (!html) return ''
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || div.innerText || ''
}

function getWordCount(text: string): number
{
  if (!text) return 0
  const plainText = /<[a-zA-Z][^>]*>/.test(text) ? stripHtml(text) : text
  const chineseChars = (plainText.match(/[\u4e00-\u9fa5]/g) || []).length
  const englishWords = plainText
    .replace(/[\u4e00-\u9fa5]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 0).length
  return chineseChars + englishWords
}

function getChapterIcon(chapter: ChapterOutline, generatingChapterId: number | null): string
{
  if (generatingChapterId === chapter.id) return '⏳'
  if (chapter.has_content) return '✅'
  if (chapter.confirmed) return '📋'
  return ''
}

function ChapterListSkeleton()
{
  return (
    <div className="space-y-2 p-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}

function EditorSkeleton()
{
  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-40" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-16" />
        </div>
      </div>
      <Skeleton className="h-[calc(100vh-250px)] w-full" />
    </div>
  )
}

export function WritingPanel({ projectId }: WritingPanelProps)
{
  // 从 workflowStore 读取章节正文生成状态（持久化，切换标签不丢失）
  const {
    writingChapterGenerating: generating,
    writingGeneratingChapterId: generatingChapterId,
    setWritingChapterGenerating,
    setWritingGeneratingChapterId,
    clearWritingGenerationState,
  } = useWorkflowStore(useShallow(s => ({
    writingChapterGenerating: s.writingChapterGenerating,
    writingGeneratingChapterId: s.writingGeneratingChapterId,
    setWritingChapterGenerating: s.setWritingChapterGenerating,
    setWritingGeneratingChapterId: s.setWritingGeneratingChapterId,
    clearWritingGenerationState: s.clearWritingGenerationState,
  })))

  // 判断章节是否可生成（前一章已生成 或 为第1章且已确认）
  const canGenerateChapter = (chapter: ChapterOutline): boolean =>
  {
    if (!chapter.confirmed) return false
    if (chapter.chapter_number === 1) return true
    const prevChapter = chapters.find(c => c.chapter_number === chapter.chapter_number - 1)
    return prevChapter?.has_content === true
  }

  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [chapterContent, setChapterContent] = useState<Chapter | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [chapterNode, setChapterNode] = useState<ChapterNode | null>(null)
  const [showChapterNode, setShowChapterNode] = useState(false)

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
        // 如果 store 中标记为正在生成，说明上次生成可能因切换标签中断
        const { writingChapterGenerating } = useWorkflowStore.getState()
        if (writingChapterGenerating)
        {
          clearWritingGenerationState()
          toast.info('生成因切换页面中断，请重新生成')
        }
      }
    }
    fetchChapters()
  }, [projectId])

  // 将原始文本（\n 分隔）转换为 HTML 段落格式
  const formatContentAsHtml = (rawContent: string): string =>
  {
    if (!rawContent) return ''
    // 已经是 HTML 格式则直接返回
    if (rawContent.includes('<p>')) return rawContent
    return rawContent
      .split('\n')
      .filter(p => p.trim())
      .map(p => `<p>${p}</p>`)
      .join('')
  }

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
        // 从 DB 读取的原始文本需转为 HTML 格式显示
        setContent(formatContentAsHtml(chapter.content || ''))
        setSaved(true)
        setTimeout(() => setSaved(false), 1500)
      }
      catch
      {
        setChapterContent(null)
        setContent('')
        setSaved(false)
      }
      finally
      {
        setLoadingContent(false)
      }
    }
    loadContent()
  }, [projectId, selectedChapter])

  const handleSave = useCallback(async () =>
  {
    if (!selectedChapter) return
    setSaving(true)
    setSaved(false)
    try
    {
      if (!chapterContent)
      {
        const created = await chaptersApi.create(projectId, selectedChapter.chapter_number)
        setChapterContent(created)
        setChapters(prev => prev.map(c =>
          c.id === selectedChapter.id ? { ...c, has_content: true } : c
        ))
      }
      const updated = await chaptersApi.update(
        projectId,
        selectedChapter.chapter_number,
        { content }
      )
      setChapterContent(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 1500)
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
  }, [selectedChapter, chapterContent, content, projectId])

  const handleGenerate = useCallback(async () =>
  {
    if (!selectedChapter) return

    if (!selectedChapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }

    if (!canGenerateChapter(selectedChapter))
    {
      toast.error('请先生成前一章的正文')
      return
    }

    // 如果没有现有内容，先展示章节点让用户确认
    if (!content && !showChapterNode) {
      setChapterNode({
        chapterNumber: selectedChapter.chapter_number,
        title: selectedChapter.title || `第${selectedChapter.chapter_number}章`,
        causalChain: "",
        hook: "",
        scenes: [],
        characters: [],
        questionsToAnswer: [],
        questionsToRaise: [],
        foreshadowings: [],
      })
      setShowChapterNode(true)
      return
    }
    setShowChapterNode(false)

    setWritingChapterGenerating(true)
    setWritingGeneratingChapterId(selectedChapter.id)
    setContent('')
    setMode('preview')

    const controller = new AbortController()
    abortControllerRef.current = controller
    const accumulated: string[] = []

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
          if (type === 'chunk')
          {
            // 从 chunk 事件中提取 content 字段
            const chunkData = data as { content: string } | string
            const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
            if (chunkText)
            {
              accumulated.push(chunkText)
              const fullText = accumulated.join('')
              const html = fullText
                .split('\n')
                .filter(p => p.trim())
                .map(p => `<p>${p}</p>`)
                .join('')
              setContent(html)
            }
          }
          else if (type === 'done')
          {
            // 从 done 事件提取章节数据（结构为 {chapter: {id, content, word_count}}）
            const doneData = data as { chapter?: { id?: number; word_count?: number; content?: string }; word_count?: number }
            const chapterData = doneData?.chapter
            const wordCount = chapterData?.word_count ?? doneData?.word_count
            if (wordCount)
            {
              toast.success(`AI 生成完成，共 ${wordCount} 字`)
            }
            else
            {
              toast.success('AI 生成完成')
            }
            // 后端已自动保存，更新前端状态反映已保存
            setChapters(prev => prev.map(c =>
              c.id === selectedChapter.id ? { ...c, has_content: true } : c
            ))
            setSaved(true)
            setTimeout(() => setSaved(false), 1500)
          }
          else if (type === 'error')
          {
            const errorData = data as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            console.error('Generation error:', errorMsg)
            toast.error(`生成失败: ${errorMsg}`)
          }
          // 兼容旧格式：无 event: 前缀的 message 事件（string data）
          else if (type === 'message' && typeof data === 'string')
          {
            accumulated.push(data)
            const fullText = accumulated.join('')
            const html = fullText
              .split('\n')
              .filter(p => p.trim())
              .map(p => `<p>${p}</p>`)
              .join('')
            setContent(html)
          }
        },
        (error) =>
        {
          console.error('Failed to generate:', error)
          toast.error('生成失败，已保留生成内容')
        }
      )

      // 生成完成后刷新 API 数据，确保内容与持久化数据一致
      try
      {
        const chapter = await chaptersApi.get(projectId, selectedChapter.chapter_number)
        setChapterContent(chapter)
        // 使用 API 返回的内容替换流式累积的内容，确保一致性
        if (chapter.content)
        {
          setContent(formatContentAsHtml(chapter.content))
        }
      }
      catch
      {
        // 刷新失败不影响已显示的流式内容
      }
    }
    finally
    {
      clearWritingGenerationState()
      abortControllerRef.current = null
    }
  }, [selectedChapter, projectId])

  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    clearWritingGenerationState()
    toast.info('已取消生成')
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

  useEffect(() =>
  {
    const handleKeyDown = (e: KeyboardEvent) =>
    {
      const isMod = e.metaKey || e.ctrlKey
      if (isMod && e.key === 's')
      {
        e.preventDefault()
        handleSave()
      }
      else if (isMod && e.key === 'Enter')
      {
        e.preventDefault()
        if (!generating)
        {
          handleGenerate()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, handleGenerate, generating])

  const wordCount = useMemo(() => getWordCount(content), [content])
  const writtenCount = chapters.filter(c => c.has_content).length

  if (loading)
  {
    return (
      <div className="flex h-full">
        <div className="w-40 border-r bg-white">
          <ChapterListSkeleton />
        </div>
        <div className="flex-1">
          <EditorSkeleton />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className={`border-r bg-white transition-all duration-300 ${sidebarCollapsed ? 'w-10' : 'w-40'}`}>
        {!sidebarCollapsed ? (
          <>
            <div className="p-2.5 border-b flex items-center justify-between">
              <span className="text-xs font-medium">章节 ({chapters.length})</span>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="text-muted-foreground hover:text-foreground"
                title="折叠侧边栏"
              >
                <PanelLeftClose className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="overflow-auto" style={{ height: 'calc(100% - 80px)' }}>
              {chapters.map((chapter) =>
              {
                const icon = getChapterIcon(chapter, generatingChapterId)
                const isActive = selectedChapter?.id === chapter.id
                const canGenerate = canGenerateChapter(chapter)

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                      isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                    } ${!canGenerate && chapter.confirmed ? 'opacity-50' : ''}`}
                    title={!canGenerate && chapter.confirmed ? '请先生成前一章正文' : undefined}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground text-[10px] min-w-[14px]">{chapter.chapter_number}.</span>
                      <span className="truncate flex-1">{chapter.title || '未命名'}</span>
                      {icon && <span className="text-[10px] flex-shrink-0">{icon}</span>}
                    </div>
                  </button>
                )
              })}
            </div>
            <div className="border-t p-2">
              <div className="text-[10px] text-muted-foreground text-center">
                已写 {writtenCount}/{chapters.length} 章
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center py-3 gap-2">
            <button
              onClick={() => setSidebarCollapsed(false)}
              className="text-muted-foreground hover:text-foreground"
              title="展开侧边栏"
            >
              <PanelLeft className="h-3.5 w-3.5" />
            </button>
            <div className="flex flex-col items-center gap-1">
              {chapters.map((chapter) =>
              {
                const icon = getChapterIcon(chapter, generatingChapterId)
                const isActive = selectedChapter?.id === chapter.id
                const canGenerate = canGenerateChapter(chapter)

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-6 h-6 rounded flex items-center justify-center text-[10px] transition-colors ${
                      isActive ? 'bg-primary/20 text-primary font-medium' : 'text-muted-foreground hover:bg-muted'
                    } ${!canGenerate && chapter.confirmed ? 'opacity-50' : ''}`}
                    title={!canGenerate && chapter.confirmed ? '请先生成前一章正文' : (chapter.title || `第${chapter.chapter_number}章`)}
                  >
                    {icon || chapter.chapter_number}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* 中间写作区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-6 overflow-auto">
          {selectedChapter ? (
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">{selectedChapter.title || `第 ${selectedChapter.chapter_number} 章`}</h2>
                <div className="flex gap-2 items-center">
                  {generating ? (
                    <Button size="sm" variant="destructive" onClick={handleCancelGenerate}>
                      <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                      取消生成
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={handleGenerate} disabled={!canGenerateChapter(selectedChapter)} title="Ctrl+Enter">
                        <Sparkles className="h-4 w-4 mr-1.5" />
                        AI 生成
                      </Button>
                      {content && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setMode(mode === 'preview' ? 'edit' : 'preview')}
                        >
                          {mode === 'preview' ? (
                            <>
                              <Pencil className="h-4 w-4 mr-1.5" />
                              编辑
                            </>
                          ) : (
                            <>
                              <Eye className="h-4 w-4 mr-1.5" />
                              预览
                            </>
                          )}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={saving || generating}
                        title="Ctrl+S"
                        className={saved ? 'bg-green-500 hover:bg-green-500 text-white' : ''}
                      >
                        {saving ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                            保存中
                          </>
                        ) : saved ? (
                          <>
                            <span className="mr-1.5">✅</span>
                            已保存
                          </>
                        ) : (
                          <>
                            <Save className="h-4 w-4 mr-1.5" />
                            保存
                          </>
                        )}
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {/* 章节点确认卡片 */}
              {showChapterNode && chapterNode && (
                <div className="mb-4">
                  <ChapterNodePanel
                    node={chapterNode}
                    onConfirm={() => { setShowChapterNode(false); handleGenerate(); }}
                    onReject={() => setShowChapterNode(false)}
                    onEdit={(updated) => setChapterNode(updated)}
                  />
                </div>
              )}
              {generating && (
                <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>AI 生成中... 字数: {wordCount}</span>
                </div>
              )}
              {loadingContent ? (
                <EditorSkeleton />
              ) : (
                mode === 'edit' ? (
                  <TipTapEditor
                    key={selectedChapter?.id}
                    content={content}
                    onChange={setContent}
                    placeholder="开始写作..."
                  />
                ) : (
                  <div
                    className="w-full min-h-[calc(100vh-280px)] p-4 border rounded-lg overflow-auto prose max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: content
                        ? DOMPurify.sanitize(content)
                        : '<p class="text-muted-foreground">点击 AI 生成按钮开始创作</p>'
                    }}
                  />
                )
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
              <Sparkles className="h-8 w-8 text-muted-foreground/40" />
              <p>选择章节开始写作</p>
            </div>
          )}
        </div>

        {/* 底部导航 */}
        <div className="border-t p-3 flex items-center justify-between bg-white">
          <div className="text-sm text-muted-foreground">
            字数: {wordCount.toLocaleString()}
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

    </div>
  )
}