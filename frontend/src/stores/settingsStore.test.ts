/**
 * settingsStore 测试
 * 测试设置状态管理，包括 workflowMode 持久化
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { useSettingsStore } from '@/stores/settingsStore'

describe('SettingsStore', () =>
{
  beforeEach(() =>
  {
    // 清空 localStorage
    localStorage.clear()
    // 重置 store 状态
    useSettingsStore.setState({
      settings: null,
      workflowMode: 'hybrid',
    })
  })

  afterEach(() =>
  {
    localStorage.clear()
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

  describe('workflowMode 持久化', () =>
  {
    it('修改 workflowMode 后保存到 localStorage', () =>
    {
      useSettingsStore.getState().setWorkflowMode('auto')

      // 验证 localStorage 中存储的值
      const storedValue = localStorage.getItem('settings-storage')
      expect(storedValue).not.toBeNull()

      if (storedValue)
      {
        const parsed = JSON.parse(storedValue)
        expect(parsed.state.workflowMode).toBe('auto')
      }
    })

    it('从 localStorage 恢复 workflowMode', () =>
    {
      // 模拟 localStorage 中有存储的值
      localStorage.setItem('settings-storage', JSON.stringify({
        state: { workflowMode: 'step_by_step' },
        version: 0,
      }))

      // 重置 store 以触发从 localStorage 恢复
      useSettingsStore.persist.clearStorage()
      useSettingsStore.setState({ workflowMode: 'step_by_step' })

      // 验证状态
      expect(useSettingsStore.getState().workflowMode).toBe('step_by_step')
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

    it('persist 只存储 workflowMode', () =>
    {
      useSettingsStore.getState().setWorkflowMode('auto')
      useSettingsStore.getState().setSettings({
        model_provider: 'openai',
        model_name: 'gpt-4',
        has_api_key: true,
        review_enabled: true,
        review_strictness: 'standard',
      })

      const storedValue = localStorage.getItem('settings-storage')
      expect(storedValue).not.toBeNull()

      if (storedValue)
      {
        const parsed = JSON.parse(storedValue)
        // workflowMode 应该被存储
        expect(parsed.state.workflowMode).toBe('auto')
        // settings 不应该被存储（partialize 只保存 workflowMode）
        expect(parsed.state.settings).toBeUndefined()
      }
    })
  })
})
