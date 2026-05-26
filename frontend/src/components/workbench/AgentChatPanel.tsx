// AgentChatPanel.tsx — 右栏智能体对话面板

import { useState, useRef, useEffect } from 'react'
import { PanelRightClose, PanelRightOpen, Send } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { AiMessage } from '@/stores/workbenchStore'

export function AgentChatPanel()
{
  const { aiSidebarOpen, toggleAiSidebar, aiMessages, addAiMessage } = useWorkbenchStore()
  const [input, setInput] = useState('')
  const [sending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() =>
  {
    if (scrollRef.current)
    {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages])

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-white border-l border-gray-200 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
          title="展开智能体"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-gray-400 text-[10px]" style={{ writingMode: 'vertical-lr' }}>
          智能体
        </span>
      </div>
    )
  }

  const handleSend = () =>
  {
    if (!input.trim() || sending) return

    const msg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(msg)
    setInput('')
    // TODO: 实际发送到 Agent API
  }

  return (
    <div className="w-[280px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
      {/* 标题栏 */}
      <div className="px-3 py-2.5 border-b border-gray-100 font-semibold text-sm flex items-center gap-2">
        ✦ 智能体
        <div className="w-1.5 h-1.5 bg-green-500 rounded-full ml-auto" />
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 消息列表 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {aiMessages.length === 0 && (
          <div className="text-center text-muted-foreground text-xs py-8">
            和智能体讨论你的创作想法
          </div>
        )}
        {aiMessages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'rounded-lg px-3 py-2 text-[11px] leading-relaxed',
              msg.role === 'assistant'
                ? 'bg-primary/5 text-foreground'
                : 'bg-primary text-primary-foreground ml-10'
            )}
          >
            {msg.content}
          </div>
        ))}
      </div>

      {/* 输入框 */}
      <div className="px-3 py-2 border-t border-gray-100">
        <div className="flex gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            className="flex-1 border border-gray-200 rounded-md px-2.5 py-1.5 text-[11px] outline-none focus:border-primary"
            placeholder="输入消息..."
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="bg-primary text-primary-foreground border-none px-2.5 py-1.5 rounded-md text-[11px] disabled:opacity-50"
          >
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[])
{
  return classes.filter(Boolean).join(' ')
}
