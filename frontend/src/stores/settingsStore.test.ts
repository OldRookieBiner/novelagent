/**
 * settingsStore 测试
 * 测试设置状态管理
 *
 * 注意：workflowMode 已迁移到项目级别，不再持久化到 localStorage
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useSettingsStore } from '@/stores/settingsStore'

describe('SettingsStore', () =>
{
  beforeEach(() =>
  {
    // 重置 store 状态
    useSettingsStore.setState({
      settings: null,
      workflowMode: 'hybrid',
    })
  })

  describe('基础状态管理', () =>
  {
    it('设置 workflowMode', () =>
    {
      useSettingsStore.getState().setWorkflowMode('step_by_step')
      expect(useSettingsStore.getState().workflowMode).toBe('step_by_step')
    })

    it('设置 workflowMode 为 auto', () =>
    {
      useSettingsStore.getState().setWorkflowMode('auto')
      expect(useSettingsStore.getState().workflowMode).toBe('auto')
    })

    it('默认 workflowMode 为 hybrid', () =>
    {
      expect(useSettingsStore.getState().workflowMode).toBe('hybrid')
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
        review_enabled: true,
        review_strictness: 'standard',
      })

      expect(useSettingsStore.getState().settings?.model_provider).toBe('openai')
      expect(useSettingsStore.getState().settings?.model_name).toBe('gpt-4')
    })

    it('设置 settings 不影响 workflowMode', () =>
    {
      useSettingsStore.getState().setWorkflowMode('auto')
      useSettingsStore.getState().setSettings({
        model_provider: 'openai',
        model_name: 'gpt-4',
        has_api_key: true,
        review_enabled: true,
        review_strictness: 'standard',
      })

      expect(useSettingsStore.getState().workflowMode).toBe('auto')
      expect(useSettingsStore.getState().settings?.model_provider).toBe('openai')
    })
  })
})
