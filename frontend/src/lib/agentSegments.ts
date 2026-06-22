// agentSegments.ts — Agent 消息 segments 归一化工具
//
// 设计意图：
// 1. 前端运行时只消费一种"工具调用"段类型：`tool_call`。
// 2. 历史会话 DB 中仍存有旧格式的 `tool_start` / `tool_result` 配对，hydrate 时
//    通过 normalizeLegacySegments 一次性归一化为 `tool_call`。
// 3. 后端 `actions` 数组维护 running/done/error 状态机；当二者都存在时，
//    actions 是状态权威来源，segments 仅决定段顺序与文案。

import type { AiMessageSegment, ToolCallSegmentData, ToolCallStatus } from '@/stores/workbenchStore'

/** fetchConversation 返回的 action 项形状（与后端契约一致） */
export interface BackendAction
{
  tool: string
  status: 'running' | 'done' | 'error'
  description?: string
  args?: Record<string, unknown>
  result?: Record<string, unknown>
}

/** 后端原始 segment 形状（来自 fetchConversation；type 可能含旧字段） */
export interface RawSegment
{
  type: string
  content?: string
  data?: Record<string, unknown>
}

/** 把 BackendAction.status 映射到前端 ToolCallStatus（保留扩展空间） */
function mapActionStatus(status: BackendAction['status']): ToolCallStatus
{
  if (status === 'error') return 'error'
  if (status === 'done') return 'done'
  return 'running'
}

/**
 * 把后端持久化的 segments 归一化为前端运行时形状：
 * - `tool_start` / `tool_result` 对配对成 `tool_call`（状态 running → done）。
 * - 未配对的 `tool_start`（历史会话残留，发生在崩溃流）标记为 `error`，
 *   因为历史流早已结束，没有 running 的语义。
 * - 其余段（agent_text / progress / warning ...）原样透传。
 *
 * @param rawSegments 后端返回的原始 segments
 * @param actions 后端 actions 数组；如存在，会按"工具名 + 第 k 次出现"对齐校正 status
 *                与 args/result，使 error 等后端权威状态生效。
 */
