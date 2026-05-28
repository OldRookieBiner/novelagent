// AgentChatPanel.tsx — Right panel: AI creation agent chat

import { useState, useRef, useEffect, useCallback } from 'react'
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck, ChevronDown } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { sendAgentMessage } from '@/lib/agentApi'
import { modelConfigsApi } from '@/lib/api'
import type { AiMessage, ImpactReport, AgentWarning } from '@/stores/workbenchStore'
import type { ModelConfig } from '@/types'

const PHASE_LABELS: Record<string, string> = {
  incubation: '创意孵化',
  structure: '结构设计',
  writing: '写作中',
  revision: '修订中',
}

const PHASE_EMPTY_HINTS: Record<string, string> = {
  incubation: '描述你的小说创意，智能体将帮你完善世界观、角色和风格',
  structure: '和智能体讨论情节安排和结构设计',
  writing: '和智能体讨论你的创作想法',
  revision: '和智能体讨论修订方向',
}

interface ModelOption {
  id: number
  name: string
  isDefault: boolean
}

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

  const phase = useWorkbenchStore((s) => s.phase)

  const [input, setInput] = useState('')
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const modelSelectorRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages, pendingImpacts])

  // 加载模型配置列表（仅一次）
  useEffect(() => {
    if (modelsLoaded) return
    modelConfigsApi.list().then((res) => {
      const enabled = res.models
        .filter((m: ModelConfig) => m.is_enabled)
        .map((m: ModelConfig) => ({
          id: m.id,
          name: m.name,
          isDefault: m.is_default,
        }))
      setModelOptions(enabled)
      const defaultModel = enabled.find((m: ModelOption) => m.isDefault)
      if (defaultModel) {
        setSelectedModelId(defaultModel.id)
      }
      setModelsLoaded(true)
    }).catch(() => {
      setModelsLoaded(true)
    })
  }, [modelsLoaded])

  // 模型选择器 click-outside 关闭
  useEffect(() => {
    if (!modelSelectorOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (modelSelectorRef.current && !modelSelectorRef.current.contains(e.target as Node)) {
        setModelSelectorOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [modelSelectorOpen])

  // SSE chat handler — 使用 agentApi
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

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await sendAgentMessage(
        currentProjectId,
        messageText,
        {
          onAgentText: (content) => {
            assistantMsg.content += content
          },
          onToolStart: (tool, args) => {
            assistantMsg.segments.push({
              type: 'tool_start' as any,
              content: `调用 ${tool}...`,
              data: { tool, args },
            })
          },
          onToolResult: (tool, result) => {
            assistantMsg.segments.push({
              type: 'tool_result' as any,
              content: `${tool} 完成`,
              data: { tool, result },
            })
          },
          onImpactAssessment: (data) => {
            addPendingImpact(data as unknown as ImpactReport)
          },
          onWarning: (data) => {
            addAgentWarning(data as unknown as AgentWarning)
          },
          onAgentDone: () => {},
          onError: (error) => {
            assistantMsg.content = assistantMsg.content || `错误：${error}`
          },
        },
        {
          modelConfigId: selectedModelId ?? undefined,
          signal: controller.signal,
        }
      )
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        assistantMsg.content = assistantMsg.content || `连接错误：${err.message}`
      }
    } finally {
      setIsAgentSending(false)
      abortRef.current = null
    }
  }, [input, currentProjectId, isAgentSending, selectedModelId, addAiMessage, addPendingImpact, addAgentWarning, setIsAgentSending])

  const handleImpactDecision = async (changeId: number, decision: string) => {
    if (!currentProjectId) return

    try {
      const res = await fetch(`/api/projects/${currentProjectId}/agent/impact-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ change_id: changeId, decision }),
      })

      if (res.ok) {
        removePendingImpact(changeId)
      }
    } catch {
      // 静默失败
    }
  }

  // 折叠状态
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

  const selectedModelName = selectedModelId
    ? modelOptions.find(m => m.id === selectedModelId)?.name
    : '默认模型'

  return (
    <div className="w-[300px] bg-white border-l border-gray-200 flex flex-col flex-shrink-0">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-gray-100 flex items-center gap-2">
        <span className="font-semibold text-sm">✦ 智能体</span>
        <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
          {PHASE_LABELS[phase] || '未知'}
        </span>
        <div className={`w-1.5 h-1.5 rounded-full ml-auto ${isAgentSending ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 模型选择器 */}
      <div className="px-3 py-1.5 border-b border-gray-50" ref={modelSelectorRef}>
        <div className="relative">
          <button
            onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
            className="w-full flex items-center justify-between gap-1 rounded border border-gray-200 px-2 py-1 text-[10px] text-foreground hover:border-gray-300 transition-colors"
          >
            <span className="truncate">{selectedModelName}</span>
            <ChevronDown className="h-3 w-3 shrink-0 text-gray-400" />
          </button>
          {modelSelectorOpen && (
            <div className="absolute left-0 right-0 top-full mt-0.5 bg-white border border-gray-200 rounded shadow-sm z-10 max-h-40 overflow-y-auto">
              <button
                onClick={() => { setSelectedModelId(null); setModelSelectorOpen(false) }}
                className={cn(
                  'w-full text-left px-2 py-1.5 text-[10px] hover:bg-muted/50',
                  !selectedModelId && 'text-primary font-medium'
                )}
              >
                默认模型
              </button>
              {modelOptions.map(m => (
                <button
                  key={m.id}
                  onClick={() => { setSelectedModelId(m.id); setModelSelectorOpen(false) }}
                  className={cn(
                    'w-full text-left px-2 py-1.5 text-[10px] hover:bg-muted/50',
                    selectedModelId === m.id && 'text-primary font-medium'
                  )}
                >
                  {m.name}
                  {m.isDefault && <span className="ml-1 text-muted-foreground">(默认)</span>}
                </button>
              ))}
            </div>
          )}
        </div>
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
            {PHASE_EMPTY_HINTS[phase] || '和智能体讨论你的创作想法'}
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
