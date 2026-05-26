// InspirationChat.tsx — 创意对话组件（对话式创意孵化）

import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { createSSEStream } from '@/lib/sseParser'
import { toast } from 'sonner'

interface InspirationChatProps {
  projectId: number
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export function InspirationChat({ projectId }: InspirationChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamingContent])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setSending(true)
    setStreamingContent('')

    const controller = new AbortController()
    abortRef.current = controller
    const accumulated: string[] = []

    try {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/inspiration`,
          method: 'POST',
          body: { message: text },
          signal: controller.signal,
        },
        (type, data) => {
          if (type === 'chunk') {
            const chunkText = typeof data === 'string' ? data : (data as any).content
            if (chunkText) {
              accumulated.push(chunkText)
              setStreamingContent(accumulated.join(''))
            }
          } else if (type === 'done') {
            const assistantMsg: ChatMessage = {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: accumulated.join(''),
              timestamp: Date.now(),
            }
            setMessages((prev) => [...prev, assistantMsg])
            setStreamingContent('')
          } else if (type === 'error') {
            const errorMsg = typeof data === 'object' && data !== null
              ? (data as any).error || JSON.stringify(data)
              : String(data)
            toast.error(`对话失败: ${errorMsg}`)
          }
        },
        (error) => {
          console.error('Inspiration chat error:', error)
          toast.error('对话失败，请重试')
        }
      )
    } catch (err) {
      console.error('Inspiration chat error:', err)
    } finally {
      setSending(false)
      abortRef.current = null
    }
  }

  const handleCancel = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setSending(false)
    if (streamingContent) {
      const partialMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: streamingContent,
        timestamp: Date.now(),
      }
      setMessages((prev) => [...prev, partialMsg])
      setStreamingContent('')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 标题 */}
      <div className="px-6 py-3 border-b bg-white flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium">创意孵化</span>
        <span className="text-[10px] text-muted-foreground">
          和智能体一起探索你的小说创意
        </span>
      </div>

      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !streamingContent && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Sparkles className="h-12 w-12 mb-4 text-muted-foreground/20" />
            <p className="text-sm mb-1">说说你的小说创意</p>
            <p className="text-xs text-muted-foreground/60">
              一句话、一段描述、甚至一个氛围都可以
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[70%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted/50 text-foreground'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* 流式输出 */}
        {streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-[70%] rounded-lg px-4 py-2.5 text-sm leading-relaxed bg-muted/50">
              {streamingContent}
              <span className="inline-block w-1 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" />
            </div>
          </div>
        )}
      </div>

      {/* 输入区 */}
      <div className="px-6 py-3 border-t bg-white">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            className="flex-1 border rounded-lg px-4 py-2.5 text-sm outline-none focus:border-primary"
            placeholder="描述你的小说创意..."
            disabled={sending}
          />
          {sending ? (
            <Button variant="outline" size="sm" onClick={handleCancel} className="gap-1.5">
              <Loader2 className="h-4 w-4 animate-spin" />
              取消
            </Button>
          ) : (
            <Button size="sm" onClick={handleSend} disabled={!input.trim()} className="gap-1.5">
              <Send className="h-4 w-4" />
              发送
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
