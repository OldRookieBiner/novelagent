// frontend/src/components/project/OutlineWorkflow.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { outlineApi, chapterOutlinesApi } from '@/lib/api'
import type { Outline } from '@/types'

interface OutlineWorkflowProps {
  projectId: number
  outline: Outline
  onOutlineUpdate: (outline: Outline) => void
  onStageChange: (stage: string) => void
}

export default function OutlineWorkflow({
  projectId,
  outline,
  onOutlineUpdate,
  onStageChange,
}: OutlineWorkflowProps) {
  const [loading, setLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(outline.title || '')
  const [editSummary, setEditSummary] = useState(outline.summary || '')
  const [chapterCount, setChapterCount] = useState(outline.chapter_count_suggested || 10)

  const handleGenerateOutline = async () => {
    setLoading(true)
    try {
      const newOutline = await outlineApi.create(projectId)
      onOutlineUpdate(newOutline)
      onStageChange('outline_confirming')
    } catch (err) {
      alert('生成大纲失败，请检查 API Key 配置')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveEdit = async () => {
    setLoading(true)
    try {
      const newOutline = await outlineApi.update(projectId, {
        title: editTitle,
        summary: editSummary,
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
      onStageChange('chapter_count_suggesting')
      // Update outline state
      const updatedOutline = await outlineApi.get(projectId)
      onOutlineUpdate(updatedOutline)
    } catch (err) {
      alert('确认大纲失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSetChapterCount = async () => {
    setLoading(true)
    try {
      await outlineApi.setChapterCount(projectId, { chapter_count: chapterCount })
      onStageChange('chapter_outlines_generating')
      // Update outline state
      const updatedOutline = await outlineApi.get(projectId)
      onOutlineUpdate(updatedOutline)
    } catch (err) {
      alert('设置章节数失败')
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
    // If title is empty, allow regeneration
    const canConfirm = outline.title && outline.summary

    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">大纲确认</CardTitle>
        </CardHeader>
        <CardContent>
          {editing ? (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">标题</label>
                <Input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">概述</label>
                <Textarea
                  value={editSummary}
                  onChange={(e) => setEditSummary(e.target.value)}
                  rows={4}
                />
              </div>
              {outline.plot_points && outline.plot_points.length > 0 && (
                <div>
                  <label className="text-sm font-medium">主要情节节点</label>
                  <ul className="list-disc list-inside text-sm">
                    {outline.plot_points.map((point, idx) => (
                      <li key={idx}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}
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
                <div>{outline.summary || '-'}</div>
              </div>
              {outline.plot_points && outline.plot_points.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-muted-foreground">主要情节节点</div>
                  <ul className="list-disc list-inside text-sm">
                    {outline.plot_points.map((point, idx) => (
                      <li key={idx}>{point}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex gap-2">
                {canConfirm ? (
                  <>
                    <Button onClick={handleConfirmOutline} disabled={loading}>
                      {loading ? '确认中...' : '确认大纲'}
                    </Button>
                    <Button variant="outline" onClick={() => setEditing(true)}>
                      编辑
                    </Button>
                  </>
                ) : (
                  <>
                    <Button onClick={handleGenerateOutline} disabled={loading}>
                      {loading ? '生成中...' : '重新生成大纲'}
                    </Button>
                    <p className="text-sm text-muted-foreground self-center">
                      标题为空，请重新生成或手动编辑
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

  // Stage: chapter_count_suggesting - set chapter count
  if (!outline.chapter_count_confirmed) {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="text-lg">设置章节数</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground mb-4">
            请设置小说的章节数量。建议: {outline.chapter_count_suggested} 章
          </p>
          <div className="flex items-center gap-4">
            <Input
              type="number"
              min={1}
              max={100}
              value={chapterCount}
              onChange={(e) => setChapterCount(parseInt(e.target.value) || 10)}
              className="w-20"
            />
            <span>章</span>
          </div>
          <Button className="mt-4" onClick={handleSetChapterCount} disabled={loading}>
            {loading ? '设置中...' : '确认章节数'}
          </Button>
        </CardContent>
      </Card>
    )
  }

  // Stage: chapter_outlines_generating - generate chapter outlines
  return (
    <Card className="flex-1">
      <CardHeader>
        <CardTitle className="text-lg">生成章节大纲</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground mb-4">
          已设置 {chapterCount} 章，可以开始生成章节大纲。
        </p>
        <Button onClick={handleGenerateChapterOutlines} disabled={loading}>
          {loading ? '生成中...' : '生成章节大纲'}
        </Button>
      </CardContent>
    </Card>
  )
}