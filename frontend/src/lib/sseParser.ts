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
