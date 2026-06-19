// AgentChatPanel.tsx — Right panel: AI creation agent chat

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { PanelRightClose, PanelRightOpen, Send, AlertTriangle, ShieldCheck, ChevronDown, ChevronRight, Loader2, CheckCircle2, GripVertical, Square, History, Plus, Copy, Check } from 'lucide-react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { sendAgentMessage, fetchConversation, createConversation } from '@/lib/agentApi'
import { modelConfigsApi, settingsApi } from '@/lib/api'
import type { AiMessage, AiMessageSegment, ImpactReport, AgentWarning } from '@/stores/workbenchStore'
import type { ModelConfig, ModelItem } from '@/types'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ConversationHistoryDialog } from './ConversationHistoryDialog'

/** 截取前 max 个 grapheme cluster（安全处理 emoji/组合字符）作为消息标题 */
export function truncateTitle(content: string, max = 15): string
{
  const cleaned = content.replace(/\s+/g, ' ').trim()
  if (!cleaned) return '(空消息)'
  const chars = Array.from(cleaned)
  if (chars.length <= max) return cleaned
  return chars.slice(0, max).join('') + '…'
}

/** 毫秒数格式化：< 1s 显示 ms，>= 1s 显示 1 位小数 s */
function formatDuration(ms: number): string
{
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

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

/** 工具名到人类可读标签的映射 */
const TOOL_LABELS: Record<string, string> = {
  // Perception
  knowledge_search: '搜索知识库',
  foreshadowing_check: '检查伏笔状态',
  style_analysis: '风格分析',
  progress_report: '生成进度报告',
  rhythm_analysis: '节奏分析',
  // Generation (new!)
  generate_outline: '生成大纲',
  generate_chapter_content: '写章节',
  generate_story_seed: '生成故事种子',
  generate_world_setting_complete: '生成完整世界观',
  // Modification
  propose_setting_change: '评估设定变更影响',
  propose_outline_adjustment: '评估结构调整影响',
  propose_chapter_rewrite: '评估重写影响',
  // Creation assist
  advance_phase: '推进阶段',
  expand_world_setting: '扩展世界观',
  consistency_scan: '一致性扫描',
  suggest_writing_direction: '建议写作方向',
  // Creation
  create_world_setting: '创建世界观',
  create_character: '创建角色',
  create_style_constraints: '创建风格约束',
  create_foreshadowing: '创建伏笔',
  create_relation: '创建关系',
  create_evolution_plan: '创建演变规划',
  create_subplot: '创建支线',
  create_plot_question: '创建情节问题',
  create_plot_block: '创建情节块',
  generate_chapter_outline: '生成章节大纲',
  review_chapter: '审阅章节',
  rewrite_chapter: '重写章节',
  record_chapter_meta: '记录章节追踪',
  delete_plot_block: '删除情节块',
  apply_change: '应用变更',
  reject_change: '拒绝变更',
  list_proposed_changes: '列出变更提案',
  report_progress: '报告进度',
}

/** 根据 create_* 工具的返回值判断显示"创建"还是"更新"
 *  当 result 包含 updated_fields 或 changes 时，显示"更新"否则"创建"
 */
function getToolLabel(toolName: string, result?: Record<string, unknown>): string {
  const baseLabels: Record<string, string> = {
    create_character: '角色',
    create_foreshadowing: '伏笔',
    create_plot_block: '情节块',
    create_subplot: '支线',
    create_plot_question: '情节问题',
  }
  if (baseLabels[toolName] && result) {
    const isUpdate = 'updated_fields' in result || 'changes' in result
    return isUpdate ? `更新${baseLabels[toolName]}` : `创建${baseLabels[toolName]}`
  }
  return TOOL_LABELS[toolName] || toolName
}

/** 判断 segments 中是否包含 agent_text 段（用于区分新/旧格式） */
function hasTextSegments(segments: AiMessageSegment[]): boolean
{
  return segments.some(s => s.type === 'agent_text')
}

/** 工具调用分组（用于折叠连续相同工具调用） */
interface ToolGroup {
  type: 'tool_group'
  toolName: string
  count: number
  items: Array<{
    status: 'running' | 'done'
    args?: Record<string, unknown>
    result?: Record<string, unknown>
  }>
}

/**
 * 合并连续相同工具调用为 tool_group
 * 将连续的 tool_start + tool_result 对（相同工具名）合并为一个分组
 */
function mergeToolGroups(
  parts: Array<{ type: 'text'; content: string } | AiMessageSegment>
): Array<{ type: 'text'; content: string } | AiMessageSegment | ToolGroup>
{
  const result: Array<{ type: 'text'; content: string } | AiMessageSegment | ToolGroup> = []
  let i = 0
  
  while (i < parts.length)
  {
    const part = parts[i]
    
    // 如果是 tool_start，检查后续是否有对应的 tool_result
    if (part.type === 'tool_start')
    {
      const toolName = (part.data?.tool as string) || part.content.replace('...', '')
      const collected: Array<{ start: typeof part; result?: typeof part }> = []
      
      // 收集连续的相同工具调用（tool_start + tool_result 对）
      while (i < parts.length)
      {
        const curr = parts[i]
        
        if (curr.type === 'tool_start')
        {
          const currToolName = (curr.data?.tool as string) || curr.content.replace('...', '')
          if (currToolName === toolName)
          {
            collected.push({ start: curr })
            i++
          }
          else
          {
            break
          }
        }
        else if (curr.type === 'tool_result' && collected.length > 0 && !collected[collected.length - 1].result)
        {
          collected[collected.length - 1].result = curr
          i++
        }
        else
        {
          break
        }
      }
      
      // 只有多个调用才折叠
      if (collected.length > 1)
      {
        result.push({
          type: 'tool_group',
          toolName,
          count: collected.length,
          items: collected.map(c => ({
            status: c.result ? 'done' as const : 'running' as const,
            args: c.start.data?.args as Record<string, unknown> | undefined,
            result: c.result?.data?.result as Record<string, unknown> | undefined,
          })),
        })
      }
      else if (collected.length === 1)
      {
        // 只有一个，保持原样
        result.push(collected[0].start)
        if (collected[0].result)
        {
          result.push(collected[0].result)
        }
      }
      continue
    }
    
    result.push(part)
    i++
  }
  
  return result
}

/**
 * 按顺序渲染 assistant 消息内容
 * 新格式：segments 中有 agent_text 段，按 segments 顺序渲染
 * 旧格式：segments 中只有 tool 段，content 字段包含全部文本
 */
/** 内部实现：共享渲染逻辑 */
function AssistantMessageContentInner({
  msg,
  isStreaming,
}: {
  msg: AiMessage
  isStreaming: boolean
})
{
  const showThinking = isStreaming
  const useNewFormat = hasTextSegments(msg.segments)

  // 旧格式兼容：没有 agent_text segment 时，先渲染 content 再渲染 tool 段
  if (!useNewFormat)
  {
    return (
      <>
        {msg.content
          ? <div className="agent-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown></div>
          : showThinking ? null : null}
        {msg.segments.filter(s => s.type === 'tool_result').map((s, i) => (
          <div key={`tool-${i}`} className="mt-1.5 text-[10px] text-muted-foreground flex items-center gap-1 border-t border-gray-100 pt-1">
            <CheckCircle2 className="h-3 w-3 shrink-0 text-green-500" />
            <span>{s.content}</span>
          </div>
        ))}
        {showThinking && <ThinkingIndicator />}
      </>
    )
  }

  // 新格式：按 segments 顺序渲染
  // 合并相邻的 agent_text 段，减少 Markdown 渲染碎片
  const mergedParts: Array<{ type: 'text'; content: string } | AiMessageSegment> = []
  let textBuffer = ''

  for (const seg of msg.segments)
  {
    if (seg.type === 'agent_text')
    {
      textBuffer += seg.content
    }
    else
    {
      if (textBuffer)
      {
        mergedParts.push({ type: 'text', content: textBuffer })
        textBuffer = ''
      }
      mergedParts.push(seg)
    }
  }
  if (textBuffer)
  {
    mergedParts.push({ type: 'text', content: textBuffer })
  }

  // 二次合并：折叠连续相同工具调用
  const finalParts = mergeToolGroups(mergedParts)

  // 展开/折叠状态
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set())

  const toggleGroup = (index: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  return (
    <>
      {finalParts.map((part, i) => {
        if (part.type === 'text')
        {
          return (
            <div key={`text-${i}`} className="agent-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{part.content}</ReactMarkdown>
            </div>
          )
        }
        // AiMessageSegment
        const seg = part as AiMessageSegment
        if (seg.type === 'tool_start')
        {
          return (
            <div key={`ts-${i}`} className="mt-1.5 text-[10px] text-muted-foreground flex items-center gap-1">
              <Loader2 className="h-3 w-3 shrink-0 animate-spin text-blue-400" />
              <span>{seg.content}</span>
            </div>
          )
        }
        if (seg.type === 'tool_result')
        {
          return (
            <div key={`tr-${i}`} className="mt-1 text-[10px] text-muted-foreground flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 shrink-0 text-green-500" />
              <span>{seg.content}</span>
            </div>
          )
        }
        if (seg.type === 'progress')
        {
          const percent = (seg.data?.percent as number) || 0
          return (
            <div key={`prog-${i}`} className="mt-1.5 flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-blue-400 rounded-full transition-all" style={{ width: `${percent}%` }} />
              </div>
              <span className="text-[10px] text-muted-foreground shrink-0">{seg.content}</span>
            </div>
          )
        }
        // tool_group: 折叠的连续相同工具调用
        if ((seg as any).type === 'tool_group')
        {
          const group = seg as any as ToolGroup
          const isExpanded = expandedGroups.has(i)
          // 获取第一个有结果的项目来判断是创建还是更新
          const firstWithResult = group.items.find(item => item.result)
          const label = getToolLabel(group.toolName, firstWithResult?.result)
          
          return (
            <div key={`tg-${i}`} className="mt-1.5">
              <button
                onClick={() => toggleGroup(i)}
                className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="h-3 w-3 shrink-0" />
                ) : (
                  <ChevronRight className="h-3 w-3 shrink-0" />
                )}
                <CheckCircle2 className="h-3 w-3 shrink-0 text-green-500" />
                <span>{label}</span>
                <span className="text-primary font-medium">×{group.count}</span>
              </button>
              {isExpanded && (
                <div className="ml-4 mt-1 space-y-0.5">
                  {group.items.map((item, j) => (
                    <div key={j} className="text-[9px] text-muted-foreground flex items-center gap-1">
                      {item.status === 'running' ? (
                        <>
                          <Loader2 className="h-2.5 w-2.5 shrink-0 animate-spin text-blue-400" />
                          <span>调用 {j + 1}</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-2.5 w-2.5 shrink-0 text-green-500" />
                          <span>调用 {j + 1} 完成</span>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        }
        return null
      })}
      {showThinking && <ThinkingIndicator />}
    </>
  )
}

/** 已完成消息 — React.memo 有效（props 稳定） */
const CompletedAssistantMessage = React.memo(function CompletedAssistantMessage({
  msg,
}: {
  msg: AiMessage
})
{
  return (
    <>
      <AssistantMessageContentInner msg={msg} isStreaming={false} />
      {msg.content && msg.durationMs !== undefined && (
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-1.5">
          <CopyButton content={msg.content} ariaLabel="复制回复内容" />
          <span>用时 {formatDuration(msg.durationMs)}</span>
        </div>
      )}
    </>
  )
})

/** 流式中消息 — 不 memo */
function StreamingAssistantMessage({ msg }: { msg: AiMessage })
{
  return <AssistantMessageContentInner msg={msg} isStreaming={true} />
}

/** 思考中指示器 */
function ThinkingIndicator()
{
  return (
    <div className="flex items-center gap-1.5 mt-1.5 text-[10px] text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
      <span>思考中...</span>
    </div>
  )
}

/** 通用复制按钮：成功显示 Check 1.5s 后还原。带 clipboard.writeText 失败 fallback */
function CopyButton({
  content,
  className,
  ariaLabel,
}: {
  content: string
  className?: string
  ariaLabel?: string
})
{
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const showSuccess = () =>
    {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }

    try
    {
      if (navigator.clipboard && navigator.clipboard.writeText)
      {
        await navigator.clipboard.writeText(content)
        showSuccess()
        return
      }
      throw new Error('clipboard unavailable')
    }
    catch
    {
      // fallback：execCommand
      try
      {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.style.position = 'fixed'
        ta.style.left = '-9999px'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        if (ok) showSuccess()
      }
      catch
      {
        // 静默失败
      }
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={cn('text-muted-foreground hover:text-foreground transition-colors', className)}
      aria-label={ariaLabel || '复制'}
      title="复制"
      type="button"
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}

export function AgentChatPanel() {
  const {
    currentProjectId,
    aiSidebarOpen,
    toggleAiSidebar,
    aiMessages,
    addAiMessage,
    updateAiMessage,
    setAiMessages,
    pendingImpacts,
    addPendingImpact,
    removePendingImpact,
    agentWarnings,
    addAgentWarning,
    isAgentSending,
    setIsAgentSending,
    incrementKnowledgeVersion,
  } = useWorkbenchStore()

  const phase = useWorkbenchStore((s) => s.phase)
  const { setActiveConversationId } = useWorkbenchStore()

  // Task 3: 会话历史对话框状态
  const [showConversationHistory, setShowConversationHistory] = useState(false)

  // 面板宽度状态
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem('agentPanelWidth')
    if (saved) {
      const parsed = parseInt(saved, 10)
      const maxW = Math.floor(window.innerWidth / 2)
      return Math.min(parsed, maxW)
    }
    return 400
  })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartX = useRef(0)
  const dragStartWidth = useRef(0)

  // 输入框行数（用于自动增高）
  const [inputRows, setInputRows] = useState(1)

  const [input, setInput] = useState('')
  // 模型配置列表（平台级）
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  // 当前选中的平台 ID
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null)
  // 当前选中的子模型名（ModelItem.id）
  const [selectedModelName, setSelectedModelName] = useState<string | null>(null)
  // 展开的平台 ID（用于显示子模型列表）
  const [expandedConfigId, setExpandedConfigId] = useState<number | null>(null)
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [modelsLoaded, setModelsLoaded] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const modelSelectorRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Task 2: 滚动管理
  const skipAutoScrollRef = useRef(false)
  const isLoadingMoreRef = useRef(false)
  const prevScrollHeightRef = useRef(0)
  // 用户消息 DOM 引用 Map：Task 2 用于复制按钮 ref 回调，Task 6 复用做锚点跳转 + 当前位置判定
  const userMessageRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const historyIndexRef = useRef<number>(-1)
  const draftRef = useRef<string>('')

  /** 重置历史导航到草稿态（发送、切换会话、新建会话、加载历史 effect 共用） */
  const resetInputHistory = useCallback(() =>
  {
    historyIndexRef.current = -1
    draftRef.current = ''
  }, [])

  // Task 14: SSE 文本缓冲 — 合并高频 chunk 后统一更新
  const textBufferRef = useRef<{
    id: string
    chunks: string[]
    timer: ReturnType<typeof setTimeout> | null
  }>({ id: '', chunks: [], timer: null })

  // 计算最小/最大宽度
  const minWidth = 400
  const maxWidth = Math.floor(window.innerWidth / 2)

  // 找到最后一条 assistant 消息的 id
  const lastAssistantId = aiMessages.reduce<string | null>((acc, m) =>
    m.role === 'assistant' ? m.id : acc, null)

  // 鼠标事件处理器
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    dragStartX.current = e.clientX
    dragStartWidth.current = panelWidth
  }, [panelWidth])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return
    const deltaX = dragStartX.current - e.clientX
    const newWidth = dragStartWidth.current + deltaX
    // 限制在最小和最大宽度之间
    const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))
    setPanelWidth(clampedWidth)
  }, [isDragging, maxWidth])

  const handleMouseUp = useCallback(() => {
    localStorage.setItem('agentPanelWidth', String(panelWidth))
    setIsDragging(false)
  }, [panelWidth])

  // 拖拽事件监听
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // 自动滚动到底部（加载历史消息时恢复位置而非滚底）
  useEffect(() => {
    if (skipAutoScrollRef.current)
    {
      skipAutoScrollRef.current = false
      if (scrollRef.current && prevScrollHeightRef.current > 0)
      {
        const newScrollHeight = scrollRef.current.scrollHeight
        scrollRef.current.scrollTop = newScrollHeight - prevScrollHeightRef.current
        prevScrollHeightRef.current = 0
      }
      return
    }
    if (scrollRef.current)
    {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [aiMessages, pendingImpacts])

  // 根据输入内容自动调整 textarea 行数
  useEffect(() => {
    const lines = input.split('\n').length
    // 限制行数：最少1行，最多根据窗口高度计算（约 50vh / 20px 每行 ≈ 27 行）
    const maxRows = Math.floor((window.innerHeight * 0.5) / 20)
    const newRows = Math.min(Math.max(lines, 1), maxRows)
    setInputRows(newRows)
  }, [input])
  // ESC 键监听：连续按两次终止生成
  useEffect(() => {
    let escPressCount = 0
    let escTimer: ReturnType<typeof setTimeout> | null = null

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') {
        escPressCount = 0
        return
      }

      escPressCount++
      
      // 清除之前的计时器
      if (escTimer) clearTimeout(escTimer)

      if (escPressCount === 1) {
        // 第一次按 ESC，1秒内按第二次才终止
        escTimer = setTimeout(() => {
          escPressCount = 0
        }, 1000)
      } else if (escPressCount >= 2) {
        // 连续按两次 ESC，终止生成
        escPressCount = 0
        if (isAgentSending && abortRef.current) {
          abortRef.current.abort()
          setIsAgentSending(false)
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (escTimer) clearTimeout(escTimer)
    }
  }, [isAgentSending])
  // 加载模型配置列表（仅一次），并恢复后端保存的模型选择
  useEffect(() => {
    if (modelsLoaded) return
    Promise.all([
      modelConfigsApi.list(),
      settingsApi.get().catch(() => null),
    ]).then(([res, settings]) => {
      const enabled = res.models.filter((m: ModelConfig) => m.is_enabled)
      setModelConfigs(enabled)

      // 优先恢复后端保存的模型选择
      if (settings?.agent_model_config_id) {
        const savedConfig = enabled.find((m: ModelConfig) => m.id === settings.agent_model_config_id)
        if (savedConfig) {
          setSelectedConfigId(savedConfig.id)
          if (settings.agent_model_name) {
            setSelectedModelName(settings.agent_model_name)
          } else if (savedConfig.model_name) {
            setSelectedModelName(savedConfig.model_name)
          }
          setModelsLoaded(true)
          return
        }
      }

      // 查找默认配置，无则取第一个启用的
      const defaultConfig = enabled.find((m: ModelConfig) => m.is_default) || enabled[0]
      if (defaultConfig) {
        setSelectedConfigId(defaultConfig.id)
        const hasModels = (defaultConfig.models?.filter((mi: ModelItem) => mi.is_enabled) ?? []).length > 0
        if (hasModels) {
          const firstEnabled = defaultConfig.models!.find((mi: ModelItem) => mi.is_enabled)
          if (firstEnabled) {
            setSelectedModelName(firstEnabled.id)
          }
        } else if (defaultConfig.model_name) {
          setSelectedModelName(defaultConfig.model_name)
        }
      }
      setModelsLoaded(true)
    }).catch(() => {
      setModelsLoaded(true)
    })
  }, [modelsLoaded])

  // 加载后端保存的聊天记录（项目切换时重新加载）
  useEffect(() => {
    if (!currentProjectId) return
    fetchConversation(currentProjectId).then((res) => {
      const loaded: AiMessage[] = res.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        segments: (m.segments || []).map((s) => ({
          type: (s.type as any) || "agent_text",
          content: s.content || "",
          data: s.data,
        })),
        timestamp: m.timestamp,
      }))
      setAiMessages(loaded)
      resetInputHistory()
    }).catch(() => {
      // 会话可能尚未创建，保持空数组
    })
  }, [currentProjectId, setAiMessages])

  // Task 2: 加载更多历史消息（向上滚动时触发）
  const loadMoreMessages = useCallback(async () => {
    if (!currentProjectId || aiMessages.length === 0) return
    if (isLoadingMoreRef.current) return
    const oldestId = aiMessages[0]?.id
    if (!oldestId) return

    isLoadingMoreRef.current = true
    prevScrollHeightRef.current = scrollRef.current?.scrollHeight ?? 0

    try
    {
      const res = await fetchConversation(currentProjectId, undefined, 30, parseInt(oldestId))
      if (res.messages.length === 0) return

      const older: AiMessage[] = res.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        segments: (m.segments || []).map((s) => ({
          type: (s.type as any) || "agent_text",
          content: s.content || "",
          data: s.data,
        })),
        timestamp: m.timestamp,
      }))

      const existingIds = new Set(aiMessages.map((m) => m.id))
      const newMessages = older.filter((m) => !existingIds.has(m.id))
      if (newMessages.length > 0)
      {
        skipAutoScrollRef.current = true
        setAiMessages([...newMessages, ...aiMessages])
      }
    }
    catch
    {
      // 静默失败
    }
    finally
    {
      isLoadingMoreRef.current = false
    }
  }, [currentProjectId, aiMessages, setAiMessages])

  // Task 2: 检测滚动到顶部
  const handleMessagesScroll = useCallback(() => {
    if (!scrollRef.current) return
    if (scrollRef.current.scrollTop < 50)
    {
      loadMoreMessages()
    }
  }, [loadMoreMessages])

  // Task 14: flush 文本缓冲
  const flushTextBuffer = useCallback(() => {
    const buf = textBufferRef.current
    if (!buf.chunks.length) return

    const combined = buf.chunks.join('')
    buf.chunks = []
    buf.timer = null

    updateAiMessage(buf.id, (m) => ({
      ...m,
      content: m.content + combined,
      segments: [...m.segments, {
        type: 'agent_text' as const,
        content: combined,
        data: undefined,
      }],
    }))
  }, [updateAiMessage])

  // Task 3: 切换会话（对话框已完成 activate，此处只加载消息）
  const handleSwitchConversation = useCallback(async (conv: { id: number }) => {
    if (!currentProjectId) return
    setActiveConversationId(conv.id)
    resetInputHistory()
    try
    {
      const res = await fetchConversation(currentProjectId, conv.id)
      const loaded: AiMessage[] = res.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        segments: (m.segments || []).map((s) => ({
          type: (s.type as any) || "agent_text",
          content: s.content || "",
          data: s.data,
        })),
        timestamp: m.timestamp,
      }))
      setAiMessages(loaded)
    }
    catch
    {
      // 会话切换失败，保持当前消息
    }
  }, [currentProjectId, setActiveConversationId, setAiMessages])

  // Task 3: 新建会话
  const handleNewConversation = useCallback(async () => {
    if (!currentProjectId || isAgentSending) return
    try
    {
      const conv = await createConversation(currentProjectId)
      setActiveConversationId(conv.id)
      setAiMessages([])
      resetInputHistory()
    }
    catch
    {
      // 可能 busy lock 冲突或其他错误
    }
  }, [currentProjectId, isAgentSending, setActiveConversationId, setAiMessages, resetInputHistory])

  // 模型选择器 click-outside 关闭
  useEffect(() => {
    if (!modelSelectorOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (modelSelectorRef.current && !modelSelectorRef.current.contains(e.target as Node)) {
        setModelSelectorOpen(false)
        setExpandedConfigId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [modelSelectorOpen])

  // 选择平台（有子模型则展开，否则直接确定）
  const handleSelectConfig = (config: ModelConfig) => {
    setSelectedConfigId(config.id)
    const hasModels = (config.models?.filter((mi: ModelItem) => mi.is_enabled) ?? []).length > 0
    if (hasModels) {
      // 有子模型：展开列表
      setExpandedConfigId(expandedConfigId === config.id ? null : config.id)
      const firstEnabled = config.models!.find((mi: ModelItem) => mi.is_enabled)
      if (firstEnabled) {
        setSelectedModelName(firstEnabled.id)
        persistModelSelection(config.id, firstEnabled.id)
      } else {
        setSelectedModelName(null)
      }
    } else {
      // 无子模型：直接用配置的 model_name
      setSelectedModelName(config.model_name || null)
      persistModelSelection(config.id, config.model_name || null)
      setModelSelectorOpen(false)
      setExpandedConfigId(null)
    }
  }

  // 选择子模型
  const handleSelectSubModel = (configId: number, modelItem: ModelItem) => {
    setSelectedConfigId(configId)
    setSelectedModelName(modelItem.id)
    persistModelSelection(configId, modelItem.id)
    setModelSelectorOpen(false)
    setExpandedConfigId(null)
  }

  // 获取当前显示的模型名称
  const getDisplayModelName = (): string => {
    if (!selectedConfigId) return '未选择模型'
    const config = modelConfigs.find((c) => c.id === selectedConfigId)
    if (!config) return '未选择模型'
    const hasModels = (config.models?.filter((mi: ModelItem) => mi.is_enabled) ?? []).length > 0
    if (hasModels && selectedModelName) {
      const sub = config.models?.find((mi: ModelItem) => mi.id === selectedModelName)
      if (sub) return sub.name
    }
    if (config.model_name) return config.model_name
    return config.name
  }

  // 持久化模型选择到后端
  const persistModelSelection = (configId: number, modelName: string | null) => {
    settingsApi.update({
      agent_model_config_id: configId,
      agent_model_name: modelName,
    }).catch(() => {
      // 持久化失败不影响使用
    })
  }

  // SSE chat handler — 使用 agentApi
  const handleSend = useCallback(async () => {
    if (!input.trim() || !currentProjectId || isAgentSending) return

    // 重置历史导航状态
    resetInputHistory()

    // 确保上一条消息的文本缓冲已刷新
    flushTextBuffer()

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
    setInputRows(1)
    setIsAgentSending(true)

    const sendStartedAt = Date.now()
    const assistantMsg: AiMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      segments: [],
      timestamp: sendStartedAt,
      startedAt: sendStartedAt,
    }
    addAiMessage(assistantMsg)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await sendAgentMessage(
        currentProjectId,
        messageText,
        {
          // 文本片段：缓冲后批量更新（50ms 防抖）
          onAgentText: (content) => {
            const buf = textBufferRef.current
            buf.id = assistantMsg.id
            buf.chunks.push(content)
            if (buf.timer) clearTimeout(buf.timer)
            buf.timer = setTimeout(flushTextBuffer, 50)
          },
          onToolStart: (tool, args) => {
            flushTextBuffer()
            updateAiMessage(assistantMsg.id, (m) => ({
              ...m,
              segments: [...m.segments, {
                type: 'tool_start' as const,
                content: `${TOOL_LABELS[tool] || tool}...`,
                data: { tool, args },
              }],
            }))
          },
          onToolResult: (tool, result) => {
            flushTextBuffer()
            updateAiMessage(assistantMsg.id, (m) => ({
              ...m,
              segments: [...m.segments, {
                type: 'tool_result' as const,
                content: `${TOOL_LABELS[tool] || tool} 完成`,
                data: { tool, result },
              }],
            }))
            // advance_phase 工具推进阶段后同步前端状态
            if (tool === 'advance_phase' && result?.advanced && result?.suggested_phase) {
              useWorkbenchStore.getState().setPhase(result.suggested_phase as any)
            }
          },
          onImpactAssessment: (data) => {
            addPendingImpact(data as unknown as ImpactReport)
          },
          onWarning: (data) => {
            addAgentWarning(data as unknown as AgentWarning)
          },
          onAgentProgress: (data) => {
            flushTextBuffer()
            updateAiMessage(assistantMsg.id, (m) => ({
              ...m,
              segments: [
                ...m.segments.filter(s => s.type !== 'progress'),
                {
                  type: 'progress' as const,
                  content: data.progress_message,
                  data: { percent: data.progress_percent },
                },
              ],
            }))
          },
          onAgentDone: () => {
            flushTextBuffer()
            const durationMs = Date.now() - sendStartedAt
            updateAiMessage(assistantMsg.id, (m) => ({
              ...m,
              durationMs,
            }))
            incrementKnowledgeVersion()
          },
          onError: (error) => {
            flushTextBuffer()
            const durationMs = Date.now() - sendStartedAt
            updateAiMessage(assistantMsg.id, (m) => ({
              ...m,
              content: m.content || `错误：${error}`,
              segments: m.content ? m.segments : [...m.segments, {
                type: 'agent_text' as const,
                content: `错误：${error}`,
                data: undefined,
              }],
              durationMs,
            }))
          },
        },
        {
          modelConfigId: selectedConfigId ?? undefined,
          modelName: selectedModelName ?? undefined,
          signal: controller.signal,
        }
      )
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        const durationMs = Date.now() - sendStartedAt
        updateAiMessage(assistantMsg.id, (m) => ({
          ...m,
          content: m.content || `连接错误：${err.message}`,
          segments: m.content ? m.segments : [...m.segments, {
            type: 'agent_text' as const,
            content: `连接错误：${err.message}`,
            data: undefined,
          }],
          durationMs,
        }))
      } else {
        // AbortError: 用户主动停止，记录耗时
        flushTextBuffer()
        const durationMs = Date.now() - sendStartedAt
        updateAiMessage(assistantMsg.id, (m) => ({
          ...m,
          durationMs,
        }))
      }
    } finally {
      setIsAgentSending(false)
      abortRef.current = null
    }
  }, [input, currentProjectId, isAgentSending, selectedConfigId, selectedModelName, addAiMessage, updateAiMessage, addPendingImpact, addAgentWarning, setIsAgentSending])

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

  // 输入框键盘事件处理
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 中文输入法 composition 期间不响应任何快捷键
    if (e.nativeEvent.isComposing) return

    // ↑/↓ 历史导航（仅当光标在首行/末行）
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown')
    {
      const textarea = e.currentTarget
      const cursorPos = textarea.selectionStart
      const beforeCursor = textarea.value.slice(0, cursorPos)
      const afterCursor = textarea.value.slice(cursorPos)

      if (e.key === 'ArrowUp' && beforeCursor.includes('\n')) return
      if (e.key === 'ArrowDown' && afterCursor.includes('\n')) return

      const userMessages = aiMessages.filter(m => m.role === 'user')
      if (userMessages.length === 0) return

      e.preventDefault()
      const msgs = userMessages.map(m => m.content)

      if (e.key === 'ArrowUp')
      {
        if (historyIndexRef.current === -1)
        {
          // 进入历史：保存当前草稿
          draftRef.current = input
          historyIndexRef.current = 0
        }
        else
        {
          historyIndexRef.current = Math.min(msgs.length - 1, historyIndexRef.current + 1)
        }
        setInput(msgs[msgs.length - 1 - historyIndexRef.current])
      }
      else
      {
        // ArrowDown
        if (historyIndexRef.current === -1) return // 已经是草稿态
        historyIndexRef.current -= 1
        if (historyIndexRef.current < 0)
        {
          // 先恢复草稿到输入框，再清空 ref —— setInput 在调用瞬间快照 draftRef.current，之后清空不影响
          setInput(draftRef.current)
          resetInputHistory()
        }
        else
        {
          setInput(msgs[msgs.length - 1 - historyIndexRef.current])
        }
      }
      return
    }

    // Enter 发送（保留原行为）
    if (e.key === 'Enter' && !e.shiftKey)
    {
      e.preventDefault()
      handleSend()
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

  return (
    <div className="flex">
      {/* 拖拽手柄 */}
      <div
        className={cn(
          'w-1 cursor-col-resize flex-shrink-0 bg-transparent hover:bg-primary/30 transition-colors flex items-center justify-center',
          isDragging && 'bg-primary/50'
        )}
        onMouseDown={handleMouseDown}
      >
        <GripVertical className={cn('h-4 text-gray-300', isDragging && 'text-primary')} />
      </div>

      {/* 主面板 */}
      <div
        className="bg-white border-l border-gray-200 flex flex-col flex-shrink-0"
        style={{ width: panelWidth }}
      >
        {/* Header */}
        <div className="px-3 py-2.5 border-b border-gray-100 flex items-center gap-2">
          <span className="font-semibold text-sm">✦ 智能体</span>
          <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            {PHASE_LABELS[phase] || '未知'}
          </span>
          <div className={`w-1.5 h-1.5 rounded-full ${isAgentSending ? 'bg-amber-500 animate-pulse' : 'bg-green-500'}`} />
          <button
            onClick={handleNewConversation}
            disabled={isAgentSending}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-30"
            title="新建会话"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setShowConversationHistory(true)}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="会话历史"
          >
            <History className="h-3.5 w-3.5" />
          </button>
          <div className="ml-auto" />
          <button
            onClick={toggleAiSidebar}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <PanelRightClose className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* 模型选择器（两级：平台 → 子模型） */}
        <div className="px-3 py-1.5 border-b border-gray-50" ref={modelSelectorRef}>
          <div className="relative">
            <button
              onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
              className="w-full flex items-center justify-between gap-1 rounded border border-gray-200 px-2 py-1 text-[10px] text-foreground hover:border-gray-300 transition-colors"
            >
              <span className="truncate">{getDisplayModelName()}</span>
              <ChevronDown className="h-3 w-3 shrink-0 text-gray-400" />
            </button>
            {modelSelectorOpen && (
              <div className="absolute left-0 right-0 top-full mt-0.5 bg-white border border-gray-200 rounded shadow-sm z-10 max-h-56 overflow-y-auto">

                {/* 平台列表 + 子模型 */}
                {modelConfigs.map((config) => {
                  const isSelected = selectedConfigId === config.id
                  const isExpanded = expandedConfigId === config.id
                  const hasSubModels = (config.models?.filter((mi) => mi.is_enabled) ?? []).length > 0
                  const isSingleSelected = isSelected && !hasSubModels

                  return (
                    <div key={config.id}>
                      {/* 平台行 */}
                      <button
                        onClick={() => handleSelectConfig(config)}
                        className={cn(
                          'w-full text-left px-2 py-1.5 text-[10px] hover:bg-muted/50 flex items-center gap-1',
                          isSingleSelected && 'text-primary font-medium'
                        )}
                      >
                        {hasSubModels && (
                          <ChevronRight
                            className={cn('h-3 w-3 shrink-0 transition-transform', isExpanded && 'rotate-90')}
                          />
                        )}
                        <span className="truncate">{config.name}</span>
                        {config.is_default && <span className="ml-auto text-muted-foreground">(默认)</span>}
                      </button>
                      {/* 子模型列表 */}
                      {hasSubModels && isExpanded && config.models!.filter((mi) => mi.is_enabled).map((mi) => (
                        <button
                          key={mi.id}
                          onClick={(e) => { e.stopPropagation(); handleSelectSubModel(config.id, mi) }}
                          className={cn(
                            'w-full text-left pl-7 pr-2 py-1 text-[10px] hover:bg-muted/50 flex items-center gap-1',
                            selectedConfigId === config.id && selectedModelName === mi.id && 'text-primary font-medium'
                          )}
                        >
                          <span className="truncate">{mi.name}</span>
                          {mi.health_status === 'healthy' && (
                            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                          )}
                          {mi.health_status && mi.health_status !== 'healthy' && (
                            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  )
                })}
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
        <div ref={scrollRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
          {aiMessages.length === 0 && (
            <div className="text-center text-muted-foreground text-xs py-8">
              {PHASE_EMPTY_HINTS[phase] || '和智能体讨论你的创作想法'}
            </div>
          )}
          {aiMessages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                msg.role === 'user' ? 'flex justify-end' : ''
              )}
            >
              {msg.role === 'user' ? (
                <div
                  ref={(el) => {
                    if (el) userMessageRefs.current.set(msg.id, el)
                    else userMessageRefs.current.delete(msg.id)
                  }}
                  className="group flex flex-col items-end"
                >
                  <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed max-w-[80%] bg-secondary text-secondary-foreground selection:bg-primary/25 selection:text-foreground">
                    {msg.content}
                  </div>
                  <CopyButton
                    content={msg.content}
                    className="opacity-0 group-hover:opacity-100 mt-0.5"
                    ariaLabel="复制用户消息"
                  />
                </div>
              ) : (
                <div className="text-[11px] leading-relaxed text-foreground">
                  {msg.id === lastAssistantId && isAgentSending ? (
                    <StreamingAssistantMessage msg={msg} />
                  ) : (
                    <CompletedAssistantMessage msg={msg} />
                  )}
                </div>
              )}
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
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              rows={inputRows}
              className="flex-1 border border-gray-200 rounded-md px-2.5 py-1.5 text-[11px] outline-none focus:border-primary resize-none"
              placeholder={isAgentSending ? '思考中...（按 Esc x2 终止）' : '输入消息...（Shift+Enter 换行）'}
              style={{ maxHeight: '50vh', minHeight: '36px' }}
            />
            <button
              onClick={() => isAgentSending ? abortRef.current?.abort() : handleSend()}
              disabled={!input.trim() && !isAgentSending}
              className={cn(
                'border-none px-2.5 py-1.5 rounded-md text-[11px] transition-colors',
                inputRows === 1 ? 'self-center' : 'self-end',
                isAgentSending ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-primary text-primary-foreground disabled:opacity-50'
              )}
              title={isAgentSending ? '停止生成 (Esc x2)' : '发送'}
            >
              {isAgentSending ? <Square className="h-3 w-3" /> : <Send className="h-3 w-3" />}
            </button>
          </div>
        </div>
      </div>

      <ConversationHistoryDialog
        open={showConversationHistory}
        onOpenChange={setShowConversationHistory}
        onSwitchConversation={handleSwitchConversation}
        isAgentSending={isAgentSending}
      />
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
