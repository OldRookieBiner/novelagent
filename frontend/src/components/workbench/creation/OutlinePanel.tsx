// frontend/src/components/workbench/creation/OutlinePanel.tsx

import { useState, useEffect, useCallback } from 'react'
import { FileText, Save, Plus, X, Check } from 'lucide-react'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { outlineApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
import type { Outline } from '@/types'

interface OutlinePanelProps
{
  projectId: number
}

// 可拖拽排序的情节节点组件
function SortablePlotPoint({ id, index, value, onChange, onRemove }: {
  id: string
  index: number
  value: string
  onChange: (v: string) => void
  onRemove: () => void
})
{
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div ref={setNodeRef} style={style} className="flex gap-2 items-center">
      {/* 拖拽手柄 */}
      <button {...attributes} {...listeners} className="cursor-grab text-muted-foreground hover:text-foreground">
        <span className="text-sm select-none">⠿</span>
      </button>
      {/* 序号 */}
      <span className="w-7 h-7 flex items-center justify-center bg-muted rounded text-xs text-muted-foreground shrink-0">
        {index + 1}
      </span>
      {/* 输入框 */}
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder="描述情节节点" className="flex-1" />
      {/* 删除按钮 */}
      <Button variant="ghost" size="sm" onClick={onRemove} className="shrink-0">
        <X className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

export function OutlinePanel({ projectId }: OutlinePanelProps)
{
  const [outline, setOutline] = useState<Outline | null>(null)
  const [loading, setLoading] = useState(true)
  const [plotPoints, setPlotPoints] = useState<string[]>([])
  // 本地编辑状态
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [chapterCount, setChapterCount] = useState(10)
  // 操作状态
  const [saving, setSaving] = useState(false)
  // AI 更新标记
  const aiUpdateMarkers = useWorkbenchStore((s) => s.aiUpdateMarkers)
  const outlineUpdated = !!aiUpdateMarkers.outline

  // 拖拽传感器，设置 5px 激活距离避免误触
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  useEffect(() =>
  {
    const fetchOutline = async () =>
    {
      try
      {
        const data = await outlineApi.get(projectId)
        setOutline(data)
        setPlotPoints(data.plot_points?.map(p => typeof p === 'string' ? p : p.event) || [])
        // 初始化本地编辑状态
        setTitle(data.title || '')
        setSummary(data.summary || '')
        setChapterCount(data.chapter_count_suggested || 10)
      }
      catch (err)
      {
        console.error('Failed to fetch outline:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchOutline()
  }, [projectId])

  const addPlotPoint = () =>
  {
    setPlotPoints([...plotPoints, ''])
  }

  const removePlotPoint = (index: number) =>
  {
    setPlotPoints(plotPoints.filter((_, i) => i !== index))
  }

  const updatePlotPoint = (index: number, value: string) =>
  {
    const updated = [...plotPoints]
    updated[index] = value
    setPlotPoints(updated)
  }

  // 拖拽排序结束回调
  const handleDragEnd = (event: { active: { id: string | number }; over: { id: string | number } | null }) =>
  {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = parseInt(String(active.id).replace('plot-', ''))
    const newIndex = parseInt(String(over.id).replace('plot-', ''))
    const updated = [...plotPoints]
    const [moved] = updated.splice(oldIndex, 1)
    updated.splice(newIndex, 0, moved)
    setPlotPoints(updated)
  }

  // 保存大纲
  const handleSave = useCallback(async () =>
  {
    if (!outline) return
    setSaving(true)
    try
    {
      const updated = await outlineApi.update(projectId, {
        title,
        summary,
        plot_points: plotPoints.filter(p => p.trim()).map((event, index) => ({
          order: index + 1,
          event
        }))
      })
      setOutline(updated)
      toast.success('保存成功')
    }
    catch (err)
    {
      console.error('Failed to save outline:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSaving(false)
    }
  }, [outline, title, summary, plotPoints, chapterCount, projectId])

  // 确认大纲
  const handleConfirm = async () =>
  {
    if (!outline) return
    if (!title || !summary)
    {
      toast.error('请先填写标题和简介')
      return
    }
    try
    {
      await outlineApi.confirm(projectId)
      toast.success('大纲已确认')
      // 更新本地状态
      setOutline({ ...outline, confirmed: true })
    }
    catch (err)
    {
      console.error('Failed to confirm outline:', err)
      toast.error('确认失败')
    }
  }

  // Ctrl+S 快捷键
  useEffect(() =>
  {
    const handleKeyDown = (e: KeyboardEvent) =>
    {
      if ((e.metaKey || e.ctrlKey) && e.key === 's')
      {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full flex-col md:flex-row">
      {/* 左栏：基本信息 */}
      <div className="flex-1 min-w-0 p-6 overflow-auto md:border-r">
        <div className="max-w-2xl mx-auto space-y-5">
          {/* 标题栏 */}
          <div className="flex items-center justify-between pb-3 border-b">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <FileText className="h-5 w-5" />
                小说大纲
              </h2>
              {outline?.confirmed && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 border border-green-200">
                  已确认
                </span>
              )}
              {outlineUpdated && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200 animate-pulse">
                  🤖 AI 已更新
                </span>
              )}
            </div>
            <div className="flex gap-2 items-center">
              <Button size="sm" onClick={handleSave} disabled={saving} title="Ctrl+S">
                <Save className="h-4 w-4 mr-1.5" />
                {saving ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>

          {/* 基本信息卡片 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <span className="text-indigo-500">📋</span> 基本信息
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <label className="text-xs text-muted-foreground mb-1.5 block">标题</label>
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="输入小说标题"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">建议章节数</label>
                  <Input
                    type="number"
                    value={chapterCount}
                    onChange={(e) => setChapterCount(parseInt(e.target.value) || 10)}
                    className="bg-muted"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 内容概述卡片 */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <span className="text-amber-500">📝</span> 内容概述
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">一句话简介</label>
                <Input
                  value={summary.split('\n')[0] || ''}
                  onChange={(e) =>
                  {
                    // 更新第一行，保留其他内容
                    const lines = summary.split('\n')
                    lines[0] = e.target.value
                    setSummary(lines.join('\n'))
                  }}
                  placeholder="用一句话概括故事"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">故事概述</label>
                <Textarea
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="详细描述故事内容"
                  rows={5}
                />
              </div>
            </CardContent>
          </Card>

          {/* 确认按钮 */}
          {!outline?.confirmed && (
            <div className="text-center pt-2">
              <Button size="sm" onClick={handleConfirm} className="px-8">
                <Check className="h-4 w-4 mr-1.5" />
                确认大纲
              </Button>
              <p className="text-xs text-muted-foreground mt-2">确认后将进入章节大纲生成阶段</p>
            </div>
          )}
        </div>
      </div>

      {/* 右栏：情节节点（拖拽排序） */}
      <div className="flex-1 min-w-0 p-6 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <span className="text-emerald-500">📍</span> 情节节点 ({plotPoints.length})
          </h3>
          <Button variant="outline" size="sm" onClick={addPlotPoint}>
            <Plus className="h-3.5 w-3.5 mr-1" /> 添加
          </Button>
        </div>

        {plotPoints.length === 0 ? (
          /* 空状态提示 */
          <div className="text-center py-12 text-muted-foreground">
            <p className="text-sm">暂无情节节点</p>
            <p className="text-xs mt-1">点击「添加」或在 AI 搭档中描述你的故事</p>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={plotPoints.map((_, i) => `plot-${i}`)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {plotPoints.map((point, index) => (
                  <SortablePlotPoint
                    key={`plot-${index}`}
                    id={`plot-${index}`}
                    index={index}
                    value={point}
                    onChange={(v) => updatePlotPoint(index, v)}
                    onRemove={() => removePlotPoint(index)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}
