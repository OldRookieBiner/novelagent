// ChapterNodePanel.tsx — 章节点确认卡片

import { useState } from 'react'
import { Check, X, Edit3, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface ChapterNode {
  chapterNumber: number
  title: string
  causalChain: string       // 因果链
  hook: string              // 钩子
  scenes: string[]          // 场景规划
  characters: string[]      // 涉及角色
  questionsToAnswer: string[] // 要回答的旧问题
  questionsToRaise: string[]  // 要提出的新问题
  foreshadowings: string[]  // 涉及的伏笔
}

interface ChapterNodePanelProps {
  node: ChapterNode
  onConfirm: () => void
  onReject: () => void
  onEdit: (updated: ChapterNode) => void
}

export function ChapterNodePanel({ node, onConfirm, onReject, onEdit }: ChapterNodePanelProps) {
  const [expanded, setExpanded] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(node.title)

  const handleEditConfirm = () => {
    onEdit({ ...node, title: editTitle })
    setEditing(false)
  }

  return (
    <div className="border rounded-lg bg-white shadow-sm">
      {/* 标题栏 */}
      <div
        className="flex items-center justify-between px-4 py-2.5 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="bg-primary/10 text-primary text-[10px] font-medium px-2 py-0.5 rounded">
            章节点
          </span>
          {editing ? (
            <input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="text-sm font-medium border-b border-primary outline-none"
              autoFocus
            />
          ) : (
            <span className="text-sm font-medium">
              第{node.chapterNumber}章 {node.title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* 展开内容 */}
      {expanded && (
        <div className="px-4 pb-3 space-y-2.5 border-t pt-3">
          {/* 因果链 */}
          {node.causalChain && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">因果链</div>
              <div className="text-xs bg-muted/30 rounded px-2.5 py-1.5">{node.causalChain}</div>
            </div>
          )}

          {/* 钩子 */}
          {node.hook && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">钩子</div>
              <div className="text-xs bg-amber-50 text-amber-800 rounded px-2.5 py-1.5">{node.hook}</div>
            </div>
          )}

          {/* 场景规划 */}
          {node.scenes?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">场景规划</div>
              <ol className="space-y-0.5">
                {node.scenes.map((scene, i) => (
                  <li key={i} className="text-xs flex items-start gap-1.5">
                    <span className="text-muted-foreground shrink-0">{i + 1}.</span>
                    {scene}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* 涉及角色 */}
          {node.characters?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">涉及角色</div>
              <div className="flex flex-wrap gap-1">
                {node.characters.map((c, i) => (
                  <span key={i} className="bg-blue-50 text-blue-700 text-[10px] px-1.5 py-0.5 rounded">{c}</span>
                ))}
              </div>
            </div>
          )}

          {/* 问题链 */}
          {(node.questionsToAnswer?.length > 0 || node.questionsToRaise?.length > 0) && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">问题链</div>
              <div className="space-y-0.5">
                {node.questionsToAnswer?.map((q, i) => (
                  <div key={`a-${i}`} className="text-xs flex items-start gap-1">
                    <span className="text-green-500 shrink-0">✓</span>{q}
                  </div>
                ))}
                {node.questionsToRaise?.map((q, i) => (
                  <div key={`r-${i}`} className="text-xs flex items-start gap-1">
                    <span className="text-amber-500 shrink-0">?</span>{q}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 涉及伏笔 */}
          {node.foreshadowings?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">涉及伏笔</div>
              <div className="flex flex-wrap gap-1">
                {node.foreshadowings.map((f, i) => (
                  <span key={i} className="bg-purple-50 text-purple-700 text-[10px] px-1.5 py-0.5 rounded">{f}</span>
                ))}
              </div>
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex items-center gap-2 pt-1">
            <Button size="sm" onClick={onConfirm} className="gap-1">
              <Check className="h-3.5 w-3.5" />
              确认并写作
            </Button>
            <Button size="sm" variant="outline" onClick={onReject} className="gap-1">
              <X className="h-3.5 w-3.5" />
              拒绝
            </Button>
            {!editing && (
              <Button size="sm" variant="ghost" onClick={() => setEditing(true)} className="gap-1">
                <Edit3 className="h-3.5 w-3.5" />
                编辑
              </Button>
            )}
            {editing && (
              <Button size="sm" variant="outline" onClick={handleEditConfirm} className="gap-1">
                <Check className="h-3.5 w-3.5" />
                保存
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
