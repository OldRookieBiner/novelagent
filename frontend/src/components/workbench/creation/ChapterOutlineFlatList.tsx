// frontend/src/components/workbench/creation/ChapterOutlineFlatList.tsx

import { Sparkles, X, RotateCcw, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ChapterOutlineCard } from './ChapterOutlineCard'
import type { ChapterOutline } from '@/types'

/** 章节大纲生成进度 */
export interface ChapterOutlineProgress
{
  current: number
  total: number
  currentTitle: string
  completed: string[]
}

interface ChapterOutlineFlatListProps
{
  /** 章节列表 */
  chapters: ChapterOutline[]
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
 * 章节大纲扁平列表 — 左侧边栏
 * 包含标题栏、进度条、章节列表、一键确认
 */
export function ChapterOutlineFlatList(props: ChapterOutlineFlatListProps)
{
  const {
    chapters,
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

  return (
    <div className="w-40 border-r bg-white flex flex-col">
      {/* 标题栏与操作按钮 */}
      <div className="p-2.5 border-b flex items-center justify-between">
        <span className="text-xs font-medium">章节 ({chapters.length})</span>
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
          {chapters.length > 0 && (
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
          {progress.completed && progress.completed.length > 0 && (
            <div className="text-[9px] text-blue-400 mt-1 truncate">
              已完成：{progress.completed.join('、')}
            </div>
          )}
        </div>
      )}

      {/* 章节列表 */}
      <div className="flex-1 overflow-auto">
        {chapters.map((chapter) => (
          <ChapterOutlineCard
            key={chapter.id}
            chapter={chapter}
            isActive={selectedChapterId === chapter.id}
            onClick={() => onSelectChapter(chapter)}
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
