/**
 * settingsStore 测试
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useSettingsStore } from '@/stores/settingsStore'

describe('SettingsStore', () =>
{
  beforeEach(() =>
  {
    useSettingsStore.setState({
      settings: null,
    })
  })

  describe('设置管理', () =>
  {
    it('设置 settings', () =>
    {
      useSettingsStore.getState().setSettings({
        model_provider: 'openai',
        model_name: 'gpt-4',
        has_api_key: true,
      })

      expect(useSettingsStore.getState().settings?.model_provider).toBe('openai')
      expect(useSettingsStore.getState().settings?.model_name).toBe('gpt-4')
    })
  })
})
