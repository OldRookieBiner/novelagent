// StructureTab.tsx — 结构标签页

import { useState, useEffect, useCallback } from 'react'
import { GitBranch, BoxSelect, Network, Activity, Hash } from 'lucide-react'
import { knowledgeApi } from '@/lib/api'
import { cn } from '@/lib/utils'

interface StructureTabProps {
  projectId: number
}

type StructureSection = 'plot_blocks' | 'questions' | 'subplots' | 'rhythm' | 'chapters'

const SECTIONS: { key: StructureSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'plot_blocks', label: '情节块', icon: BoxSelect },
  { key: 'questions', label: '问题链', icon: GitBranch },
  { key: 'subplots', label: '支线网络', icon: Network },
  { key: 'rhythm', label: '节奏曲线', icon: Activity },
  { key: 'chapters', label: '章节数估算', icon: Hash },
]

export function StructureTab({ projectId }: StructureTabProps) {
  const [activeSection, setActiveSection] = useState<StructureSection>('plot_blocks')
  const [plotBlocks, setPlotBlocks] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const loadStructure = useCallback(async () => {
    setLoading(true)
    try {
      const blocks = await knowledgeApi.getPlotBlocks(projectId)
      setPlotBlocks(blocks)
    } catch {
      setPlotBlocks([])
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    loadStructure()
  }, [loadStructure])

  const renderContent = () => {
    switch (activeSection) {
      case 'plot_blocks':
        return <PlotBlocksView data={plotBlocks} loading={loading} />
      case 'questions':
        return <QuestionsView data={plotBlocks} loading={loading} />
      case 'subplots':
        return <PlaceholderView label="支线网络" />
      case 'rhythm':
        return <PlaceholderView label="节奏曲线" />
      case 'chapters':
        return <PlaceholderView label="章节数估算" />
      default:
        return null
    }
  }

  return (
    <div className="flex h-full">
      {/* 左侧导航 */}
      <div className="w-40 border-r bg-white flex-shrink-0">
        <div className="p-3 border-b">
          <div className="flex items-center gap-2 text-sm font-medium">
            <GitBranch className="h-4 w-4" />
            结构
          </div>
        </div>
        <nav className="py-1">
          {SECTIONS.map((section) => {
            const Icon = section.icon
            return (
              <button
                key={section.key}
                onClick={() => setActiveSection(section.key)}
                className={cn(
                  'w-full flex items-center gap-2 px-3 py-2 text-xs text-left transition-colors',
                  activeSection === section.key
                    ? 'bg-primary/5 text-primary font-medium border-r-2 border-primary'
                    : 'text-muted-foreground hover:bg-muted/50'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {section.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* 右侧内容 */}
      <div className="flex-1 overflow-auto p-6">
        {renderContent()}
      </div>
    </div>
  )
}

// ========== 情节块视图 ==========
function PlotBlocksView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="情节块尚未生成，请先完成结构设计阶段" />

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">情节块</h3>
      {data.map((block, index) => (
        <div key={block.id} className="border rounded-lg p-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className="bg-primary/10 text-primary text-[10px] font-medium px-2 py-0.5 rounded">
              块 {index + 1}
            </span>
            <span className="text-sm font-medium">{block.title}</span>
            {block.expected_mood && (
              <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                {block.expected_mood}
              </span>
            )}
          </div>

          {/* 章节范围 */}
          {block.chapter_start && (
            <div className="text-[10px] text-muted-foreground">
              第 {block.chapter_start}{block.chapter_end ? `-${block.chapter_end}` : '+'} 章
            </div>
          )}

          {/* 要回答的旧问题 */}
          {block.questions_to_answer?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">回答的问题</div>
              <ul className="space-y-0.5">
                {block.questions_to_answer.map((q: string, i: number) => (
                  <li key={i} className="text-xs flex items-start gap-1">
                    <span className="text-green-500 mt-0.5">✓</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 要提出的新问题 */}
          {block.questions_to_raise?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">提出的问题</div>
              <ul className="space-y-0.5">
                {block.questions_to_raise.map((q: string, i: number) => (
                  <li key={i} className="text-xs flex items-start gap-1">
                    <span className="text-amber-500 mt-0.5">?</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 必须事件 */}
          {block.must_happen?.length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">必须事件</div>
              <ul className="space-y-0.5">
                {block.must_happen.map((evt: string, i: number) => (
                  <li key={i} className="text-xs flex items-start gap-1">
                    <span className="text-red-500 mt-0.5">!</span>
                    {evt}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 完成摘要 */}
          {block.completion_summary && (
            <div className="bg-muted/30 rounded px-3 py-2 text-xs text-muted-foreground">
              {block.completion_summary}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ========== 问题链视图 ==========
function QuestionsView({ data, loading }: { data: any[]; loading: boolean }) {
  if (loading) return <LoadingSkeleton />
  if (!data?.length) return <EmptyState label="问题链将随情节块一起生成" />

  // 从情节块中提取所有问题
  const questions: { text: string; type: 'answer' | 'raise'; blockTitle: string }[] = []
  for (const block of data) {
    for (const q of block.questions_to_answer || []) {
      questions.push({ text: q, type: 'answer', blockTitle: block.title })
    }
    for (const q of block.questions_to_raise || []) {
      questions.push({ text: q, type: 'raise', blockTitle: block.title })
    }
  }

  if (!questions.length) return <EmptyState label="问题链将随情节块一起生成" />

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">问题链</h3>
      {questions.map((q, i) => (
        <div key={i} className="flex items-start gap-2 border-l-2 pl-3 py-1"
          style={{ borderColor: q.type === 'answer' ? '#22c55e' : '#f59e0b' }}>
          <span className={cn(
            'text-[10px] px-1.5 py-0.5 rounded shrink-0',
            q.type === 'answer' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
          )}>
            {q.type === 'answer' ? '回答' : '提出'}
          </span>
          <div className="flex-1">
            <div className="text-xs">{q.text}</div>
            <div className="text-[10px] text-muted-foreground">{q.blockTitle}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ========== 通用占位 ==========
function PlaceholderView({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
      <GitBranch className="h-8 w-8 mb-3 text-muted-foreground/30" />
      <p>{label}将在结构设计阶段生成</p>
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
      <GitBranch className="h-8 w-8 mb-3 text-muted-foreground/30" />
      <p>{label}</p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-5 w-24 bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
      <div className="h-24 w-full bg-muted rounded animate-pulse" />
    </div>
  )
}
