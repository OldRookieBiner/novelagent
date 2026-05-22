// frontend/src/components/workbench/creation/ChapterDetailPanel.tsx

import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { ChapterOutline } from '@/types'

interface ChapterDetailPanelProps
{
  /** 当前选中的章节 */
  selectedChapter: ChapterOutline | null
  /** 是否折叠 */
  collapsed: boolean
  /** 折叠切换回调 */
  onToggleCollapse: () => void
  /** 已确认章节数 */
  confirmedCount: number
  /** 已写正文章节数 */
  hasContentCount: number
  /** 总章节数 */
  totalChapters: number
  /** 总目标字数 */
  totalTargetWords: number
}

/**
 * 章节详情面板 — 右侧可折叠面板
 * 显示选中章节状态、统计数据
 */
export function ChapterDetailPanel(props: ChapterDetailPanelProps)
{
  const {
    selectedChapter,
    collapsed,
    onToggleCollapse,
    confirmedCount,
    hasContentCount,
    totalChapters,
    totalTargetWords,
  } = props

  return (
    <div className={`border-l bg-white shrink-0 transition-all duration-300 ${collapsed ? 'w-12' : 'w-[360px]'} relative ${collapsed ? '' : 'p-3'}`}>
      {/* 折叠切换按钮 */}
      <button
        onClick={onToggleCollapse}
        className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>

      {/* 展开状态内容 */}
      {!collapsed && (
        <>
          <h3 className="text-xs font-medium mb-3">章节详情</h3>
          {selectedChapter ? (
            <div className="space-y-3">
              {/* 状态卡片 */}
              <Card>
                <CardContent className="pt-3 pb-3">
                  <div className="text-xs">
                    <span className="text-muted-foreground">状态：</span>
                    <span className={selectedChapter.confirmed ? 'text-green-600 font-medium' : 'text-amber-600'}>
                      {selectedChapter.confirmed ? '已确认' : '草稿'}
                    </span>
                  </div>
                  {selectedChapter.has_content && (
                    <div className="text-xs mt-1">
                      <span className="text-muted-foreground">已写正文：</span>
                      <span className="text-blue-600 font-medium">是</span>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 统计信息 */}
              <div className="p-3 bg-blue-50 rounded-md border border-blue-200 text-xs space-y-1.5">
                <div className="font-medium text-blue-800">📊 章节大纲统计</div>
                <div className="text-blue-700">已确认：{confirmedCount} / {totalChapters}</div>
                <div className="text-blue-700">已写正文：{hasContentCount} 章</div>
                <div className="text-blue-700">总目标字数：{totalTargetWords.toLocaleString()}</div>
              </div>

              {/* 已确认提示 */}
              {selectedChapter.confirmed && (
                <div className="p-2.5 bg-green-50 rounded-md border border-green-200 text-xs">
                  <p className="font-medium text-green-700">章节已确认</p>
                  <p className="text-green-600 mt-1">可以进行章节写作</p>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-32 text-center">
              <p className="text-xs text-muted-foreground">选择章节查看详情</p>
            </div>
          )}
        </>
      )}

      {/* 折叠状态图标 */}
      {collapsed && (
        <div className="flex flex-col items-center pt-4 gap-3">
          <FileText className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
