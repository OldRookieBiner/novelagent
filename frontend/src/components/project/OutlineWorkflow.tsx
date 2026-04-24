// frontend/src/components/project/OutlineWorkflow.tsx
import { useState, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { outlineApi, chapterOutlinesApi } from '@/lib/api'
import type { Outline, ChapterOutline } from '@/types'

interface OutlineWorkflowProps {
  projectId: number
  outline: Outline
  onOutlineUpdate: (outline: Outline) => void
  onStageChange: (stage: string, skipRefresh?: boolean) => void
  onGeneratingChange?: (isGenerating: boolean) => void  // 生成状态变化回调
}

// 将大纲转换为可编辑文本格式
function outlineToText(outline: Outline): string {
  let text = `标题：${outline.title || ''}\n\n`
  text += `概述：\n${outline.summary || ''}\n\n`
  if (outline.plot_points && outline.plot_points.length > 0) {
    text += `主要情节节点：\n`
    outline.plot_points.forEach((point, idx) => {
      // v0.6.1: 支持新的字典格式
      const eventText = typeof point === 'string' ? point : point.event
      text += `${idx + 1}. ${eventText}\n`
    })
  }
  return text
}

// 从文本格式解析大纲
function textToOutline(text: string): { title: string; summary: string; plot_points: { order: number; event: string }[] } {
  const result = { title: '', summary: '', plot_points: [] as { order: number; event: string }[] }

  // 解析标题
  const titleMatch = text.match(/标题[：:]\s*(.+?)(?:\n|$)/)
  if (titleMatch) {
    result.title = titleMatch[1].trim()
  }

  // 解析概述
  const summaryMatch = text.match(/概述[：:]\s*\n([\s\S]*?)(?=\n\s*主要情节节点[：:]|$)/)
  if (summaryMatch) {
    result.summary = summaryMatch[1].trim()
  }

  // 解析情节节点 - v0.6.1: 返回字典格式
  const plotMatch = text.match(/主要情节节点[：:]\s*\n([\s\S]*)$/)
  if (plotMatch) {
    const points = plotMatch[1]
      .split('\n')
      .map(line => line.replace(/^\d+\.\s*/, '').trim())
      .filter(line => line.length > 0)
    result.plot_points = points.map((event, idx) => ({
      order: idx + 1,
      event
    }))
  }

  return result
}

export default function OutlineWorkflow({
  projectId,
  outline,
  onOutlineUpdate,
  onStageChange,
  onGeneratingChange,
}: OutlineWorkflowProps) {
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  // Streaming state for outline
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  // Streaming state for chapter outlines
  const [isGeneratingChapters, setIsGeneratingChapters] = useState(false)
  const [chapterProgress, setChapterProgress] = useState({ current: 0, total: 0 })
  const [generatedChapters, setGeneratedChapters] = useState<ChapterOutline[]>([])

  // AbortController for stopping generation
  const abortControllerRef = useRef<AbortController | null>(null)

  // 通知父组件生成状态变化
  useEffect(() => {
    const isGenerating = isStreaming || isGeneratingChapters
    onGeneratingChange?.(isGenerating)
  }, [isStreaming, isGeneratingChapters, onGeneratingChange])

  // Sync edit content when outline changes
  useEffect(() => {
    if (!editing) {
      setEditContent(outlineToText(outline))
    }
  }, [outline, editing])

  const handleGenerateOutline = async () => {
    setLoading(true)
    setIsStreaming(true)
    setStreamingContent('')

    // 创建 AbortController 用于取消请求
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      await outlineApi.createStream(projectId, {
        onChunk: (chunk) => {
          setStreamingContent(prev => prev + chunk)
        },
        onDone: (result) => {
          const updatedOutline: Outline = {
            ...outline,
            title: result.outline.title || '',
            summary: result.outline.summary || '',
            plot_points: result.outline.plot_points || [],
            confirmed: false,
          }
          onOutlineUpdate(updatedOutline)
          onStageChange(result.stage, true)
          setIsStreaming(false)
        },
        onError: (error) => {
          setIsStreaming(false)
          toast.error(`生成大纲失败: ${error}`)
        },
      }, { signal: controller.signal })
    } catch (err) {
      setIsStreaming(false)
      toast.error('生成大纲失败，请检查 API Key 配置')
    } finally {
      setLoading(false)
      abortControllerRef.current = null
    }
  }

  const handleSaveEdit = async () => {
    setLoading(true)
    try {
      const parsed = textToOutline(editContent)
      const newOutline = await outlineApi.update(projectId, {
        title: parsed.title,
        summary: parsed.summary,
        plot_points: parsed.plot_points,
      })
      onOutlineUpdate(newOutline)
      setEditing(false)
    } catch (err) {
      toast.error('保存大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmOutline = async () => {
    setLoading(true)
    try {
      await outlineApi.confirm(projectId)
      onStageChange('chapter_outlines')
      const updatedOutline = await outlineApi.get(projectId)
      onOutlineUpdate(updatedOutline)
    } catch (err) {
      toast.error('确认大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateChapterOutlines = async () => {
    setIsGeneratingChapters(true)
    setChapterProgress({ current: 0, total: outline.chapter_count_suggested })
    setGeneratedChapters([])

    // 创建 AbortController 用于取消请求
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      await chapterOutlinesApi.createStream(projectId, {
        onProgress: (chapterNumber, total, chapter) => {
          setChapterProgress({ current: chapterNumber, total })
          // Add to generated chapters list
          setGeneratedChapters(prev => [...prev, chapter as ChapterOutline])
        },
        onDone: (_total, stage) => {
          setIsGeneratingChapters(false)
          onStageChange(stage)
        },
        onError: (error) => {
          setIsGeneratingChapters(false)
          toast.error(`生成章节大纲失败: ${error}`)
        },
      }, { signal: controller.signal })
    } catch (err) {
      setIsGeneratingChapters(false)
      toast.error('生成章节大纲失败，请检查 API Key 配置')
    } finally {
      abortControllerRef.current = null
    }
  }

  // Streaming view for outline generation
  if (isStreaming) {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">正在生成大纲...</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="min-h-[200px] max-h-[500px] overflow-y-auto bg-muted p-4 rounded-md font-mono text-sm whitespace-pre-wrap">
            {streamingContent || '等待生成...'}
          </div>
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
              <span className="text-sm text-muted-foreground">AI 正在创作大纲...</span>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => abortControllerRef.current?.abort()}
            >
              停止生成
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Streaming view for chapter outline generation
  if (isGeneratingChapters) {
    const progressPercent = chapterProgress.total > 0
      ? Math.round((chapterProgress.current / chapterProgress.total) * 100)
      : 0

    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">正在生成章节大纲...</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Progress bar */}
          <div className="mb-4">
            <div className="flex justify-between text-sm mb-1">
              <span>进度：{chapterProgress.current} / {chapterProgress.total} 章</span>
              <span>{progressPercent}%</span>
            </div>
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Generated chapters list */}
          {generatedChapters.length > 0 && (
            <div className="max-h-[300px] overflow-y-auto border rounded-md p-2">
              {generatedChapters.map((chapter) => (
                <div key={chapter.id} className="flex items-center gap-2 py-1 text-sm">
                  <span className="text-green-500">✓</span>
                  <span>第{chapter.chapter_number}章：{chapter.title || '生成中...'}</span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
              <span className="text-sm text-muted-foreground">
                正在生成第 {chapterProgress.current + 1} 章...
              </span>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => abortControllerRef.current?.abort()}
            >
              停止生成
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Stage: outline - show generate button
  if (!outline.title && !outline.summary) {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">大纲生成</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground mb-4">
            信息收集完成，可以开始生成小说大纲了。
          </p>
          <Button onClick={handleGenerateOutline} disabled={loading}>
            {loading ? '生成中...' : '生成大纲'}
          </Button>
        </CardContent>
      </Card>
    )
  }

  // Stage: outline - show outline for review/edit
  if (!outline.confirmed) {
    const canConfirm = outline.title && outline.summary

    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">大纲确认</CardTitle>
        </CardHeader>
        <CardContent>
          {editing ? (
            <div className="space-y-4">
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={20}
                className="font-mono text-sm"
              />
              <div className="flex gap-2">
                <Button onClick={handleSaveEdit} disabled={loading}>
                  {loading ? '保存中...' : '保存'}
                </Button>
                <Button variant="outline" onClick={() => setEditing(false)}>
                  取消
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="text-sm font-medium text-muted-foreground">标题</div>
                <div className="text-lg font-semibold">{outline.title || '（未生成）'}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">概述</div>
                <div className="whitespace-pre-wrap">{outline.summary || '-'}</div>
              </div>
              {outline.plot_points && outline.plot_points.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-muted-foreground">主要情节节点</div>
                  <ul className="list-disc list-inside text-sm mt-1">
                    {outline.plot_points.map((point, idx) => {
                      // v0.6.1: 支持新的字典格式
                      const eventText = typeof point === 'string' ? point : point.event
                      return <li key={idx} className="mb-1">{eventText}</li>
                    })}
                  </ul>
                </div>
              )}
              <div className="flex gap-2 pt-2">
                {canConfirm ? (
                  <>
                    <Button onClick={handleConfirmOutline} disabled={loading}>
                      {loading ? '确认中...' : '确认大纲'}
                    </Button>
                    <Button variant="outline" onClick={() => {
                      setEditContent(outlineToText(outline))
                      setEditing(true)
                    }}>
                      编辑
                    </Button>
                  </>
                ) : (
                  <>
                    <Button onClick={handleGenerateOutline} disabled={loading}>
                      {loading ? '生成中...' : '重新生成大纲'}
                    </Button>
                    <p className="text-sm text-muted-foreground self-center">
                      大纲信息不完整，请重新生成或手动编辑
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  // Stage: chapter_outlines
  return (
    <Card className="flex-1">
      <CardHeader>
        <CardTitle className="text-lg">生成章节大纲</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground mb-4">
          已设置 {outline.chapter_count_suggested} 章，可以开始生成章节大纲。
        </p>
        <p className="text-xs text-muted-foreground mb-4">
          每个章节将逐一生成，预计耗时较长，请耐心等待。
        </p>
        <Button onClick={handleGenerateChapterOutlines} disabled={loading}>
          {loading ? '生成中...' : '生成章节大纲'}
        </Button>
      </CardContent>
    </Card>
  )
}