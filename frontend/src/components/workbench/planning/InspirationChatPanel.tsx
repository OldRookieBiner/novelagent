// frontend/src/components/workbench/planning/InspirationChatPanel.tsx
// 灵感聊天面板 — 对话式灵感收集，右侧实时预览结构化参数

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, SkipForward } from 'lucide-react'
import { inspirationChatApi } from '@/lib/api'
import type { InspirationChatCallbacks } from '@/lib/api'
import { inferFieldsFromText, getMissingFields } from '@/lib/inspiration'
import type { InspirationData } from '@/lib/inspiration'
import { InspirationPreview } from './InspirationPreview'

interface InspirationChatPanelProps
{
  projectId: number
  onComplete: (data: InspirationData) => void
  onSwitchToForm: () => void
  initialMessages?: Array<{ role: 'user' | 'assistant'; content: string }>
  initialFields?: Partial<InspirationData>
}

interface ChatMessage
{
  role: 'user' | 'assistant'
  content: string
}

export function InspirationChatPanel({
  projectId,
  onComplete,
  onSwitchToForm,
  initialMessages,
  initialFields,
}: InspirationChatPanelProps)
{
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages || [])
  const [input, setInput] = useState('')
  const [extractedFields, setExtractedFields] = useState<Partial<InspirationData>>(initialFields || {})
  const [missingFields, setMissingFields] = useState<string[]>(
    initialFields ? getMissingFields(initialFields as InspirationData) : ['novelType', 'targetReader', 'targetWords', 'era']
  )
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const assistantContentRef = useRef<string>('')
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 自动滚动到底部
  useEffect(() =>
  {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 防抖更新消息列表（避免流式 chunk 导致频繁重渲染）
  const debouncedUpdateMessage = useCallback((content: string) =>
  {
    assistantContentRef.current = content
    if (debounceTimerRef.current)
    {
      clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = setTimeout(() =>
    {
      setMessages((prev) =>
      {
        const updated = [...prev]
        if (updated.length > 0 && updated[updated.length - 1].role === 'assistant')
        {
          updated[updated.length - 1] = { role: 'assistant', content: assistantContentRef.current }
        }
        else
        {
          updated.push({ role: 'assistant', content: assistantContentRef.current })
        }
        return updated
      })
    }, 100)
  }, [])

  const handleSend = async () =>
  {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    // 客户端预推断：从用户输入中提取关键词映射字段
    const clientInferred = inferFieldsFromText(userMessage)
    const merged = { ...extractedFields, ...clientInferred }
    setExtractedFields(merged)
    setMissingFields(getMissingFields(merged as InspirationData))

    // 重置助手回复缓冲区
    assistantContentRef.current = ''

    // 构建 SSE 回调
    const callbacks: InspirationChatCallbacks = {
      onChunk: (content: string) =>
      {
        assistantContentRef.current += content
        debouncedUpdateMessage(assistantContentRef.current)
      },
      onExtracted: (fields: Record<string, unknown>, missing: string[]) =>
      {
        setExtractedFields((prev) => ({ ...prev, ...fields }) as Partial<InspirationData>)
        setMissingFields(missing)
      },
      onDone: () =>
      {
        // 确保最后一次防抖更新被刷新
        if (debounceTimerRef.current)
        {
          clearTimeout(debounceTimerRef.current)
        }
        setMessages((prev) =>
        {
          const updated = [...prev]
          if (updated.length > 0 && updated[updated.length - 1].role === 'assistant')
          {
            updated[updated.length - 1] = { role: 'assistant', content: assistantContentRef.current }
          }
          return updated
        })
        setLoading(false)
      },
      onError: (error: string) =>
      {
        setMessages((prev) => [...prev, { role: 'assistant', content: `出错了：${error}` }])
        setLoading(false)
      },
    }

    try
    {
      await inspirationChatApi.chat(projectId, userMessage, callbacks)
    }
    catch (err)
    {
      setMessages((prev) => [...prev, { role: 'assistant', content: '网络错误，请重试' }])
      setLoading(false)
    }
  }

  // 右侧预览区字段编辑回调
  const handleFieldEdit = (field: keyof InspirationData, value: string) =>
  {
    const updated = { ...extractedFields, [field]: value }
    setExtractedFields(updated)
    setMissingFields(getMissingFields(updated as InspirationData))
  }

  // 确认灵感数据并完成
  const handleComplete = () =>
  {
    onComplete(extractedFields as InspirationData)
  }

  return (
    <div className="flex h-full">
      {/* 左侧对话区 */}
      <div className="flex flex-1 flex-col border-r">
        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              描述你想写的故事，AI 会帮你完善细节
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="border-t p-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="继续描述或回答问题..."
            disabled={loading}
            className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="rounded-md bg-primary px-3 py-2 text-primary-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
          <button
            onClick={onSwitchToForm}
            className="rounded-md border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            <SkipForward className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* 右侧结构化预览 */}
      <div className="w-72 p-4 overflow-y-auto">
        <InspirationPreview
          fields={extractedFields}
          missingFields={missingFields}
          onFieldEdit={handleFieldEdit}
          onComplete={handleComplete}
        />
      </div>
    </div>
  )
}
