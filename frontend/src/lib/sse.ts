/**
 * SSE（Server-Sent Events）解析工具
 * 用于解析后端流式传输的事件数据
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
 * SSE 解析回调
 */
export interface SSECallbacks<T>
{
  onChunk: (chunk: T | string) => void
  onDone?: (result: T) => void
  onError?: (error: string) => void
  // 工作流事件回调
  onNodeStart?: (node: string) => void
  onNodeDone?: (node: string, state: Record<string, unknown>) => void
  onWaiting?: (type: string) => void
}

/**
 * 从 ReadableStream 解析 SSE 事件
 * @param reader - 可读流的 reader
 * @param callbacks - 事件回调函数
 */
export async function parseSSEStream<T>(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  callbacks: SSECallbacks<T>
): Promise<void>
{
  const decoder = new TextDecoder()
  let buffer = ''

  /**
   * 处理缓冲区中的完整事件
   */
  const processBuffer = (buf: string): string => {
    let remaining = buf

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

      // 解析事件行
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
          eventData += line.slice(5)
        }
      }

      if (eventData)
      {
        if (eventType === 'done')
        {
          // 完成事件 - 解析 JSON
          try
          {
            const result = JSON.parse(eventData) as T
            callbacks.onDone?.(result)
          }
          catch (e)
          {
            callbacks.onError?.(`解析完成数据失败: ${eventData.slice(0, 100)}...`)
          }
        }
        else if (eventType === 'error')
        {
          callbacks.onError?.(eventData)
        }
        else if (eventType === 'node_start')
        {
          // 节点开始事件
          try
          {
            const nodeName = JSON.parse(eventData) as string
            callbacks.onNodeStart?.(nodeName)
          }
          catch
          {
            callbacks.onNodeStart?.(eventData)
          }
        }
        else if (eventType === 'node_done')
        {
          // 节点完成事件
          try
          {
            const data = JSON.parse(eventData) as { node: string; state: Record<string, unknown> }
            callbacks.onNodeDone?.(data.node, data.state)
          }
          catch
          {
            // 解析失败时忽略
          }
        }
        else if (eventType === 'waiting')
        {
          // 等待确认事件
          try
          {
            const waitingType = JSON.parse(eventData) as string
            callbacks.onWaiting?.(waitingType)
          }
          catch
          {
            callbacks.onWaiting?.(eventData)
          }
        }
        else
        {
          // 普通数据块 - 解码并转发
          try
          {
            const chunk = JSON.parse(eventData)
            callbacks.onChunk(chunk)
          }
          catch
          {
            // 如果不是有效的 JSON，当作原始文本处理
            callbacks.onChunk(eventData)
          }
        }
      }
    }

    return remaining
  }

  try
  {
    while (true)
    {
      const { done, value } = await reader.read()

      if (done)
      {
        // 处理剩余的缓冲区
        if (buffer.trim())
        {
          processBuffer(buffer)
        }
        break
      }

      buffer += decoder.decode(value, { stream: true })
      buffer = processBuffer(buffer)
    }
  }
  catch (err)
  {
    callbacks.onError?.(err instanceof Error ? err.message : '未知错误')
  }
}

/**
 * 解析单个 SSE 数据行
 * @param data - data: 后面的内容
 * @returns 解析后的字符串
 */
export function parseSSEData(data: string): string
{
  // 后端使用 JSON.stringify 编码换行符
  try
  {
    return JSON.parse(data)
  }
  catch
  {
    return data
  }
}
