/**
 * SSE 解析工具
 * 统一的 Server-Sent Events 解析逻辑
 */

/**
 * SSE 事件结构
 */
export interface SSEEvent
{
  type: string
  data: string
}

/**
 * 解析 SSE 格式的文本块
 * @param eventBlock - 单个 SSE 事件块（以 \n\n 结尾的部分）
 * @returns 解析后的事件对象
 */
export function parseSSEEventBlock(eventBlock: string): SSEEvent
{
  const lines = eventBlock.split('\n')
  let eventType = 'message'
  let eventData = ''

  for (const line of lines)
  {
    if (line.startsWith('event:'))
    {
      eventType = line.slice(6).trim()
    }
    else if (line.startsWith('data:'))
    {
      // data: 后面的内容，去掉冒号后的空格（SSE 规范）
      const dataContent = line.slice(5)
      // 如果 data: 后面有空格，去掉一个空格（SSE 规范要求）
      eventData += dataContent.startsWith(' ') ? dataContent.slice(1) : dataContent
    }
  }

  return { type: eventType, data: eventData }
}

/**
 * 处理 SSE 流的缓冲区
 * 返回处理后的剩余缓冲区和完整事件列表
 * @param buffer - 当前缓冲区内容
 * @param incomingData - 新到达的数据
 * @returns [剩余缓冲区, 完整事件列表]
 */
export function processSSEBuffer(
  buffer: string,
  incomingData: string
): [string, SSEEvent[]]
{
  let remaining = buffer + incomingData
  const events: SSEEvent[] = []

  // 处理所有完整的 SSE 事件（以 \n\n 结尾）
  while (true)
  {
    const eventEndIndex = remaining.indexOf('\n\n')
    if (eventEndIndex === -1)
    {
      // 没有完整事件，保留在缓冲区
      break
    }

    const eventBlock = remaining.slice(0, eventEndIndex)
    remaining = remaining.slice(eventEndIndex + 2)

    // 解析事件
    const event = parseSSEEventBlock(eventBlock)
    if (event.data)
    {
      events.push(event)
    }
  }

  return [remaining, events]
}

/**
 * 解析 SSE 事件的 data 字段
 * 支持直接字符串或 JSON 对象
 * @param data - data 字段的原始值
 * @returns 解析后的数据
 */
export function parseSSEData(data: string): unknown
{
  // 尝试 JSON 解析
  try
  {
    return JSON.parse(data)
  }
  catch
  {
    // 如果不是有效 JSON，返回原始字符串
    return data
  }
}

/**
 * SSE 流式请求选项
 */
export interface SSEStreamOptions
{
  url: string
  method?: string
  body?: unknown
  signal?: AbortSignal
}

/**
 * 创建 SSE 流式连接的通用函数
 * 统一处理认证、fetch、流读取、缓冲区解析、错误处理
 * @param options - 请求选项
 * @param onEvent - 事件回调函数
 * @param onError - 错误回调函数
 */
export async function createSSEStream(
  options: SSEStreamOptions,
  onEvent: (type: string, data: unknown) => void,
  onError: (error: string) => void
): Promise<void>
{
  // 动态导入避免循环依赖
  const { getSessionToken } = await import('./api')

  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const headers: HeadersInit = {}

  if (options.method === 'POST' || options.body)
  {
    headers['Content-Type'] = 'application/json'
  }

  // 构建认证头
  const token = getSessionToken()
  if (token)
  {
    const credentials = btoa(`${token}:`)
    headers['Authorization'] = `Basic ${credentials}`
  }

  const response = await fetch(`${API_BASE_URL}${options.url}`, {
    method: options.method || 'GET',
    headers,
    signal: options.signal,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok)
  {
    const errorData = await response.json().catch(() => ({ detail: '请求失败' }))
    onError(errorData.detail || `HTTP ${response.status}`)
    return
  }

  const reader = response.body?.getReader()
  if (!reader)
  {
    onError('无法获取数据流')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try
  {
    while (true)
    {
      const { done, value } = await reader.read()

      if (done)
      {
        // 处理剩余缓冲区
        if (buffer.trim())
        {
          const [remaining, events] = processSSEBuffer(buffer, '')
          for (const event of events)
          {
            const parsedData = parseSSEData(event.data)
            onEvent(event.type, parsedData)
          }
        }
        break
      }

      const newData = decoder.decode(value, { stream: true })
      const [remaining, events] = processSSEBuffer(buffer, newData)
      buffer = remaining

      for (const event of events)
      {
        const parsedData = parseSSEData(event.data)
        onEvent(event.type, parsedData)
      }
    }
  }
  catch (err)
  {
    // 用户主动取消，不触发错误回调
    if (err instanceof Error && err.name === 'AbortError')
    {
      return
    }
    onError(err instanceof Error ? err.message : '未知错误')
  }
}
