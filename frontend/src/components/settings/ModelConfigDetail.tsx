import { useState, useEffect } from 'react'
import { ModelConfig, ModelConfigCreate, ModelItem, ProviderInfo } from '@/types'
import ModelCard from './ModelCard'
import FetchModelsDialog from './FetchModelsDialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Globe, Search, Star, Trash2 } from 'lucide-react'

/**
 * 模型配置详情 Props
 */
interface ModelConfigDetailProps
{
  config: ModelConfig | null  // null = 新建模式
  providers: ProviderInfo[]
  onSave: (data: ModelConfigCreate, configId?: number) => Promise<void>
  onSetDefault: (configId: number) => Promise<void>
  onDelete: () => void
  onCheckHealth: () => void
  saving: boolean
}

/**
 * 模型配置详情面板 — 右侧编辑/查看区域
 * - 编辑模式：config !== null，显示已有配置详情
 * - 新建模式：config === null，空表单
 */
export function ModelConfigDetail({
  config,
  providers,
  onSave,
  onSetDefault,
  onDelete,
  onCheckHealth,
  saving,
}: ModelConfigDetailProps)
{
  // 本地表单状态
  const [provider, setProvider] = useState(config?.provider ?? '')
  const [name, setName] = useState(config?.name ?? '')
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? '')
  const [apiKey, setApiKey] = useState('')
  const [models, setModels] = useState<ModelItem[]>(config?.models ?? [])
  const [fetchDialogOpen, setFetchDialogOpen] = useState(false)

  // 记录 baseUrl 是否由提供商自动填充（用于自动填充逻辑）
  const [baseUrlAutoFilled, setBaseUrlAutoFilled] = useState(false)

  // 当 config prop 变化时（用户选择不同配置），重置本地状态
  useEffect(() =>
  {
    setProvider(config?.provider ?? '')
    setName(config?.name ?? '')
    setBaseUrl(config?.base_url ?? '')
    setApiKey('')
    setModels(config?.models ?? [])
    setBaseUrlAutoFilled(false)
  }, [config])

  /**
   * 提供商变更时，自动填充 API 地址
   * 仅在 baseUrl 之前由自动填充设置、或为空时才自动填充
   */
  const handleProviderChange = (newProvider: string) =>
  {
    setProvider(newProvider)

    // 查找匹配的提供商，自动填充 baseUrl
    const found = providers.find(p => p.id === newProvider)
    if (found)
    {
      // 仅在未手动编辑过、或之前是自动填充时才覆盖
      if (!baseUrl || baseUrlAutoFilled)
      {
        setBaseUrl(found.base_url)
        setBaseUrlAutoFilled(true)
      }
    }
  }

  /**
   * 手动编辑 baseUrl 时，标记为非自动填充
   */
  const handleBaseUrlChange = (value: string) =>
  {
    setBaseUrl(value)
    setBaseUrlAutoFilled(false)
  }

  /**
   * 添加模型（来自 FetchModelsDialog）
   */
  const handleAddModel = (model: { id: string; name: string }) =>
  {
    setModels(prev =>
    {
      // 避免重复添加
      if (prev.some(m => m.id === model.id)) return prev
      return [
        ...prev,
        {
          id: model.id,
          name: model.name,
          is_enabled: true,
          health_status: undefined,
          temperature: 0.7,
          reasoning_effort: 'none',
        },
      ]
    })
  }

  /**
   * 移除模型（来自 FetchModelsDialog）
   */
  const handleRemoveModel = (modelId: string) =>
  {
    setModels(prev => prev.filter(m => m.id !== modelId))
  }

  /**
   * 更新模型温度
   */
  const handleTemperatureChange = (modelId: string, val: number) =>
  {
    setModels(prev =>
      prev.map(m =>
        m.id === modelId ? { ...m, temperature: val } : m
      )
    )
  }

  /**
   * 更新模型思考强度
   */
  const handleReasoningEffortChange = (modelId: string, val: string) =>
  {
    setModels(prev =>
      prev.map(m =>
        m.id === modelId ? { ...m, reasoning_effort: val } : m
      )
    )
  }

  /**
   * 移除模型（来自 ModelCard）
   */
  const handleModelCardRemove = (modelId: string) =>
  {
    setModels(prev => prev.filter(m => m.id !== modelId))
  }

  /**
   * 保存配置
   */
  const handleSave = async () =>
  {
    const data: ModelConfigCreate = {
      name,
      provider,
      provider_type: 'single',  // 固定为 single，前端不再用它做分支判断
      base_url: baseUrl,
      model_name: models.length > 0 ? models[0].name : undefined,
      models,
      api_key: apiKey || undefined,
    }
    await onSave(data, config?.id)
  }

  // 是否为编辑模式
  const isEditMode = config !== null

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* 顶部栏：配置名称 + 操作按钮 */}
      <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between shrink-0">
        <h2 className="text-sm font-semibold text-slate-800 truncate">
          {isEditMode ? (config?.name ?? '未命名配置') : '添加模型配置'}
        </h2>

        {isEditMode && (
          <div className="flex items-center gap-2 shrink-0">
            {/* 设为默认按钮 */}
            {!config?.is_default && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                {
                  if (config?.id) onSetDefault(config.id)
                }}
                className="text-xs h-7"
              >
                <Star className="h-3.5 w-3.5 mr-1" />
                设为默认
              </Button>
            )}

            {/* 健康检查按钮 */}
            <Button
              variant="outline"
              size="sm"
              onClick={onCheckHealth}
              className="text-xs h-7"
            >
              <Globe className="h-3.5 w-3.5 mr-1" />
              健康检查
            </Button>

            {/* 删除按钮 */}
            <Button
              variant="outline"
              size="sm"
              onClick={onDelete}
              className="text-xs h-7 text-red-500 border-red-300 hover:bg-red-50 hover:text-red-600"
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              删除
            </Button>
          </div>
        )}
      </div>

      {/* 可滚动内容区 */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {/* 基本信息网格 — 2列 */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {/* 提供商 */}
          <div>
            <Label className="text-xs text-slate-500 mb-1 block">提供商</Label>
            <Select
              value={provider}
              onValueChange={handleProviderChange}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue placeholder="选择提供商" />
              </SelectTrigger>
              <SelectContent>
                {providers.map(p => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 显示名称 */}
          <div>
            <Label className="text-xs text-slate-500 mb-1 block">显示名称</Label>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="输入显示名称"
              className="h-8 text-sm"
            />
          </div>

          {/* API 地址 */}
          <div>
            <Label className="text-xs text-slate-500 mb-1 block">API 地址</Label>
            <Input
              value={baseUrl}
              onChange={e => handleBaseUrlChange(e.target.value)}
              placeholder="https://api.example.com/v1"
              className="h-8 text-sm"
            />
          </div>

          {/* API Key */}
          <div>
            <Label className="text-xs text-slate-500 mb-1 block">API Key</Label>
            <Input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder={isEditMode && config?.has_api_key ? 'sk-••••••••' : '输入 API Key'}
              className="h-8 text-sm"
            />
          </div>
        </div>

        {/* 分隔线 */}
        <div className="border-t border-slate-200 my-4" />

        {/* 模型区域 */}
        <div>
          {/* 头部：模型标签 + 获取模型按钮 */}
          <div className="flex items-center justify-between mb-2">
            <Label className="text-xs text-slate-500">模型</Label>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFetchDialogOpen(true)}
              className="text-xs h-7"
            >
              <Search className="h-3.5 w-3.5 mr-1" />
              获取模型
            </Button>
          </div>

          {/* 模型卡片列表 */}
          {models.length > 0 ? (
            <div className="space-y-0">
              {models.map(model => (
                <ModelCard
                  key={model.id}
                  model={model}
                  onTemperatureChange={(val) => handleTemperatureChange(model.id, val)}
                  onReasoningEffortChange={(val) => handleReasoningEffortChange(model.id, val)}
                  onRemove={() => handleModelCardRemove(model.id)}
                />
              ))}
            </div>
          ) : (
            /* 空状态 */
            <div className="border border-dashed border-slate-300 rounded-lg py-8 flex items-center justify-center text-sm text-slate-400">
              点击"获取模型"按钮添加模型
            </div>
          )}
        </div>
      </div>

      {/* 底部栏 — 新建模式才显示 */}
      {!isEditMode && (
        <div className="px-5 py-3 border-t border-slate-200 flex items-center justify-end gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-7"
            onClick={() =>
            {
              // 重置表单
              setProvider('')
              setName('')
              setBaseUrl('')
              setApiKey('')
              setModels([])
              setBaseUrlAutoFilled(false)
            }}
          >
            取消
          </Button>
          <Button
            size="sm"
            className="text-xs h-7"
            onClick={handleSave}
            disabled={saving || !name.trim()}
          >
            {saving ? '添加中...' : '添加配置'}
          </Button>
        </div>
      )}

      {/* 获取模型对话框 */}
      <FetchModelsDialog
        open={fetchDialogOpen}
        onClose={() => setFetchDialogOpen(false)}
        existingModelIds={models.map(m => m.id)}
        onAddModel={handleAddModel}
        onRemoveModel={handleRemoveModel}
        provider={provider}
        baseUrl={baseUrl}
        apiKey={apiKey}
      />
    </div>
  )
}
