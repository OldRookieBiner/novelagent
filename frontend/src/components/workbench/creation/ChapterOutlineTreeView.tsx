// frontend/src/components/workbench/creation/ChapterOutlineTreeView.tsx

import { Sparkles, X, RotateCcw, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ArcOutlineSection, type ArcOutline } from './ArcOutlineSection'
import type { ChapterOutline } from '@/types'

/** 章节大纲生成进度 */
interface ChapterOutlineProgress
{
  current: number
  total: number
  currentTitle: string
  completed: string[]
}

interface ChapterOutlineTreeViewProps
{
  /** 弧线列表（含章节） */
  arcs: ArcOutline[]
  /** 选中章节 ID */
  selectedChapterId: number | null
  /** 选中章节回调 */
  onSelectChapter: (chapter: ChapterOutline) => void
  /** 是否正在生成 */
  generating: boolean
  /** 是否正在重新规划 */
  replaning: boolean
  /** 生成进度 */
  progress: ChapterOutlineProgress | null
  /** 批量生成回调 */
  onGenerate: () => void
  /** 取消生成回调 */
  onCancelGenerate: () => void
  /** 重新规划回调 */
  onReplan: () => void
  /** 未确认章节数 */
  unconfirmedCount: number
  /** 一键确认回调 */
  onConfirmAll: () => void
}

/**
 * 章节大纲树形视图 — 长篇小说用
 * 按弧线分组显示章节，当前为占位组件
 */
export function ChapterOutlineTreeView(props: ChapterOutlineTreeViewProps)
{
  const {
    arcs,
    selectedChapterId,
    onSelectChapter,
    generating,
    replaning,
    progress,
    onGenerate,
    onCancelGenerate,
    onReplan,
    unconfirmedCount,
    onConfirmAll,
  } = props

  // 总章节数
  const totalChapters = arcs.reduce((sum, arc) => sum + arc.chapters.length, 0)

  return (
    <div className="w-56 border-r bg-white flex flex-col">
      {/* 标题栏与操作按钮 */}
      <div className="p-2.5 border-b flex items-center justify-between">
        <span className="text-xs font-medium">章节 ({totalChapters})</span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={generating || replaning ? onCancelGenerate : onGenerate}
            disabled={replaning}
            title={generating ? '取消生成' : '批量生成所有章节大纲'}
          >
            {generating ? <X className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
          </Button>
          {totalChapters > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={onReplan}
              disabled={generating || replaning}
              title="重新生成章节大纲"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* 生成进度条 */}
      {progress && (
        <div className="px-2 py-2 bg-blue-50 border-b">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-blue-700 font-medium">
              ⏳ {progress.currentTitle}
            </span>
            <span className="text-[10px] text-blue-600">{progress.current}/{progress.total}</span>
          </div>
          <div className="h-1.5 bg-blue-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* 按弧线分组的章节列表 */}
      <div className="flex-1 overflow-auto">
        {arcs.map((arc) => (
          <ArcOutlineSection
            key={arc.id}
            arc={arc}
            selectedChapterId={selectedChapterId}
            onSelectChapter={onSelectChapter}
          />
        ))}
      </div>

      {/* 一键确认 */}
      {unconfirmedCount > 0 && (
        <div className="border-t p-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs text-green-600 border-green-300 hover:bg-green-50"
            onClick={onConfirmAll}
          >
            <Check className="h-3 w-3 mr-1" />
            一键确认 ({unconfirmedCount})
          </Button>
        </div>
      )}
    </div>
  )
}
