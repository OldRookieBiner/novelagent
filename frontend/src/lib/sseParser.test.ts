/**
 * SSE 解析工具测试
 */

import { describe, it, expect } from 'vitest'
import { parseSSEEventBlock, processSSEBuffer, parseSSEData } from './sseParser'

describe('SSE Parser', () =>
{
  describe('parseSSEEventBlock', () =>
  {
    it('解析基本事件', () =>
    {
      const block = 'event: node_start\ndata: "generate_outline"'
      const event = parseSSEEventBlock(block)

      expect(event.type).toBe('node_start')
      expect(event.data).toBe('"generate_outline"')
    })

    it('解析没有 event 字段的事件（默认 message）', () =>
    {
      const block = 'data: {"key": "value"}'
      const event = parseSSEEventBlock(block)

      expect(event.type).toBe('message')
      expect(event.data).toBe('{"key": "value"}')
    })

    it('解析多行 data（SSE 规范：每行都有 data: 前缀）', () =>
    {
      // SSE 规范：多行 data 应该每行都有 data: 前缀
      const block = 'event: chunk\ndata: line1\ndata: line2'
      const event = parseSSEEventBlock(block)

      expect(event.type).toBe('chunk')
      expect(event.data).toBe('line1line2')
    })

    it('解析不带空格的 data 行', () =>
    {
      // data: 后面没有空格也是合法的
      const block = 'event: test\ndata:value'
      const event = parseSSEEventBlock(block)

      expect(event.type).toBe('test')
      expect(event.data).toBe('value')
    })
  })

  describe('parseSSEData', () =>
  {
    it('解析 JSON 字符串', () =>
    {
      const result = parseSSEData('"hello"')
      expect(result).toBe('hello')
    })

    it('解析 JSON 对象', () =>
    {
      const result = parseSSEData('{"name": "test"}')
      expect(result).toEqual({ name: 'test' })
    })

    it('解析 JSON 数组', () =>
    {
      const result = parseSSEData('[1, 2, 3]')
      expect(result).toEqual([1, 2, 3])
    })

    it('非 JSON 返回原始字符串', () =>
    {
      const result = parseSSEData('plain text')
      expect(result).toBe('plain text')
    })

    it('解析数字', () =>
    {
      const result = parseSSEData('42')
      expect(result).toBe(42)
    })

    it('解析布尔值', () =>
    {
      expect(parseSSEData('true')).toBe(true)
      expect(parseSSEData('false')).toBe(false)
    })
  })

  describe('processSSEBuffer', () =>
  {
    it('处理完整事件', () =>
    {
      const buffer = ''
      const data = 'event: node_start\ndata: "test"\n\n'
      const [remaining, events] = processSSEBuffer(buffer, data)

      expect(remaining).toBe('')
      expect(events).toHaveLength(1)
      expect(events[0].type).toBe('node_start')
      expect(events[0].data).toBe('"test"')
    })

    it('处理多个事件', () =>
    {
      const buffer = ''
      const data = 'event: node_start\ndata: "test1"\n\nevent: node_done\ndata: {"node":"test"}\n\n'
      const [remaining, events] = processSSEBuffer(buffer, data)

      expect(remaining).toBe('')
      expect(events).toHaveLength(2)
      expect(events[0].type).toBe('node_start')
      expect(events[1].type).toBe('node_done')
    })

    it('保留不完整事件在缓冲区', () =>
    {
      const buffer = ''
      const data = 'event: node_start\ndata: "test"'
      const [remaining, events] = processSSEBuffer(buffer, data)

      expect(remaining).toBe(data)
      expect(events).toHaveLength(0)
    })

    it('追加到现有缓冲区', () =>
    {
      const buffer = 'event: node_start\ndata: "test'
      const data = '"\n\n'
      const [remaining, events] = processSSEBuffer(buffer, data)

      expect(remaining).toBe('')
      expect(events).toHaveLength(1)
      expect(events[0].data).toBe('"test"')
    })

    it('处理没有 data 的事件', () =>
    {
      const buffer = ''
      const data = 'event: ping\n\n'
      const [remaining, events] = processSSEBuffer(buffer, data)

      expect(remaining).toBe('')
      expect(events).toHaveLength(0) // 没有 data 的事件被忽略
    })
  })
})