export function normalizeLegacySegments(
  rawSegments: RawSegment[] | undefined | null,
  actions?: BackendAction[] | undefined | null,
): AiMessageSegment[]
{
  const segments = (rawSegments || []).map((s): AiMessageSegment => ({
    type: (s.type as AiMessageSegment['type']) || 'agent_text',
    content: s.content || '',
    data: s.data,
  }))

  const out: AiMessageSegment[] = []
  // 跟踪每个工具名的 running tool_call 在 out 中的下标栈（最近一个在栈顶）
  const runningByTool = new Map<string, number[]>()

  for (const seg of segments)
  {
    if (seg.type === 'tool_start')
    {
      const tool = String((seg.data?.tool as string) || seg.content || '')
      const args = seg.data?.args as Record<string, unknown> | undefined
      const data: ToolCallSegmentData = { tool, status: 'running', args }
      const callSeg: AiMessageSegment = {
        type: 'tool_call',
        content: seg.content || tool,
        data: data as unknown as Record<string, unknown>,
      }
      const idx = out.push(callSeg) - 1
      const stack = runningByTool.get(tool) ?? []
      stack.push(idx)
      runningByTool.set(tool, stack)
      continue
    }

    if (seg.type === 'tool_result')
    {
      const tool = String((seg.data?.tool as string) || seg.content || '')
      const result = seg.data?.result as Record<string, unknown> | undefined
      const stack = runningByTool.get(tool)
      if (stack && stack.length > 0)
      {
        // 配对：取最近一个同 tool 的 running tool_call，原地改 done
        const idx = stack.pop()!
        runningByTool.set(tool, stack)
        const prev = out[idx]
        const prevData = (prev.data as ToolCallSegmentData | undefined) || { tool, status: 'running' }
        const merged: ToolCallSegmentData = {
          ...prevData,
          tool,
          status: 'done',
          result: result ?? prevData.result,
        }
        out[idx] = { ...prev, data: merged as unknown as Record<string, unknown> }
      }
      else
      {
        // 历史数据异常：tool_result 无配对 start。保守做法是丢弃，避免凭空
        // 生成一条"没有标题文案的 tool_call"。这种情况在生产中不应出现。
      }
      continue
    }

    // 防御：DB 中如已存在 tool_call（未来兼容），原样保留并把 running 的下标入栈
    if (seg.type === 'tool_call')
    {
      const data = (seg.data as ToolCallSegmentData | undefined)
      const tool = String(data?.tool || '')
      const idx = out.push(seg) - 1
      if (data?.status === 'running' && tool)
      {
        const stack = runningByTool.get(tool) ?? []
        stack.push(idx)
        runningByTool.set(tool, stack)
      }
      continue
    }

    out.push(seg)
  }

  // 残留 running tool_call（历史会话崩溃流）→ 标记 error
  for (const [, stack] of runningByTool)
  {
    for (const idx of stack)
    {
      const prev = out[idx]
      const prevData = (prev.data as ToolCallSegmentData | undefined) || { tool: '', status: 'running' }
      out[idx] = {
        ...prev,
        data: { ...prevData, status: 'error' } as unknown as Record<string, unknown>,
      }
    }
  }

  // 用 actions 数组校正：actions 是后端状态权威来源
  // 对齐策略：按工具名 + 该工具名下的第 k 次出现 一一对应。
  if (actions && actions.length > 0)
  {
    // 收集 out 中每个工具名对应的 tool_call 下标序列（按出现顺序）
    const indicesByTool = new Map<string, number[]>()
    out.forEach((seg, idx) =>
    {
      if (seg.type !== 'tool_call') return
      const tool = String((seg.data as ToolCallSegmentData | undefined)?.tool || '')
      if (!tool) return
      const arr = indicesByTool.get(tool) ?? []
      arr.push(idx)
      indicesByTool.set(tool, arr)
    })

    // 按工具名计数，从对应序列里依次取下标
    const cursorByTool = new Map<string, number>()
    for (const action of actions)
    {
      const tool = action.tool
      if (!tool) continue
      const indices = indicesByTool.get(tool)
      if (!indices) continue
      const cursor = cursorByTool.get(tool) ?? 0
      if (cursor >= indices.length) continue
      const idx = indices[cursor]
      cursorByTool.set(tool, cursor + 1)
      const prev = out[idx]
      const prevData = (prev.data as ToolCallSegmentData | undefined) || { tool, status: 'running' }
      const merged: ToolCallSegmentData = {
        ...prevData,
        tool,
        status: mapActionStatus(action.status),
        args: action.args ?? prevData.args,
        result: action.result ?? prevData.result,
      }
      out[idx] = { ...prev, data: merged as unknown as Record<string, unknown> }
    }
  }

  return out
}

/**
 * 把 segments 中所有 `tool_call` 段里 status === 'running' 的批量改为 finalStatus。
 * 纯函数：不修改入参，返回新数组（如无变化则返回原数组以便上游 short-circuit）。
 *
 * 仅供流终止（error / aborted）路径调用；SSE 自然结束不应使用，
 * 以便残留 running 能在 UI 上暴露上游 bug。
 */
export function finalizeRunningToolCalls(
  segments: AiMessageSegment[],
  finalStatus: 'error' | 'aborted',
): AiMessageSegment[]
{
  let changed = false
  const out = segments.map((seg) =>
  {
    if (seg.type !== 'tool_call') return seg
    const data = seg.data as ToolCallSegmentData | undefined
    if (!data || data.status !== 'running') return seg
    changed = true
    const merged: ToolCallSegmentData = { ...data, status: finalStatus }
    return { ...seg, data: merged as unknown as Record<string, unknown> }
  })
  return changed ? out : segments
}
