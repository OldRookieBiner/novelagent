import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ModelConfigItem from '@/components/settings/ModelConfigItem'
import ModelConfigDialog from '@/components/settings/ModelConfigDialog'
import type { ModelConfig, ModelConfigCreate } from '@/types'

interface ModelConfigPanelProps
{
  modelConfigs: ModelConfig[]
  configsLoading: boolean
  onSetDefault: (configId: number) => Promise<void>
  onEdit: (config: ModelConfig) => void
  onDelete: (configId: number) => Promise<void>
  onCheckHealth: (configId: number) => Promise<void>
  onAdd: () => void
  showConfigDialog: boolean
  savingConfig: boolean
  editingConfig: ModelConfig | null
  onSaveModel: (data: ModelConfigCreate) => Promise<void>
  onCloseConfigDialog: () => void
}

export default function ModelConfigPanel({
  modelConfigs,
  configsLoading,
  onSetDefault,
  onEdit,
  onDelete,
  onCheckHealth,
  onAdd,
  showConfigDialog,
  savingConfig,
  editingConfig,
  onSaveModel,
  onCloseConfigDialog,
}: ModelConfigPanelProps)
{
  return (
    <div id="model-panel" role="tabpanel" className="max-w-2xl">
      <h3 className="text-lg font-semibold mb-1">模型配置</h3>
      <p className="text-muted-foreground text-sm mb-6">管理 AI 模型配置，设置默认模型</p>

      {configsLoading ? (
        <LoadingSpinner text="加载中..." />
      ) : (
        <>
          {modelConfigs.map((config) => (
            <ModelConfigItem
              key={config.id}
              config={config}
              onSetDefault={() => onSetDefault(config.id)}
              onEdit={onEdit}
              onDelete={config.is_default ? undefined : () => onDelete(config.id)}
              onRefresh={() => onCheckHealth(config.id)}
            />
          ))}

          {/* 添加自定义模型按钮 */}
          <button
            onClick={onAdd}
            className="w-full border-2 border-dashed border-gray-300 rounded-lg p-4 text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-all"
          >
            + 添加自定义模型
          </button>
        </>
      )}

      {/* 模型配置弹窗 */}
      <ModelConfigDialog
        open={showConfigDialog}
        onClose={onCloseConfigDialog}
        onSubmit={onSaveModel}
        loading={savingConfig}
        editConfig={editingConfig}
      />
    </div>
  )
}
