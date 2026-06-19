import { describe, it, expect } from 'vitest'
import { truncateTitle } from '@/components/workbench/AgentChatPanel'

describe('truncateTitle', () => {
  it('空串返回占位', () => {
    expect(truncateTitle('')).toBe('(空消息)')
  })
  it('纯空白返回占位', () => {
    expect(truncateTitle('   \n  \t')).toBe('(空消息)')
  })
  it('全英文 14 字不截', () => {
    const s = 'a'.repeat(14)
    expect(truncateTitle(s)).toBe(s)
  })
  it('全英文 15 字不截', () => {
    const s = 'a'.repeat(15)
    expect(truncateTitle(s)).toBe(s)
  })
  it('全英文 16 字截断加…', () => {
    const s = 'a'.repeat(16)
    expect(truncateTitle(s)).toBe('a'.repeat(15) + '…')
  })
  it('中文 15 字不截', () => {
    const s = '中'.repeat(15)
    expect(truncateTitle(s)).toBe(s)
  })
  it('中文 16 字截断加…', () => {
    const s = '中'.repeat(16)
    expect(truncateTitle(s)).toBe('中'.repeat(15) + '…')
  })
  it('emoji 按 grapheme 计', () => {
    const s = '👍' + 'a'.repeat(14)  // 共 15 个 grapheme
    expect(truncateTitle(s)).toBe(s)
  })
  it('多个换行/空白合并清理', () => {
    expect(truncateTitle('\n  你好\n世界  \n')).toBe('你好 世界')
  })
})
