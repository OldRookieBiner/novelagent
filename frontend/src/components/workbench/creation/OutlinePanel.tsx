// frontend/src/components/workbench/creation/OutlinePanel.tsx

import { useState, useEffect, useRef } from 'react'
import { FileText, Sparkles, Save, Plus, X, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { outlineApi } from '@/lib/api'
import { toast } from 'sonner'
import type { Outline } from '@/types'

interface OutlinePanelProps
{
  projectId: number
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
  const [generating, setGenerating] = useState(false)
  const [generatedContent, setGeneratedContent] = useState('')
  // SSE 流式请求控制器
  const abortControllerRef = useRef<AbortController | null>(null)

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

  // 组件卸载时取消进行中的 SSE 请求
  useEffect(() =>
  {
    return () =>
    {
      if (abortControllerRef.current)
      {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
    }
  }, [])

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

  // 保存大纲
  const handleSave = async () =>
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
  }

  // AI 生成大纲（SSE 流式）
  const handleGenerate = async () =>
  {
    setGenerating(true)
    setGeneratedContent('')
    // 创建 AbortController 用于取消请求
    const controller = new AbortController()
    abortControllerRef.current = controller
    try
    {
      await outlineApi.createStream(
        projectId,
        {
          onChunk: (chunk) =>
          {
            setGeneratedContent(prev => prev + chunk)
          },
          onDone: (result) =>
          {
            // 更新本地状态
            if (result.outline.title) setTitle(result.outline.title)
            if (result.outline.summary) setSummary(result.outline.summary)
            if (result.outline.plot_points)
            {
              setPlotPoints(result.outline.plot_points.map(p =>
                typeof p === 'string' ? p : p.event
              ))
            }
            setGenerating(false)
            abortControllerRef.current = null
            toast.success('AI 生成完成')
          },
          onError: (error) =>
          {
            setGenerating(false)
            abortControllerRef.current = null
            toast.error(`生成失败: ${error}`)
          }
        },
        { signal: controller.signal }
      )
    }
    catch (err)
    {
      setGenerating(false)
      abortControllerRef.current = null
      toast.error('生成失败')
    }
  }

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

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <FileText className="h-5 w-5" />
              小说大纲
            </h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleGenerate} disabled={generating}>
                <Sparkles className="h-4 w-4 mr-2" />
                {generating ? '生成中...' : 'AI 生成'}
              </Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <Save className="h-4 w-4 mr-2" />
                {saving ? '保存中...' : '保存'}
              </Button>
              {!outline?.confirmed && (
                <Button variant="default" size="sm" onClick={handleConfirm}>
                  <Check className="h-4 w-4 mr-2" />
                  确认大纲
                </Button>
              )}
            </div>
          </div>

          <Card>
            <CardContent className="pt-6 space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">小说标题</label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="输入小说标题"
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm text-muted-foreground">一句话简介</label>
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
                  className="mt-1"
                />
              </div>

              <div>
                <label className="text-sm text-muted-foreground">故事概述</label>
                <Textarea
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  placeholder="详细描述故事内容"
                  rows={6}
                  className="mt-1"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm text-muted-foreground">主要情节节点</label>
                  <Button variant="outline" size="sm" onClick={addPlotPoint}>
                    <Plus className="h-4 w-4 mr-1" />
                    添加
                  </Button>
                </div>
                <div className="space-y-2">
                  {plotPoints.map((point, index) => (
                    <div key={index} className="flex gap-2">
                      <span className="w-8 h-8 flex items-center justify-center bg-muted rounded text-sm">
                        {index + 1}
                      </span>
                      <Input
                        value={point}
                        onChange={(e) => updatePlotPoint(index, e.target.value)}
                        placeholder="描述情节节点"
                        className="flex-1"
                      />
                      <Button variant="ghost" size="sm" onClick={() => removePlotPoint(index)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm text-muted-foreground">章节数量建议（仅供参考）</label>
                <Input
                  type="number"
                  value={chapterCount}
                  readOnly
                  className="mt-1 w-32 bg-muted"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 右侧 AI 助手 */}
      <div className="w-80 border-l bg-white p-4 overflow-auto">
        <h3 className="font-medium mb-4 flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          AI 建议
        </h3>
        {/* AI 生成内容展示区 */}
        {generating && generatedContent && (
          <div className="mb-4 p-3 bg-blue-50 rounded-md text-sm whitespace-pre-wrap">
            <p className="font-medium text-blue-700">生成中...</p>
            <p className="text-blue-600 mt-1">{generatedContent}</p>
          </div>
        )}
        <div className="space-y-3">
          {/* TODO: 替换为 AI 生成的动态建议 */}
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">情节建议</p>
            <p className="text-muted-foreground text-xs mt-1">可以在第3章加入转折</p>
          </div>
          <div className="p-3 bg-muted rounded-md text-sm">
            <p className="font-medium">角色发展</p>
            <p className="text-muted-foreground text-xs mt-1">主角的动机可以更明确</p>
          </div>
        </div>
        {/* 已确认状态提示 */}
        {outline?.confirmed && (
          <div className="mt-4 p-3 bg-green-50 rounded-md text-sm">
            <p className="font-medium text-green-700">大纲已确认</p>
            <p className="text-green-600 text-xs mt-1">可以进入下一阶段</p>
          </div>
        )}
      </div>
    </div>
  )
}
