// frontend/src/components/workbench/AICompanionSidebar.tsx

import { useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'
import { sendAgentMessage } from '@/lib/agentApi'

export function AICompanionSidebar()
{
  const { id } = useParams()
  const projectId = parseInt(id || '0')
  const { aiSidebarOpen, toggleAiSidebar, addAiMessage } = useWorkbenchStore()
  const [sending, setSending] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-slate-950 border-l border-slate-800 flex flex-col items-center pt-3 gap-2">
        <button onClick={toggleAiSidebar} className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors" title="展开 AI 搭档">
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-slate-600 text-[10px]" style={{ writingMode: 'vertical-lr' }}>AI 搭档</span>
      </div>
    )
  }

  const handleSend = async (message: string) =>
  {
    // 添加用户消息
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })

    // 创建 AI 消息占位
    const assistantId = crypto.randomUUID()
    addAiMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      actions: [],
      timestamp: Date.now(),
    })

    setSending(true)
    const controller = new AbortController()
    abortRef.current = controller

    const { activeTab, activeMenuItem, aiMessages } = useWorkbenchStore.getState()

    // 构建历史消息（最近 10 轮，排除当前占位消息）
    const history = aiMessages
      .filter((m) => m.id !== assistantId)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }))

    try
    {
      await sendAgentMessage(projectId, message, {
        onAgentText: (content) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + content } : m
            ),
          }))
        },
        onToolStart: (tool, args) =>
        {
          const desc = _toolDescription(tool, args)
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? { ...m, actions: [...(m.actions || []), { tool, status: 'running' as const, description: desc }] }
                : m
            ),
          }))
        },
        onToolResult: (tool) =>
        {
          useWorkbenchStore.setState((state) =>
          {
            const msg = state.aiMessages.find((m) => m.id === assistantId)
            if (!msg?.actions) return state
            // 找到该 tool 最后一个 running 的 action
            const actionIdx = [...msg.actions].reverse().findIndex(
              (a) => a.tool === tool && a.status === 'running'
            )
            if (actionIdx === -1) return state
            const realIdx = msg.actions.length - 1 - actionIdx
            return {
              aiMessages: state.aiMessages.map((m) =>
                m.id === assistantId
                  ? { ...m, actions: m.actions?.map((a, i) => i === realIdx ? { ...a, status: 'done' as const } : a) }
                  : m
              ),
            }
          })
        },
        onAiUpdate: (module) =>
        {
          useWorkbenchStore.getState().addAiUpdateMarker(module)
          setTimeout(() =>
          {
            useWorkbenchStore.getState().clearAiUpdateMarker(module)
          }, 5 * 60 * 1000)
        },
        onAgentDone: () =>
        {
          setSending(false)
        },
        onError: (error) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content || `出错：${error}` } : m
            ),
          }))
          setSending(false)
        },
      }, {
        activeTab,
        activeMenuItem,
        history,
        signal: controller.signal,
      })
    }
    catch
    {
      setSending(false)
    }
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>
        </div>
        <button onClick={toggleAiSidebar} className="p-1 text-slate-500 hover:text-slate-300 transition-colors" title="折叠 AI 搭档">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* 聊天区 */}
      <AICompanionChat />

      {/* 输入区 */}
      <AICompanionInput onSend={handleSend} disabled={sending} />
    </div>
  )
}

/** 生成 tool 操作的可读描述 */
function _toolDescription(tool: string, args: Record<string, unknown>): string
{
  const map: Record<string, (args: Record<string, unknown>) => string> = {
    read_outline: () => '读取大纲',
    update_outline: () => '修改大纲',
    read_characters: () => '读取角色',
    update_character: (a) => `修改角色「${a.name || ''}」`,
    create_character: (a) => `新增角色「${a.name || ''}」`,
    read_chapter_outlines: () => '读取章节大纲',
    update_chapter_outline: () => '修改章节大纲',
  }
  return (map[tool] || (() => tool))(args)
}
