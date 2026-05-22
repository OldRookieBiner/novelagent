import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'

export function AICompanionSidebar()
{
  const { aiSidebarOpen, toggleAiSidebar, addAiMessage } = useWorkbenchStore()

  // 折叠状态
  if (!aiSidebarOpen)
  {
    return (
      <div className="w-10 bg-slate-950 border-l border-slate-800 flex flex-col items-center pt-3 gap-2">
        <button
          onClick={toggleAiSidebar}
          className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors"
          title="展开 AI 搭档"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <span className="text-slate-600 text-[10px] writing-vertical"
          style={{ writingMode: 'vertical-lr' }}
        >
          AI 搭档
        </span>
      </div>
    )
  }

  const handleSend = (message: string) =>
  {
    // MVP 阶段：仅添加用户消息到本地，后端连接在 Phase 3 实现
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
    })
    // 临时 AI 回复（占位，Phase 3 替换为真实 API 调用）
    setTimeout(() =>
    {
      addAiMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '收到！我正在思考如何帮你优化小说...',
        timestamp: Date.now(),
      })
    }, 500)
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>
        </div>
        <button
          onClick={toggleAiSidebar}
          className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
          title="折叠 AI 搭档"
        >
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* 聊天区 */}
      <AICompanionChat />

      {/* 输入区 */}
      <AICompanionInput onSend={handleSend} />
    </div>
  )
}
