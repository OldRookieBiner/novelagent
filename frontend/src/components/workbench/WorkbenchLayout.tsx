// WorkbenchLayout.tsx — 三栏+标签页布局

import { ReactNode, useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { LayoutList, Pencil, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Header from '@/components/layout/Header'
import { TabNavigation } from './TabNavigation'
import { ChapterListPanel } from './ChapterListPanel'
import { AgentChatPanel } from './AgentChatPanel'
import { VolumePanel, VolumeInfo } from './VolumePanel'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { cn } from '@/lib/utils'

export interface PlotBlockGroup {
  title: string
  chapters: { chapterNumber: number; title: string; status: 'written' | 'writing' | 'pending' }[]
  isActive: boolean
}

interface WorkbenchLayoutProps {
  projectName: string
  onNameChange?: (name: string) => void
  progress: number
  plotBlocks: PlotBlockGroup[]
  volumes?: VolumeInfo[]
  currentVolume?: number
  showChapterList?: boolean  // 是否显示左侧章节列表
  children: ReactNode
}

export function WorkbenchLayout({
  projectName,
  onNameChange,
  progress,
  plotBlocks,
  volumes = [],
  currentVolume = 1,
  showChapterList = false,  // 默认不显示章节列表
  children,
}: WorkbenchLayoutProps) {
  const phase = useWorkbenchStore((s) => s.phase)

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 项目 Header */}
      <header className="h-12 border-b bg-white flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <InlineEditableName
            name={projectName}
            onChange={onNameChange}
          />
          <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {phase === 'incubation' ? '创意孵化' : phase === 'structure' ? '结构设计' : phase === 'writing' ? '写作中' : '修订中'}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all bg-primary"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-[10px]">{progress}%</span>
          </div>
        </div>
        <Button asChild variant="outline" size="sm" className="gap-1.5">
          <Link to="/">
            <LayoutList className="h-3.5 w-3.5" />
            项目列表
          </Link>
        </Button>
      </header>

      {/* Tab 导航 */}
      <TabNavigation />

      {/* 主内容区：三栏 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左栏：章节列表 + 卷管理（可选） */}
        {showChapterList && (
          <div className="w-[180px] bg-white border-r border-gray-200 overflow-y-auto flex-shrink-0 flex flex-col">
            <ChapterListPanel blocks={plotBlocks} />
            {volumes.length > 0 && (
              <>
                <div className="border-t border-gray-100 mx-2" />
                <VolumePanel volumes={volumes} currentVolume={currentVolume} />
              </>
            )}
          </div>
        )}

        {/* 中栏：标签页内容 */}
        <main className={cn(
          'flex-1 overflow-auto',
          !showChapterList && 'border-l border-gray-200'
        )}>
          {children}
        </main>

        {/* 右栏：智能体对话 */}
        <AgentChatPanel />
      </div>
    </div>
  )
}

function InlineEditableName({ name, onChange }: { name: string; onChange?: (name: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(name)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.select()
    }
  }, [editing])

  const startEdit = () => {
    if (!onChange) return
    setDraft(name)
    setEditing(true)
  }

  const save = async () => {
    const trimmed = draft.trim()
    if (!trimmed || trimmed === name) {
      setEditing(false)
      return
    }
    setSaving(true)
    try {
      await onChange(trimmed)
      setEditing(false)
    } catch {
      setDraft(name)
    } finally {
      setSaving(false)
    }
  }

  const cancel = () => {
    setDraft(name)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') cancel()
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={save}
          disabled={saving}
          className="text-base font-semibold bg-white border border-primary rounded px-1.5 py-0 outline-none w-48"
          maxLength={50}
        />
        {saving ? (
          <span className="text-[10px] text-muted-foreground">保存中...</span>
        ) : (
          <Check className="h-3.5 w-3.5 text-primary cursor-pointer" onClick={save} onMouseDown={(e) => e.preventDefault()} />
        )}
        <X className="h-3.5 w-3.5 text-muted-foreground cursor-pointer" onClick={cancel} onMouseDown={(e) => e.preventDefault()} />
      </div>
    )
  }

  return (
    <h1
      className="text-base font-semibold cursor-pointer group flex items-center gap-1"
      onClick={startEdit}
      title="点击修改项目名"
    >
      {name}
      {onChange && (
        <Pencil className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </h1>
  )
}
