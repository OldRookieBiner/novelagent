import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchStore } from '@/stores/workbenchStore'

describe('workbenchStore inspiration fields', () =>
{
  beforeEach(() =>
  {
    useWorkbenchStore.getState().reset()
  })

  it('should have default empty inspirationFields', () =>
  {
    const { inspirationFields } = useWorkbenchStore.getState()
    expect(inspirationFields).toBeDefined()
    expect(inspirationFields.novelType).toBe('')
    expect(inspirationFields.targetWords).toBe(50000)
  })

  it('should update inspirationFields via setInspirationField', () =>
  {
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    expect(useWorkbenchStore.getState().inspirationFields.novelType).toBe('xuanhuan')
  })

  it('should update fieldStatus via setInspirationFieldStatus', () =>
  {
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_populated')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBe('agent_populated')
  })

  it('should clear agent_asking status when field is set by user', () =>
  {
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_asking')
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBeUndefined()
  })

  it('should keep agent_populated status when field is set', () =>
  {
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_populated')
    useWorkbenchStore.getState().setInspirationField('novelType', 'dushi')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBe('agent_populated')
  })

  it('should batch update inspirationFields via setInspirationFields', () =>
  {
    useWorkbenchStore.getState().setInspirationFields({
      novelType: 'xuanhuan',
      targetReader: 'male',
      targetWords: 100000,
    })
    const { inspirationFields } = useWorkbenchStore.getState()
    expect(inspirationFields.novelType).toBe('xuanhuan')
    expect(inspirationFields.targetReader).toBe('male')
    expect(inspirationFields.targetWords).toBe(100000)
  })

  it('should reset inspiration state on reset()', () =>
  {
    useWorkbenchStore.getState().setInspirationField('novelType', 'xuanhuan')
    useWorkbenchStore.getState().setInspirationFieldStatus('novelType', 'agent_populated')
    useWorkbenchStore.getState().reset()
    expect(useWorkbenchStore.getState().inspirationFields.novelType).toBe('')
    expect(useWorkbenchStore.getState().inspirationFieldStatus.novelType).toBeUndefined()
  })
})
