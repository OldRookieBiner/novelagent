import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchStore } from '@/stores/workbenchStore'

describe('workbenchStore inspiration brief', () =>
{
  beforeEach(() =>
  {
    useWorkbenchStore.getState().reset()
  })

  it('should have default empty inspirationBrief', () =>
  {
    const { inspirationBrief } = useWorkbenchStore.getState()
    expect(inspirationBrief).toBe('')
  })

  it('should update inspirationBrief via setInspirationBrief', () =>
  {
    useWorkbenchStore.getState().setInspirationBrief('# 测试灵感\n\n这是一个测试')
    expect(useWorkbenchStore.getState().inspirationBrief).toBe('# 测试灵感\n\n这是一个测试')
  })

  it('should reset inspirationBrief on reset()', () =>
  {
    useWorkbenchStore.getState().setInspirationBrief('一些内容')
    useWorkbenchStore.getState().reset()
    expect(useWorkbenchStore.getState().inspirationBrief).toBe('')
  })
})
