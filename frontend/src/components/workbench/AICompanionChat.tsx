import { useEffect, useRef } from 'react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AIActionCard } from './AIActionCard'

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
            {msg.content}
            {msg.actions && msg.actions.length > 0 && <AIActionCard actions={msg.actions} />}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
