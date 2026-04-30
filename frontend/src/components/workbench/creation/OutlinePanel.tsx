// frontend/src/components/workbench/creation/OutlinePanel.tsx

import { useState, useEffect, useRef, useCallback } from 'react'
import { FileText, Sparkles, Save, Plus, X, Check, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  // SSE 流式请求控制器
  const abortControllerRef = useRef<AbortController | null>(null)
  // AI 分析面板状态
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<{ type: string; content: string }[] | null>(null)

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

  // AI 生成大纲（SSE 流式）
  const handleGenerate = async () =>
  {
    setGenerating(true)
    // 创建 AbortController 用于取消请求
    const controller = new AbortController()
    abortControllerRef.current = controller
    try
    {
      await outlineApi.createStream(
        projectId,
        {
          onChunk: () => {},
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
            if (result.outline.chapter_count_suggested) setChapterCount(result.outline.chapter_count_suggested)
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

  // AI 分析大纲
  const handleAnalyze = async () =>
  {
    if (!outline) return
    setAnalyzing(true)
    setAnalysisResult(null)
    // TODO: 后端 AI 分析 API 就绪后替换为实际 SSE 调用
    setTimeout(() =>
    {
      setAnalysisResult([
        { type: '情节建议', content: '可以在中间加入反派视角的故事线，增加张力和层次感。建议在第5章左右引入反派背景。' },
        { type: '角色发展', content: '主角的成长弧线需要更明显，当前情节转变过快，建议第3-4章增加内心挣扎描写。' },
        { type: '世界观', content: '修仙大陆的世界观设定较完整，可以加入不同势力的政治博弈增加深度。' },
      ])
      setAnalyzing(false)
    }, 2000)
  }

  // 采纳 AI 分析建议
  const acceptAnalysis = (suggestion: { type: string; content: string }) =>
  {
    setSummary(prev => prev + '\n\n[AI建议 — ' + suggestion.type + '] ' + suggestion.content)
    setAnalysisResult(prev => prev?.filter(s => s !== suggestion) || null)
    toast.success('建议已采纳，已追加到概述中')
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
    <div className="flex h-full">
      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-3xl mx-auto space-y-5">
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
            </div>
            <div className="flex gap-2 items-center">
              <Button variant="outline" size="sm" onClick={handleGenerate} disabled={generating}>
                <Sparkles className="h-4 w-4 mr-1.5" />
                {generating ? '生成中...' : 'AI 生成'}
              </Button>
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

          {/* 情节节点卡片 */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <span className="text-emerald-500">📍</span> 情节节点 ({plotPoints.length})
                </CardTitle>
                <Button variant="outline" size="sm" onClick={addPlotPoint}>
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  添加
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {plotPoints.map((point, index) => (
                <div key={index} className="flex gap-2 items-center">
                  <span className="w-7 h-7 flex items-center justify-center bg-muted rounded text-xs text-muted-foreground flex-shrink-0">
                    {index + 1}
                  </span>
                  <Input
                    value={point}
                    onChange={(e) => updatePlotPoint(index, e.target.value)}
                    placeholder="描述情节节点"
                    className="flex-1"
                  />
                  <Button variant="ghost" size="sm" onClick={() => removePlotPoint(index)} className="flex-shrink-0">
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
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

      {/* 右侧 AI 分析区 */}
      <div className="w-[240px] border-l bg-white flex flex-col">
        <button
          onClick={() => setAiPanelCollapsed(!aiPanelCollapsed)}
          className="flex items-center justify-between px-3 py-2.5 border-b hover:bg-muted/50 transition-colors"
        >
          <span className="text-xs font-medium flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            AI 分析
          </span>
          {aiPanelCollapsed ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
        </button>

        {!aiPanelCollapsed && (
          <div className="flex-1 overflow-auto p-3 space-y-3">
            {analysisResult ? (
              <>
                <div className="p-2 bg-green-50 rounded border border-green-200 text-center">
                  <div className="text-xs text-green-700 font-medium">✅ 分析完成</div>
                  <button
                    onClick={() => { setAnalysisResult(null); handleAnalyze() }}
                    className="text-[10px] text-muted-foreground hover:text-foreground mt-1"
                  >
                    🔄 重新分析
                  </button>
                </div>
                {analysisResult.map((s, i) => (
                  <div key={i} className="p-2.5 bg-white border rounded-md">
                    <div className="text-[11px] font-medium mb-1">{s.type}</div>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">{s.content}</p>
                    <div className="flex gap-1.5 mt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 text-[10px] px-2"
                        onClick={() => acceptAnalysis(s)}
                      >
                        采纳
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] px-2"
                        onClick={() => setAnalysisResult(prev => prev?.filter(x => x !== s) || null)}
                      >
                        忽略
                      </Button>
                    </div>
                  </div>
                ))}
              </>
            ) : analyzing ? (
              <div className="p-3 bg-blue-50 rounded border border-blue-200 text-center space-y-2">
                <Loader2 className="h-5 w-5 animate-spin text-blue-500 mx-auto" />
                <div className="text-[11px] text-blue-700 font-medium">AI 正在分析...</div>
                <div className="h-1.5 bg-blue-200 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full animate-pulse w-2/3" />
                </div>
                <button
                  onClick={() => setAnalyzing(false)}
                  className="text-[10px] text-muted-foreground hover:text-foreground"
                >
                  取消
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
                <div className="text-2xl">🔍</div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  大纲编辑完成后，<br />点击下方按钮让 AI<br />分析大纲并提供建议
                </p>
                <Button size="sm" onClick={handleAnalyze} className="text-xs">
                  <Sparkles className="h-3 w-3 mr-1" />
                  AI 分析大纲
                </Button>
                <p className="text-[10px] text-muted-foreground">分析情节/角色/世界观等</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}