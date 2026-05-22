// frontend/src/components/workbench/creation/ChapterOutlineEditor.tsx

import { Save, Check, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { ChapterOutline } from '@/types'

interface ChapterOutlineEditorProps
{
  /** 当前选中的章节 */
  selectedChapter: ChapterOutline | null
  /** 编辑中的标题 */
  editingTitle: string
  /** 编辑中的场景 */
  editingScene: string
  /** 编辑中的情节 */
  editingPlot: string
  /** 编辑中的目标字数 */
  editingTargetWords: number
  /** 是否保存中 */
  saving: boolean
  /** 章节列表（用于空状态判断） */
  chaptersLength: number
  /** 是否正在生成 */
  generating: boolean
  /** 标题变更回调 */
  onTitleChange: (value: string) => void
  /** 场景变更回调 */
  onSceneChange: (value: string) => void
  /** 情节变更回调 */
  onPlotChange: (value: string) => void
  /** 目标字数变更回调 */
  onTargetWordsChange: (value: number) => void
  /** 确认回调 */
  onConfirm: () => void
  /** 保存回调 */
  onSave: () => void
  /** 生成回调（空状态用） */
  onGenerate: () => void
}

/**
 * 章节大纲编辑器 — 中间编辑区
 * 显示选中章节的标题、场景、情节、目标字数编辑表单
 */
export function ChapterOutlineEditor(props: ChapterOutlineEditorProps)
{
  const {
    selectedChapter,
    editingTitle,
    editingScene,
    editingPlot,
    editingTargetWords,
    saving,
    chaptersLength,
    generating,
    onTitleChange,
    onSceneChange,
    onPlotChange,
    onTargetWordsChange,
    onConfirm,
    onSave,
    onGenerate,
  } = props

  // 无选中章节 — 空状态
  if (!selectedChapter)
  {
    return (
      <div className="flex-1 p-6 overflow-auto">
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
          <Sparkles className="h-8 w-8 text-muted-foreground/40" />
          {chaptersLength === 0 ? (
            <>
              <p>请先生成小说大纲，再生成章节大纲</p>
              <Button onClick={onGenerate} disabled={generating}>
                <Sparkles className="h-4 w-4 mr-1.5" />
                {generating ? '生成中...' : '生成章节大纲'}
              </Button>
            </>
          ) : (
            <p>选择章节查看大纲</p>
          )}
        </div>
      </div>
    )
  }

  // 编辑表单
  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-2xl mx-auto space-y-4">
        {/* 标题栏与操作 */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">第 {selectedChapter.chapter_number} 章</h2>
          <div className="flex gap-2">
            {!selectedChapter.confirmed && (
              <Button variant="outline" size="sm" onClick={onConfirm}>
                <Check className="h-4 w-4 mr-1.5" />
                确认
              </Button>
            )}
            <Button size="sm" onClick={onSave} disabled={saving} title="Ctrl+S">
              <Save className="h-4 w-4 mr-1.5" />
              {saving ? '保存中...' : '保存'}
            </Button>
          </div>
        </div>

        {/* 章节标题 */}
        <div>
          <label className="text-xs text-muted-foreground mb-1.5 block">章节标题</label>
          <Input
            value={editingTitle}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="输入章节标题"
          />
        </div>

        {/* 场景设定 */}
        <div>
          <label className="text-xs text-muted-foreground mb-1.5 block">场景设定</label>
          <Textarea
            value={editingScene}
            onChange={(e) => onSceneChange(e.target.value)}
            placeholder="描述本章场景"
            rows={2}
          />
        </div>

        {/* 情节概要 */}
        <div>
          <label className="text-xs text-muted-foreground mb-1.5 block">情节概要</label>
          <Textarea
            value={editingPlot}
            onChange={(e) => onPlotChange(e.target.value)}
            placeholder="描述本章主要情节"
            rows={4}
          />
        </div>

        {/* 目标字数 */}
        <div>
          <label className="text-xs text-muted-foreground mb-1.5 block">目标字数</label>
          <Input
            type="number"
            value={editingTargetWords}
            onChange={(e) => onTargetWordsChange(parseInt(e.target.value) || 3000)}
            className="w-32"
          />
        </div>
      </div>
    </div>
  )
}
