import { useState, useEffect } from 'react'
import { ModelConfig, ModelConfigCreate, ModelConfigUpdate, ProviderInfo } from '@/types'
import { modelConfigsApi } from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { ModelConfigSidebar } from './ModelConfigSidebar'
import { ModelConfigDetail } from './ModelConfigDetail'

interface ModelConfigPanelProps
{
  modelConfigs: ModelConfig[]
  configsLoading: boolean
  selectedConfigId: number | null
  savingConfig: boolean
  onCreateModel: (data: ModelConfigCreate) => Promise<void>
  onUpdateModel: (configId: number, data: ModelConfigUpdate) => Promise<void>
  onSetDefault: (configId: number) => Promise<void>
  onDeleteModel: (configId: number) => Promise<void>
  onCheckHealth: (configId: number) => Promise<void>
  onToggleEnabled: (configId: number, enabled: boolean) => void
  onSelectConfig: (configId: number | null) => void
}

export default function ModelConfigPanel({
  modelConfigs,
  configsLoading,
  selectedConfigId,
  savingConfig,
  onCreateModel,
  onUpdateModel,
  onSetDefault,
  onDeleteModel,
  onCheckHealth,
  onToggleEnabled,
  onSelectConfig,
}: ModelConfigPanelProps)
{
  const [providers, setProviders] = useState<ProviderInfo[]>([])

  // 加载提供商列表
  useEffect(() =>
  {
    modelConfigsApi.getProviders().then((data) =>
    {
      setProviders(data.providers)
    }).catch(console.error)
  }, [])

  // 获取选中的配置
  const selectedConfig = modelConfigs.find((c) => c.id === selectedConfigId) ?? null

  // 添加新配置
  const handleAdd = () =>
  {
    onSelectConfig(null)  // null = 新建模式
  }

  if (configsLoading)
  {
    return <LoadingSpinner text="加载中..." />
  }

  return (
    <div className="flex border rounded-xl overflow-hidden bg-white min-h-[520px]">
      {/* 左栏：配置列表 */}
      <ModelConfigSidebar
        configs={modelConfigs}
        selectedId={selectedConfigId}
        onSelect={onSelectConfig}
        onToggleEnabled={onToggleEnabled}
        onAdd={handleAdd}
      />

      {/* 右栏：配置详情 */}
      <ModelConfigDetail
        config={selectedConfig}
        providers={providers}
        onCreate={onCreateModel}
        onUpdate={onUpdateModel}
        onSetDefault={onSetDefault}
        onDelete={() =>
        {
          if (selectedConfigId)
          {
            onDeleteModel(selectedConfigId)
          }
        }}
        onCheckHealth={onCheckHealth}
        saving={savingConfig}
      />
    </div>
  )
}
