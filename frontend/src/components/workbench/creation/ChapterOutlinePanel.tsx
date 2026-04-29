// frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx

import { useState, useEffect, useRef } from 'react'
import { Save, Sparkles, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { chapterOutlinesApi } from '@/lib/api'
import { toast } from 'sonner'
import type { ChapterOutline } from '@/types'

interface ChapterOutlinePanelProps
{
  projectId: number
}

export function ChapterOutlinePanel({ projectId }: ChapterOutlinePanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)

  // 编辑状态
  const [editingTitle, setEditingTitle] = useState('')
  const [editingScene, setEditingScene] = useState('')
  const [editingPlot, setEditingPlot] = useState('')
  const [editingTargetWords, setEditingTargetWords] = useState(3000)

  // 操作状态
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null)

  // SSE 流式请求控制器
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

  // 选中章节变化时初始化编辑状态
  useEffect(() =>
  {
    if (selectedChapter)
    {
      setEditingTitle(selectedChapter.title || '')
      setEditingScene(selectedChapter.scene || '')
      setEditingPlot(selectedChapter.plot || '')
      setEditingTargetWords(selectedChapter.target_words || 3000)
    }
  }, [selectedChapter])

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

  // 保存章节大纲
  const handleSave = async () =>
  {
    if (!selectedChapter) return
    setSaving(true)
    try
    {
      const updated = await chapterOutlinesApi.update(
        projectId,
        selectedChapter.chapter_number,
        {
          title: editingTitle,
          scene: editingScene,
          plot: editingPlot,
          target_words: editingTargetWords
        }
      )
      // 更新列表中的章节
      setChapters(chapters.map(c =>
        c.id === updated.id ? updated : c
      ))
      // 更新选中章节
      setSelectedChapter(updated)
      toast.success('保存成功')
    }
    catch (err)
    {
      console.error('Failed to save chapter outline:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSaving(false)
    }
  }

  // 确认章节大纲
  const handleConfirm = async () =>
  {
    if (!selectedChapter) return
    try
    {
      await chapterOutlinesApi.confirm(projectId, selectedChapter.chapter_number)
      // 更新章节状态
      const updatedChapter = { ...selectedChapter, confirmed: true }
      setChapters(chapters.map(c =>
        c.id === selectedChapter.id ? updatedChapter : c
      ))
      setSelectedChapter(updatedChapter)
      toast.success('章节已确认')
    }
    catch (err)
    {
      console.error('Failed to confirm chapter:', err)
      toast.error('确认失败')
    }
  }

  // 批量生成章节大纲（SSE 流式）
  const handleGenerateAll = async () =>
  {
    setGenerating(true)
    setProgress(null)
    // 创建 AbortController 用于取消请求
    const controller = new AbortController()
    abortControllerRef.current = controller
    try
    {
      await chapterOutlinesApi.createStream(
        projectId,
        {
          onProgress: (chapterNumber, total, chapter) =>
          {
            setProgress({ current: chapterNumber, total })
            // 添加新章节到列表
            setChapters(prev =>
            {
              const exists = prev.find(c => c.id === chapter.id)
              if (exists) return prev
              return [...prev, {
                id: chapter.id,
                project_id: projectId,
                chapter_number: chapter.chapter_number,
                title: chapter.title,
                scene: '',
                plot: '',
                target_words: 3000,
                confirmed: false,
                created_at: new Date().toISOString(),
                has_content: false
              } as ChapterOutline]
            })
          },
          onDone: (total) =>
          {
            setGenerating(false)
            setProgress(null)
            abortControllerRef.current = null
            toast.success(`已生成 ${total} 个章节大纲`)
          },
          onError: (error) =>
          {
            setGenerating(false)
            setProgress(null)
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
      setProgress(null)
      abortControllerRef.current = null
      toast.error('生成失败')
    }
  }

  // 取消生成
  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setGenerating(false)
      setProgress(null)
      toast.info('已取消生成')
    }
  }

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className="w-44 border-r bg-white">
        <div className="p-3 border-b flex items-center justify-between">
          <span className="text-sm font-medium">章节列表</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={generating ? handleCancelGenerate : handleGenerateAll}
            disabled={generating && !abortControllerRef.current}
            title={generating ? '取消生成' : '生成全部章节大纲'}
          >
            {generating ? <X className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
          </Button>
        </div>
        {/* 生成进度 */}
        {progress && (
          <div className="px-3 py-2 bg-blue-50 text-xs text-blue-700">
            生成中: {progress.current}/{progress.total}
          </div>
        )}
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
                {chapter.confirmed && (
                  <Check className="h-3 w-3 text-green-500 flex-shrink-0" />
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 中间编辑区 */}
      <div className="flex-1 p-6 overflow-auto">
        {selectedChapter ? (
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">第 {selectedChapter.chapter_number} 章</h2>
              <div className="flex gap-2">
                {!selectedChapter.confirmed && (
                  <Button variant="outline" size="sm" onClick={handleConfirm}>
                    <Check className="h-4 w-4 mr-2" />
                    确认
                  </Button>
                )}
                <Button size="sm" onClick={handleSave} disabled={saving}>
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? '保存中...' : '保存'}
                </Button>
              </div>
            </div>

            <div>
              <label className="text-sm text-muted-foreground">章节标题</label>
              <Input
                value={editingTitle}
                onChange={(e) => setEditingTitle(e.target.value)}
                placeholder="输入章节标题"
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground">场景设定</label>
              <Textarea
                value={editingScene}
                onChange={(e) => setEditingScene(e.target.value)}
                placeholder="描述本章场景"
                rows={2}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground">情节概要</label>
              <Textarea
                value={editingPlot}
                onChange={(e) => setEditingPlot(e.target.value)}
                placeholder="描述本章主要情节"
                rows={4}
                className="mt-1"
              />
            </div>

            <div>
              <label className="text-sm text-muted-foreground">目标字数</label>
              <Input
                type="number"
                value={editingTargetWords}
                onChange={(e) => setEditingTargetWords(parseInt(e.target.value) || 3000)}
                className="mt-1 w-32"
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
            <p>选择章节查看大纲</p>
            {chapters.length === 0 && (
              <Button onClick={handleGenerateAll} disabled={generating}>
                <Sparkles className="h-4 w-4 mr-2" />
                {generating ? '生成中...' : '生成章节大纲'}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* 右侧详情面板 */}
      <div className="w-80 border-l bg-white p-4">
        <h3 className="font-medium mb-4">章节详情</h3>
        {selectedChapter ? (
          <div className="space-y-4">
            <Card>
              <CardContent className="pt-4">
                <div className="text-sm">
                  <span className="text-muted-foreground">状态: </span>
                  <span className={selectedChapter.confirmed ? 'text-green-600' : 'text-yellow-600'}>
                    {selectedChapter.confirmed ? '已确认' : '草稿'}
                  </span>
                </div>
              </CardContent>
            </Card>
            {/* 已确认提示 */}
            {selectedChapter.confirmed && (
              <div className="p-3 bg-green-50 rounded-md text-sm">
                <p className="font-medium text-green-700">章节已确认</p>
                <p className="text-green-600 text-xs mt-1">可以进行章节写作</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">选择章节查看详情</p>
        )}
      </div>
    </div>
  )
}
