import { useState, useEffect, useCallback } from 'react'
import { settingsApi, systemPromptsApi, modelConfigsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import { toast } from 'sonner'
import type { SettingsUpdate, SystemPrompt, ModelConfig, ModelConfigCreate } from '@/types'

const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
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
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null)

  // 审核设置状态
  const [reviewMode, setReviewMode] = useState<'off' | 'manual' | 'auto'>('manual')
  const [maxRewriteCount, setMaxRewriteCount] = useState(3)

  // 工作流模式状态
  const setSettings = useSettingsStore((state) => state.setSettings)
  const workflowMode = useSettingsStore((state) => state.workflowMode)
  const setWorkflowMode = useSettingsStore((state) => state.setWorkflowMode)

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

  // 加载模型配置
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
    setSaved(false)
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

  // 添加或更新模型配置
  const handleSaveModel = useCallback(async (data: ModelConfigCreate) =>
  {
    setSavingConfig(true)
    try
    {
      if (editingConfig)
      {
        await modelConfigsApi.update(editingConfig.id, data)
      }
      else
      {
        await modelConfigsApi.create(data)
      }
      await loadModelConfigs()
    }
    finally
    {
      setSavingConfig(false)
    }
  }, [editingConfig, loadModelConfigs])

  // 打开编辑对话框
  const handleEditModel = useCallback((config: ModelConfig) =>
  {
    setEditingConfig(config)
    setShowConfigDialog(true)
  }, [])

  // 打开新增对话框
  const handleAddModel = useCallback(() =>
  {
    setEditingConfig(null)
    setShowConfigDialog(true)
  }, [])

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
    }
    catch (err)
    {
      console.error('Failed to delete:', err)
      toast.error('删除模型配置失败')
    }
  }, [loadModelConfigs])

  // 健康检查
  const handleCheckHealth = useCallback(async (configId: number) =>
  {
    try
    {
      await modelConfigsApi.checkHealth(configId)
      await loadModelConfigs()
    }
    catch (err)
    {
      console.error('Health check failed:', err)
    }
  }, [loadModelConfigs])

  // 关闭配置对话框
  const handleCloseConfigDialog = useCallback(() =>
  {
    setShowConfigDialog(false)
    setEditingConfig(null)
  }, [])

  return {
    loading,
    // 模型配置
    modelConfigs,
    configsLoading,
    showConfigDialog,
    savingConfig,
    editingConfig,
    loadModelConfigs,
    handleSaveModel,
    handleEditModel,
    handleAddModel,
    handleSetDefault,
    handleDeleteModel,
    handleCheckHealth,
    handleCloseConfigDialog,
    // 审核设置
    reviewMode,
    setReviewMode,
    maxRewriteCount,
    setMaxRewriteCount,
    workflowMode,
    setWorkflowMode,
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
