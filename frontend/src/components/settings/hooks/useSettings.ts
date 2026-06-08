import { useState, useEffect, useCallback } from 'react'
import { settingsApi, modelConfigsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import { toast } from 'sonner'
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types'


export function useSettings()
{
  const [loading, setLoading] = useState(true)

  // 模型配置状态
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [configsLoading, setConfigsLoading] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null)

  // 工作流模式状态
  const setSettings = useSettingsStore((state) => state.setSettings)

  // 加载设置
  useEffect(() =>
  {
    const fetchSettings = async () =>
    {
      try
      {
        const data = await settingsApi.get()
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
  }
}
