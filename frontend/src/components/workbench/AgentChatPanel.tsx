// AgentChatPanel.tsx — Right panel: AI creation agent chat

import { useState, useRef, useEffect, useCallback } from 'react'
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { AiMessage, ImpactReport, AgentWarning } from '@/stores/workbenchStore'

const API_BASE = '/api/projects'

export function AgentChatPanel() {
  const {
    currentProjectId,
    aiSidebarOpen,
    toggleAiSidebar,
    aiMessages,
    addAiMessage,
    pendingImpacts,
    addPendingImpact,
    removePendingImpact,
    agentWarnings,
    addAgentWarning,
    isAgentSending,
    setIsAgentSending,
  } = useWorkbenchStore()

  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages, pendingImpacts])

  // SSE chat handler
  const handleSend = useCallback(async () => {
    if (!input.trim() || !currentProjectId || isAgentSending) return

    const userMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(userMsg)
    const messageText = input.trim()
    setInput('')
    setIsAgentSending(true)

    const assistantMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      segments: [],
      timestamp: Date.now(),
    }
    addAiMessage(assistantMsg)

    try {
      const res = await fetch(`${API_BASE}/${currentProjectId}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        assistantMsg.content = `错误：${err.detail || res.statusText}`
        setIsAgentSending(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let lastEventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            lastEventType = line.slice(7).trim()
            continue
          }
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6)
            try {
              const data = JSON.parse(dataStr)
              // Dispatch based on the SSE event type
              if (lastEventType === 'chunk' && data.content && typeof data.content === 'string') {
                assistantMsg.content += data.content
              } else if (lastEventType === 'agent_tool_start' && data.tool) {
                assistantMsg.segments.push({
                  type: 'tool_start' as any,
                  content: `调用 ${data.tool}...`,
                  data,
                })
              } else if (lastEventType === 'agent_tool_result' && data.tool) {
                assistantMsg.segments.push({
                  type: 'tool_result' as any,
                  content: `${data.tool} 完成`,
                  data,
                })
              } else if (lastEventType === 'impact_assessment' && data.change_id !== undefined) {
                addPendingImpact(data as ImpactReport)
              } else if (lastEventType === 'warning' && data.message) {
                addAgentWarning(data as AgentWarning)
              }
            } catch {
              // Not JSON, skip
            }
            lastEventType = ''
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        assistantMsg.content = `连接错误：${err.message}`
      }
    } finally {
      setIsAgentSending(false)
    }
  }, [input, currentProjectId, isAgentSending, addAiMessage, addPendingImpact, addAgentWarning, setIsAgentSending])

  // Impact decision handler
  const handleImpactDecision = async (changeId: number, decision: string) => {
    if (!currentProjectId) return

    try {
      const res = await fetch(`${API_BASE}/${currentProjectId}/agent/impact-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ change_id: changeId, decision }),
      })

      if (res.ok) {
        removePendingImpact(changeId)
      }
    } catch {
      // Silently fail
    }
  }

  // Collapsed state
  if (!aiSidebarOpen) {
    return (
      <div className="w-10 bg-white border-l border-gray-200 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-gray-400 hover:text-gray-600 transition-colors"
          title="展开智能体"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        {agentWarnings.length > 0 && (
          <div className="relative">
            <AlertTriangle className="h-3 w-3 text-amber-500" />
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full" />
          </div>
        )}
        <span className="text-gray-400 text-[10px]" style={{ writingMode: 'vertical-lr' }}>
          智能体
        </span>
      </div>
    )
  }

  return (
    <div className="w-[300px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-gray-100 font-semibold text-sm flex items-center gap-2">
        <span>✦ 智能体</span>
        <div className={`w-1.5 h-1.5 rounded-full ml-auto ${isAgentSending ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Warnings */}
      {agentWarnings.length > 0 && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-100">
          {agentWarnings.slice(-2).map((w, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[10px] text-amber-700 mb-1">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
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
            {msg.content || (msg.role === 'assistant' && isAgentSending ? '...' : '')}
            {/* Tool segments */}
            {msg.segments.filter(s => s.type === 'tool_result').map((s, i) => (
              <div key={i} className="mt-1 text-[10px] text-muted-foreground border-t border-gray-100 pt-1">
                {s.content}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Impact Assessment Cards */}
      {pendingImpacts.length > 0 && (
        <div className="px-3 py-2 border-t border-gray-100 space-y-2">
          {pendingImpacts.map((report) => (
            <div key={report.change_id} className="bg-gray-50 rounded-lg p-2 text-[10px]">
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldCheck className="h-3 w-3 text-gray-500" />
                <span className="font-medium">影响评估</span>
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-[9px] font-medium',
                  report.impact_level === 'severe' ? 'bg-red-100 text-red-700' :
                  report.impact_level === 'moderate' ? 'bg-orange-100 text-orange-700' :
                  report.impact_level === 'minor' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-green-100 text-green-700'
                )}>
                  {report.impact_label}
                </span>
              </div>
              <div className="text-muted-foreground mb-1.5">
                影响 {report.affected_chapters} 章 / {report.affected_paragraphs} 段
              </div>
              {report.detail && (
                <div className="text-muted-foreground mb-1.5 text-[9px]">{report.detail}</div>
              )}
              <div className="flex gap-1.5">
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'proceed')}
                  className="px-2 py-1 bg-primary text-primary-foreground rounded text-[9px]"
                >
                  按原方案修改
                </button>
                <button
                  onClick={() => handleImpactDecision(report.change_id, 'abandon')}
                  className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-[9px]"
                >
                  放弃
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-2 border-t border-gray-100">
        <div className="flex gap-1.5">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            className="flex-1 border border-gray-200 rounded-md px-2.5 py-1.5 text-[11px] outline-none focus:border-primary"
            placeholder={isAgentSending ? '思考中...' : '输入消息...'}
            disabled={isAgentSending}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isAgentSending}
            className="bg-primary text-primary-foreground border-none px-2.5 py-1.5 rounded-md text-[11px] disabled:opacity-50"
          >
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
