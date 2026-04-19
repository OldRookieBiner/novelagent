// frontend/src/components/project/OutlineWorkflow.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { outlineApi, chapterOutlinesApi } from '@/lib/api'
import type { Outline } from '@/types'

interface OutlineWorkflowProps {
  projectId: number
  outline: Outline
  onOutlineUpdate: (outline: Outline) => void
  onStageChange: (stage: string, skipRefresh?: boolean) => void
}

// 将大纲转换为可编辑文本格式
function outlineToText(outline: Outline): string {
  let text = `标题：${outline.title || ''}\n\n`
  text += `概述：\n${outline.summary || ''}\n\n`
  if (outline.plot_points && outline.plot_points.length > 0) {
    text += `主要情节节点：\n`
    outline.plot_points.forEach((point, idx) => {
      text += `${idx + 1}. ${point}\n`
    })
  }
  return text
}

// 从文本格式解析大纲
function textToOutline(text: string): { title: string; summary: string; plot_points: string[] } {
  const result = { title: '', summary: '', plot_points: [] as string[] }

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

  // 解析情节节点
  const plotMatch = text.match(/主要情节节点[：:]\s*\n([\s\S]*)$/)
  if (plotMatch) {
    const points = plotMatch[1]
      .split('\n')
      .map(line => line.replace(/^\d+\.\s*/, '').trim())
      .filter(line => line.length > 0)
    result.plot_points = points
  }

  return result
}

export default function OutlineWorkflow({
  projectId,
  outline,
  onOutlineUpdate,
  onStageChange,
}: OutlineWorkflowProps) {
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  // Streaming state
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

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
          alert(`生成大纲失败: ${error}`)
        },
      })
    } catch (err) {
      setIsStreaming(false)
      alert('生成大纲失败，请检查 API Key 配置')
    } finally {
      setLoading(false)
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
      alert('保存大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmOutline = async () => {
    setLoading(true)
    try {
      await outlineApi.confirm(projectId)
      onStageChange('chapter_outlines_generating')
      const updatedOutline = await outlineApi.get(projectId)
      onOutlineUpdate(updatedOutline)
    } catch (err) {
      alert('确认大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateChapterOutlines = async () => {
    setLoading(true)
    try {
      await chapterOutlinesApi.create(projectId)
      onStageChange('chapter_outlines_confirming')
    } catch (err) {
      alert('生成章节大纲失败，请检查 API Key 配置')
    } finally {
      setLoading(false)
    }
  }

  // Streaming view
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
          <div className="mt-4 flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            <span className="text-sm text-muted-foreground">AI 正在创作大纲...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Stage: outline_generating - show generate button
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

  // Stage: outline_confirming - show outline for review/edit
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
                    {outline.plot_points.map((point, idx) => (
                      <li key={idx} className="mb-1">{point}</li>
                    ))}
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

  // Stage: chapter_outlines_generating
  return (
    <Card className="flex-1">
      <CardHeader>
        <CardTitle className="text-lg">生成章节大纲</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground mb-4">
          已设置 {outline.chapter_count_suggested} 章，可以开始生成章节大纲。
        </p>
        <Button onClick={handleGenerateChapterOutlines} disabled={loading}>
          {loading ? '生成中...' : '生成章节大纲'}
        </Button>
      </CardContent>
    </Card>
  )
}