import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInspirationForm } from '../useInspirationForm'
import { useWorkbenchStore } from '@/stores/workbenchStore'

// Mock API — 必须在 import 之前
vi.mock('@/lib/api', () => ({
  collectedInfoApi: { update: vi.fn().mockResolvedValue({}) },
  modelConfigsApi: { list: vi.fn().mockResolvedValue({ models: [] }) },
  outlineApi: { get: vi.fn().mockRejectedValue({}) },
}))

// Mock inspiration 模块避免实际执行
vi.mock('@/lib/inspiration', () => ({
  REQUIRED_FIELDS: ['novelType', 'targetReader', 'targetWords', 'era', 'coreTheme', 'wordsPerChapter'],
  MALE_REQUIRED_FIELDS: ['maleLead'],
  FEMALE_REQUIRED_FIELDS: ['femaleLead'],
  getContextStrategyFromTargetWords: vi.fn((w: number) => w <= 100000 ? 'fulltext' : w <= 300000 ? 'hybrid' : 'summary'),
  generateInspirationTemplate: vi.fn(() => '# Template'),
  saveInspirationDraft: vi.fn(),
  loadInspirationDraft: vi.fn(() => null),
}))

describe('useInspirationForm', () =>
{
  beforeEach(() =>
  {
    useWorkbenchStore.getState().reset()
  })

  it('should initialize with default values', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    expect(result.current.errors).toEqual({})
    expect(result.current.confirming).toBe(false)
  })

  it('should validate required fields and set errors', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => { result.current.validate() })
    expect(Object.keys(result.current.errors).length).toBeGreaterThan(0)
    expect(result.current.errors.targetReader).toBeDefined()
  })

  it('should clear error when field is set', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => { result.current.validate() })
    expect(result.current.errors.targetReader).toBeDefined()
    act(() => { result.current.setField('targetReader', 'male') })
    expect(result.current.errors.targetReader).toBeUndefined()
  })

  it('should build collectedInfoData for API', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() =>
    {
      result.current.setField('novelType', 'xuanhuan')
      result.current.setField('targetReader', 'male')
      result.current.setField('targetWords', 100000)
    })
    const data = result.current.buildCollectedInfoData()
    expect(data.novelType).toBe('xuanhuan')
    expect(data.targetReader).toBe('male')
  })

  it('should compute required progress', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    const { requiredFilled, requiredTotal } = result.current.progress
    expect(requiredTotal).toBeGreaterThanOrEqual(6)
    expect(requiredFilled).toBeLessThan(requiredTotal)
  })

  it('should auto-set contextStrategy when targetWords changes', () =>
  {
    const { result } = renderHook(() => useInspirationForm({ projectId: 1 }))
    act(() => { result.current.setField('targetWords', 200000) })
    expect(result.current.fields.contextStrategy).toBe('hybrid')
    act(() => { result.current.setField('targetWords', 50000) })
    expect(result.current.fields.contextStrategy).toBe('fulltext')
  })
})
