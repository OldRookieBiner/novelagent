// frontend/src/components/workbench/AICompanionChat.tsx

import { useEffect, useRef, useState } from 'react'
import { useWorkbenchStore, type AiMessage } from '@/stores/workbenchStore'
import { AIActionCard } from './AIActionCard'

/** 渲染 segments 混合内容 */
function MessageContent({ message }: { message: AiMessage })
{
  if (!message.segments || message.segments.length === 0)
  {
    return <span className="whitespace-pre-wrap">{message.content}</span>
  }

  // 合并相邻的 agent_text segments
  const merged: Array<{ type: string; content: string; data?: Record<string, unknown> }> = []
  for (const seg of message.segments)
  {
    const last = merged[merged.length - 1]
    if (last && last.type === 'agent_text' && seg.type === 'agent_text')
    {
      last.content += seg.content
    }
    else
    {
      merged.push({ type: seg.type, content: seg.content, data: seg.data })
    }
  }

  return (
    <>
      {merged.map((seg, i) =>
      {
        if (seg.type === 'agent_text')
        {
          return <span key={i} className="whitespace-pre-wrap">{seg.content}</span>
        }

        if (seg.type === 'chapter_preview')
        {
          return <ChapterPreviewCard key={i} data={seg.data || {}} />
        }

        if (seg.type === 'review')
        {
          return <ReviewResultCard key={i} data={seg.data || {}} />
        }

        return <span key={i} className="whitespace-pre-wrap">{seg.content}</span>
      })}
    </>
  )
}

/** 章节生成/重写预览卡片 */
function ChapterPreviewCard({ data }: { data: Record<string, unknown> })
{
  const [expanded, setExpanded] = useState(false)
  const preview = String(data.preview || '')
  const title = String(data.title || '')
  const wordCount = Number(data.word_count || 0)
  const action = String(data.action || 'generated')
  const actionLabel = action === 'rewritten' ? '已重写' : '已生成'

  return (
    <div className="my-1.5 rounded bg-slate-800/60 border border-emerald-700/30 px-2.5 py-2">
      <div className="text-[10px] text-emerald-400/80 mb-1">
        📝 {title} · {actionLabel} · {wordCount}字
      </div>
      {preview && (
        <div className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
          {expanded ? preview : preview.slice(0, 150)}
          {preview.length > 150 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-1 text-slate-500 hover:text-slate-300"
            >
              {expanded ? '收起' : '...展开'}
            </button>
          )}
        </div>
      )}
      <div className="text-[10px] text-slate-500 mt-1">
        完整内容可在「写作」标签页查看
      </div>
    </div>
  )
}

/** 审核结果卡片 */
function ReviewResultCard({ data }: { data: Record<string, unknown> })
{
  const review = data as {
    passed?: boolean
    scores?: Record<string, number>
    issues?: Array<{ type: string; location: string; description: string }>
    suggestions?: string
  }

  const passed = review.passed !== false
  const scores = review.scores || {}
  const issues = review.issues || []

  return (
    <div className={`my-1.5 rounded border px-2.5 py-2 ${
      passed
        ? 'bg-green-900/20 border-green-700/30'
        : 'bg-red-900/20 border-red-700/30'
    }`}>
      <div className={`text-[10px] font-medium mb-1 ${
        passed ? 'text-green-400' : 'text-red-400'
      }`}>
        {passed ? '✓ 审核通过' : '✗ 审核未通过'}
      </div>

      {Object.keys(scores).length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mb-1">
          {Object.entries(scores).map(([key, val]) => (
            <span key={key} className="text-[10px] text-slate-400">
              {key}: <span className={val >= 7 ? 'text-green-400' : val >= 5 ? 'text-amber-400' : 'text-red-400'}>{val}</span>
            </span>
          ))}
        </div>
      )}

      {issues.length > 0 && (
        <div className="space-y-0.5 mb-1">
          {issues.map((issue, i) => (
            <div key={i} className="text-[10px] text-slate-400">
              <span className="text-amber-400">[{issue.type}]</span> {issue.location}: {issue.description}
            </div>
          ))}
        </div>
      )}

      {review.suggestions && (
        <div className="text-[10px] text-slate-400 italic">{review.suggestions}</div>
      )}
    </div>
  )
}

export function AICompanionChat()
{
  const messages = useWorkbenchStore((s) => s.aiMessages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() =>
  {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-auto p-3 space-y-3">
      {messages.length === 0 && (
        <div className="flex flex-col items-center justify-center h-full gap-2 text-center">
          <div className="text-2xl">🤖</div>
          <p className="text-xs text-slate-500 leading-relaxed">
            我是你的 AI 编剧搭档<br />
            跟我说说你对小说的想法<br />
            我会帮你修改大纲、角色、章节...
          </p>
        </div>
      )}
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
              msg.role === 'user'
                ? 'bg-blue-900/50 text-blue-200'
                : 'bg-emerald-900/40 text-emerald-200'
            }`}
          >
            <MessageContent message={msg} />
            {msg.actions && msg.actions.length > 0 && <AIActionCard actions={msg.actions} />}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
