import { useState, useEffect, useCallback } from 'react'
import { settingsApi, systemPromptsApi, modelConfigsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import { toast } from 'sonner'
import type { SettingsUpdate, SystemPrompt, ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types'

const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
  { id: 'character_generation', label: '人物生成' },
  { id: 'relation_generation', label: '关系生成' },
  { id: 'review', label: '审核' },
  { id: 'rewrite', label: '重写' },
] as const

type AgentTab = typeof AGENT_TABS[number]['id']

export type { AgentTab, AGENT_TABS as AGENT_TABS_CONST }
export { AGENT_TABS }

export function useSettings()
{
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // 模型配置状态
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [configsLoading, setConfigsLoading] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null)

  // 审核设置状态
  const [reviewMode, setReviewMode] = useState<'off' | 'manual' | 'auto'>('manual')
  const [maxRewriteCount, setMaxRewriteCount] = useState(3)

  // 工作流模式状态
  const setSettings = useSettingsStore((state) => state.setSettings)

  // 系统提示词状态
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [promptsLoading, setPromptsLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentTab>('outline_generation')
  const [editContent, setEditContent] = useState('')
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [resettingPrompt, setResettingPrompt] = useState(false)

  // 加载设置
  useEffect(() =>
  {
    const fetchSettings = async () =>
    {
      try
      {
        const data = await settingsApi.get()
        if (!data.review_enabled)
        {
          setReviewMode('off')
        }
        else
        {
          setReviewMode('manual')
        }
        setSettings(data)
      }
      catch (err)
      {
        console.error('Failed to fetch settings:', err)
        toast.error('加载设置失败')
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  // 加载模型配置（带 loading 状态，用于用户主动触发的加载）
  const loadModelConfigs = useCallback(async () =>
  {
    setConfigsLoading(true)
    try
    {
      const data = await modelConfigsApi.list()
      setModelConfigs(data.models)
    }
    catch (err)
    {
      console.error('Failed to load model configs:', err)
      toast.error('加载模型配置失败')
    }
    finally
    {
      setConfigsLoading(false)
    }
  }, [])

  // 静默刷新模型配置（不带 loading 状态，用于自动保存后同步最新数据）
  const refreshModelConfigs = useCallback(async () =>
  {
    try
    {
      const data = await modelConfigsApi.list()
      setModelConfigs(data.models)
    }
    catch (err)
    {
      console.error('Failed to refresh model configs:', err)
    }
  }, [])

  // 加载系统提示词
  const loadPrompts = useCallback(async () =>
  {
    setPromptsLoading(true)
    try
    {
      const data = await systemPromptsApi.list()
      setPrompts(data.prompts)
    }
    catch (err)
    {
      console.error('Failed to load system prompts:', err)
      toast.error('加载提示词失败')
    }
    finally
    {
      setPromptsLoading(false)
    }
  }, [])

  // 当 prompts 加载后，更新编辑内容
  useEffect(() =>
  {
    const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)
    if (currentPrompt)
    {
      setEditContent(currentPrompt.prompt_content)
    }
  }, [prompts, selectedAgent])

  // 当前选中的提示词
  const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)

  // 保存提示词
  const handleSavePrompt = useCallback(async () =>
  {
    if (!currentPrompt) return
    setSavingPrompt(true)
    try
    {
      const updated = await systemPromptsApi.update(selectedAgent, { prompt_content: editContent })
      setPrompts((prev) =>
        prev.map((p) => (p.agent_type === selectedAgent ? updated : p))
      )
    }
    catch (err)
    {
      console.error('Failed to save prompt:', err)
      toast.error('保存提示词失败')
    }
    finally
    {
      setSavingPrompt(false)
    }
  }, [currentPrompt, selectedAgent, editContent])

  // 重置提示词
  const handleResetPrompt = useCallback(async () =>
  {
    if (!confirm('确定要重置为默认值吗？您的修改将丢失。')) return
    setResettingPrompt(true)
    try
    {
      const updated = await systemPromptsApi.reset(selectedAgent)
      setPrompts((prev) =>
        prev.map((p) => (p.agent_type === selectedAgent ? updated : p))
      )
      setEditContent(updated.prompt_content)
    }
    catch (err)
    {
      console.error('Failed to reset prompt:', err)
      toast.error('重置提示词失败')
    }
    finally
    {
      setResettingPrompt(false)
    }
  }, [selectedAgent])

  // 保存审核设置
  const handleSaveReviewSettings = useCallback(async () =>
  {
    setSaving(true)
    try
    {
      const update: SettingsUpdate = {
        review_enabled: reviewMode !== 'off',
        review_strictness: 'standard',
      }
      const updated = await settingsApi.update(update)
      setSettings(updated)
      setSaved(true)
    }
    catch (err)
    {
      console.error('Failed to save settings:', err)
      toast.error('保存审核设置失败')
    }
    finally
    {
      setSaving(false)
    }
  }, [reviewMode])

  // 创建模型配置
  const handleCreateModel = useCallback(async (data: ModelConfigCreate) =>
  {
    setSavingConfig(true)
    try
    {
      await modelConfigsApi.create(data)
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to create model config:', err)
      toast.error('创建模型配置失败')
    }
    finally
    {
      setSavingConfig(false)
    }
  }, [loadModelConfigs])

  // 更新模型配置（部分更新，静默刷新）
  const handleUpdateModel = useCallback(async (configId: number, data: ModelConfigUpdate) =>
  {
    try
    {
      await modelConfigsApi.update(configId, data)
      await refreshModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to update model config:', err)
      toast.error('更新模型配置失败')
    }
  }, [refreshModelConfigs])

  // 设置默认模型
  const handleSetDefault = useCallback(async (configId: number) =>
  {
    try
    {
      await modelConfigsApi.setDefault(configId)
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to set default:', err)
      toast.error('设置默认模型失败')
    }
  }, [loadModelConfigs])

  // 删除模型配置
  const handleDeleteModel = useCallback(async (configId: number) =>
  {
    if (!confirm('确定要删除这个模型配置吗？')) return
    try
    {
      await modelConfigsApi.delete(configId)
      await loadModelConfigs()
      // 删除后若该配置被选中，清除选中状态
      if (selectedConfigId === configId)
      {
        setSelectedConfigId(null)
      }
    }
    catch (err)
    {
      console.error('Failed to delete:', err)
      toast.error('删除模型配置失败')
    }
  }, [loadModelConfigs, selectedConfigId])

  // 健康检查
  const handleCheckHealth = useCallback(async (configId: number) =>
  {
    try
    {
      const result = await modelConfigsApi.checkHealth(configId)
      await loadModelConfigs()
      // 反馈检查结果
      if (result.model_results && result.model_results.length > 0)
      {
        const healthy = result.model_results.filter(r => r.status === 'healthy').length
        const unhealthy = result.model_results.length - healthy
        if (unhealthy === 0)
        {
          toast.success(`全部 ${healthy} 个模型健康`)
        }
        else
        {
          toast.error(`${healthy} 个模型健康，${unhealthy} 个模型异常`)
        }
      }
      else if (result.status === 'healthy')
      {
        toast.success('模型连接正常')
      }
      else
      {
        toast.error(`模型异常：${result.error || '未知错误'}`)
      }
    }
    catch (err)
    {
      console.error('Health check failed:', err)
      toast.error('健康检查失败')
    }
  }, [loadModelConfigs])

  // 切换模型启用状态
  const handleToggleEnabled = useCallback(async (configId: number, enabled: boolean) =>
  {
    try
    {
      await modelConfigsApi.update(configId, { is_enabled: enabled })
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Failed to toggle enabled:', err)
      toast.error('切换启用状态失败')
    }
  }, [loadModelConfigs])

  // 选中模型配置
  const handleSelectConfig = useCallback((configId: number | null) =>
  {
    setSelectedConfigId(configId)
  }, [])

  return {
    loading,
    // 模型配置
    modelConfigs,
    configsLoading,
    savingConfig,
    selectedConfigId,
    loadModelConfigs,
    handleCreateModel, handleUpdateModel,
    handleSetDefault,
    handleDeleteModel,
    handleCheckHealth,
    handleToggleEnabled,
    handleSelectConfig,
    // 审核设置
    reviewMode,
    setReviewMode,
    maxRewriteCount,
    setMaxRewriteCount,
    saving,
    saved,
    handleSaveReviewSettings,
    // 系统提示词
    prompts,
    promptsLoading,
    loadPrompts,
    selectedAgent,
    setSelectedAgent,
    editContent,
    setEditContent,
    currentPrompt,
    savingPrompt,
    resettingPrompt,
    handleSavePrompt,
    handleResetPrompt,
  }
}
