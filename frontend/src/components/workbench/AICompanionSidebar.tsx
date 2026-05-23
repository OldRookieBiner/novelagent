// frontend/src/components/workbench/AICompanionSidebar.tsx

import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { PanelRightClose, PanelRightOpen, ChevronDown } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { AICompanionChat } from './AICompanionChat'
import { AICompanionInput } from './AICompanionInput'
import { sendAgentMessage } from '@/lib/agentApi'
import { modelConfigsApi } from '@/lib/api'
import type { ModelConfig } from '@/types'

export function AICompanionSidebar()
{
  const { id } = useParams()
  const projectId = parseInt(id || '0')
  const {
    aiSidebarOpen, toggleAiSidebar, addAiMessage,
    setIsAgentBusy,
  } = useWorkbenchStore()
  const workflowRunning = useWorkflowStore((s) => s.isRunning)
  const [sending, setSending] = useState(false)
  const activeTabFromStore = useWorkbenchStore((s) => s.activeTab)
  const [models, setModels] = useState<ModelConfig[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // 加载模型配置列表
  useEffect(() =>
  {
    modelConfigsApi.list().then((res) =>
    {
      const healthy = (res.models || []).filter((c: ModelConfig) => c.health_status === 'healthy')
      setModels(healthy)
      if (healthy.length > 0 && !selectedModelId)
      {
        setSelectedModelId(healthy[0].id)
      }
    }).catch(() => {})
  }, [])

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

  const disabled = sending || workflowRunning
  const disabledReason = workflowRunning
    ? '工作流运行中，Agent 暂不可用'
    : sending ? 'Agent 思考中...' : undefined

  const selectedModel = models.find((m) => m.id === selectedModelId)

  const handleSend = async (message: string) =>
  {
    addAiMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      segments: [],
      timestamp: Date.now(),
    })

    const assistantId = crypto.randomUUID()
    addAiMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      segments: [],
      actions: [],
      timestamp: Date.now(),
    })

    setSending(true)
    setIsAgentBusy(true)
    const controller = new AbortController()
    abortRef.current = controller

    const { activeTab, activeMenuItem, aiMessages } = useWorkbenchStore.getState()
    const selectedChapterNumber = (useWorkbenchStore.getState() as unknown as Record<string, unknown>).selectedChapterNumber as number | undefined

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
              m.id === assistantId
                ? {
                    ...m,
                    content: m.content + content,
                    segments: [...m.segments, { type: 'agent_text' as const, content }],
                  }
                : m
            ),
          }))
        },
        onToolStart: (tool, args) =>
        {
          const desc = _toolDescription(tool, args)
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    actions: [...(m.actions || []), {
                      tool,
                      status: 'running' as const,
                      description: desc,
                      args,
                    }],
                  }
                : m
            ),
          }))
        },
        onToolResult: (tool, result) =>
        {
          useWorkbenchStore.setState((state) =>
          {
            const msg = state.aiMessages.find((m) => m.id === assistantId)
            if (!msg?.actions) return state
            const actionIdx = [...msg.actions].reverse().findIndex(
              (a) => a.tool === tool && a.status === 'running'
            )
            if (actionIdx === -1) return state
            const realIdx = msg.actions.length - 1 - actionIdx
            return {
              aiMessages: state.aiMessages.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      actions: m.actions?.map((a, i) =>
                        i === realIdx
                          ? { ...a, status: 'done' as const, result }
                          : a
                      ),
                    }
                  : m
              ),
            }
          })
        },
        onChapterPreview: (data) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    segments: [...m.segments, {
                      type: 'chapter_preview' as const,
                      content: String(data.preview || ''),
                      data,
                    }],
                  }
                : m
            ),
          }))
        },
        onReview: (data) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    segments: [...m.segments, {
                      type: 'review' as const,
                      content: JSON.stringify(data),
                      data,
                    }],
                  }
                : m
            ),
          }))
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
          setIsAgentBusy(false)
        },
        onError: (error) =>
        {
          useWorkbenchStore.setState((state) => ({
            aiMessages: state.aiMessages.map((m) =>
              m.id === assistantId ? { ...m, content: m.content || `出错：${error}` } : m
            ),
          }))
          setSending(false)
          setIsAgentBusy(false)
        },
      }, {
        activeTab,
        activeMenuItem,
        currentChapterNumber: selectedChapterNumber || undefined,
        history,
        modelConfigId: selectedModelId || undefined,
        signal: controller.signal,
      })
    }
    catch
    {
      setSending(false)
      setIsAgentBusy(false)
    }
  }

  return (
    <div className="w-[340px] bg-slate-950 border-l border-slate-800 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-200">🤖 AI 搭档</span>
          <span className="text-[9px] px-1.5 py-0.5 bg-green-500/20 text-green-400 rounded">在线</span>

          {/* 模型选择器 */}
          <div className="relative">
            <button
              onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 px-1.5 py-0.5 rounded hover:bg-slate-800 transition-colors"
              title="选择模型"
            >
              <span className="max-w-[80px] truncate">{selectedModel?.name || '默认'}</span>
              <ChevronDown className="h-3 w-3" />
            </button>
            {modelDropdownOpen && models.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-48 bg-slate-800 border border-slate-700 rounded-md shadow-lg z-50 py-1 max-h-48 overflow-auto">
                {models.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { setSelectedModelId(m.id); setModelDropdownOpen(false) }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-700 transition-colors ${
                      m.id === selectedModelId ? 'text-emerald-400' : 'text-slate-300'
                    }`}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <button onClick={toggleAiSidebar} className="p-1 text-slate-500 hover:text-slate-300 transition-colors" title="折叠 AI 搭档">
          <PanelRightClose className="h-4 w-4" />
        </button>
      </div>

      {/* 聊天区 */}
      <AICompanionChat />

      {/* 输入区 */}
      <AICompanionInput
        onSend={handleSend}
        disabled={disabled}
        disabledReason={disabledReason}
        activeTab={activeTabFromStore}
      />
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
    read_relations: () => '读取人物关系',
    update_relations: () => '修改人物关系',
    generate_chapter_content: (a) => `生成第${a.chapter_number || '?'}章正文`,
    review_chapter: (a) => `审核第${a.chapter_number || '?'}章`,
    rewrite_chapter: (a) => `重写第${a.chapter_number || '?'}章`,
  }
  return (map[tool] || (() => tool))(args)
}
