import { useState, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { modelConfigsApi } from '@/lib/api'
import type { ModelConfigCreate, ProviderInfo, ModelItem } from '@/types'

interface AddModelDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: ModelConfigCreate) => Promise<void>
  loading: boolean
}

export default function AddModelDialog({
  open,
  onClose,
  onSubmit,
  loading,
}: AddModelDialogProps) {
  // 提供商列表
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [loadingProviders, setLoadingProviders] = useState(false)

  // 表单字段
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [modelName, setModelName] = useState('') // 单模型配置使用

  // Coding Plan 相关
  const [availableModels, setAvailableModels] = useState<ModelItem[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)

  // 错误状态
  const [errors, setErrors] = useState<Record<string, string>>({})

  // 获取选中的提供商信息
  const selectedProviderInfo = providers.find(p => p.id === selectedProvider)
  const isCodingPlan = selectedProviderInfo?.provider_type === 'coding_plan'
  const isCustom = selectedProvider === 'custom'

  // 加载提供商列表
  useEffect(() => {
    if (open) {
      loadProviders()
    }
  }, [open])

  // 重置表单
  const resetForm = () => {
    setSelectedProvider('')
    setName('')
    setBaseUrl('')
    setApiKey('')
    setModelName('')
    setAvailableModels([])
    setFetchError(null)
    setErrors({})
  }

  // 加载提供商
  const loadProviders = async () => {
    setLoadingProviders(true)
    try {
      const result = await modelConfigsApi.getProviders()
      // 添加自定义选项
      const customProvider: ProviderInfo = {
        id: 'custom',
        name: '自定义',
        provider_type: 'single',
        base_url: '',
      }
      setProviders([customProvider, ...result.providers])
    } catch (err) {
      console.error('Failed to load providers:', err)
    } finally {
      setLoadingProviders(false)
    }
  }

  // 选择提供商时自动填充 base_url
  const handleProviderChange = (providerId: string) => {
    setSelectedProvider(providerId)
    const provider = providers.find(p => p.id === providerId)
    if (provider && providerId !== 'custom') {
      setBaseUrl(provider.base_url)
      // 自动填充名称
      if (!name) {
        setName(provider.name)
      }
    } else {
      setBaseUrl('')
    }
    // 重置模型相关
    setModelName('')
    setAvailableModels([])
    setFetchError(null)
    setErrors({})
  }

  // 获取模型列表（Coding Plan）
  const handleFetchModels = async () => {
    if (!baseUrl.trim()) {
      setErrors({ baseUrl: '请输入 API 地址' })
      return
    }

    setFetchingModels(true)
    setFetchError(null)

    try {
      const result = await modelConfigsApi.fetchModels({
        provider: selectedProvider,
        base_url: baseUrl,
        api_key: apiKey,
      })

      if (result.error) {
        setFetchError(result.error)
      } else {
        // 转换为 ModelItem 格式，默认全部启用
        const models: ModelItem[] = result.models.map(m => ({
          id: m.id,
          name: m.name,
          is_enabled: true,
          health_status: undefined,
        }))
        setAvailableModels(models)
      }
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : '获取模型列表失败')
    } finally {
      setFetchingModels(false)
    }
  }

  // 切换模型启用状态
  const toggleModelEnabled = (modelId: string) => {
    setAvailableModels(prev =>
      prev.map(m => (m.id === modelId ? { ...m, is_enabled: !m.is_enabled } : m))
    )
  }

  // 全选/取消全选
  const toggleAllModels = (enabled: boolean) => {
    setAvailableModels(prev => prev.map(m => ({ ...m, is_enabled: enabled })))
  }

  // 获取表单数据
  const getFormData = (): ModelConfigCreate | null => {
    const newErrors: Record<string, string> = {}

    if (!selectedProvider) newErrors.provider = '请选择提供商'
    if (!name.trim()) newErrors.name = '请输入显示名称'
    if (!baseUrl.trim()) newErrors.baseUrl = '请输入 API 地址'

    // 单模型验证
    if (!isCodingPlan && !modelName.trim()) {
      newErrors.modelName = '请输入模型名称'
    }

    // Coding Plan 验证
    if (isCodingPlan) {
      const enabledModels = availableModels.filter(m => m.is_enabled)
      if (enabledModels.length === 0) {
        newErrors.models = '请至少选择一个模型'
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return null
    }

    const data: ModelConfigCreate = {
      name: name.trim(),
      provider: selectedProvider,
      provider_type: isCodingPlan ? 'coding_plan' : 'single',
      base_url: baseUrl.trim(),
      api_key: apiKey.trim() || undefined,
    }

    if (isCodingPlan) {
      data.models = availableModels.filter(m => m.is_enabled)
    } else {
      data.model_name = modelName.trim()
    }

    return data
  }

  // 提交表单
  const handleSubmit = async () => {
    const data = getFormData()
    if (!data) return

    try {
      await onSubmit(data)
      resetForm()
      onClose()
    } catch (err) {
      // 错误由父组件处理
    }
  }

  // 关闭对话框
  const handleClose = () => {
    resetForm()
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>添加模型配置</DialogTitle>
          <DialogDescription>
            选择提供商并配置 API 信息，添加新的模型配置
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* 提供商选择 */}
          <div className="space-y-2">
            <Label htmlFor="provider">
              提供商 <span className="text-red-500">*</span>
            </Label>
            <Select
              value={selectedProvider}
              onValueChange={handleProviderChange}
              disabled={loadingProviders}
            >
              <SelectTrigger id="provider">
                <SelectValue placeholder={loadingProviders ? '加载中...' : '选择提供商'} />
              </SelectTrigger>
              <SelectContent>
                {providers.map(provider => (
                  <SelectItem key={provider.id} value={provider.id}>
                    {provider.name}
                    {provider.provider_type === 'coding_plan' && ' (套餐)'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.provider && (
              <p className="text-red-500 text-xs">{errors.provider}</p>
            )}
          </div>

          {/* 显示名称 */}
          <div className="space-y-2">
            <Label htmlFor="name">
              显示名称 <span className="text-red-500">*</span>
            </Label>
            <Input
              id="name"
              value={name}
              onChange={e => {
                setName(e.target.value)
                if (errors.name) setErrors({ ...errors, name: '' })
              }}
              placeholder="如：我的 OpenAI"
            />
            {errors.name && (
              <p className="text-red-500 text-xs">{errors.name}</p>
            )}
          </div>

          {/* API 地址 */}
          <div className="space-y-2">
            <Label htmlFor="baseUrl">
              API 地址 <span className="text-red-500">*</span>
            </Label>
            <Input
              id="baseUrl"
              value={baseUrl}
              onChange={e => {
                setBaseUrl(e.target.value)
                if (errors.baseUrl) setErrors({ ...errors, baseUrl: '' })
              }}
              placeholder="如：https://api.openai.com/v1"
              disabled={!isCustom && selectedProvider !== ''}
            />
            {errors.baseUrl && (
              <p className="text-red-500 text-xs">{errors.baseUrl}</p>
            )}
            {isCustom && (
              <p className="text-xs text-muted-foreground">自定义提供商需输入完整的 API 地址</p>
            )}
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="可选，部分服务需要"
            />
            <p className="text-xs text-muted-foreground">部分本地部署服务无需 API Key</p>
          </div>

          {/* 单模型配置：模型名称 */}
          {!isCodingPlan && selectedProvider && (
            <div className="space-y-2">
              <Label htmlFor="modelName">
                模型名称 <span className="text-red-500">*</span>
              </Label>
              <Input
                id="modelName"
                value={modelName}
                onChange={e => {
                  setModelName(e.target.value)
                  if (errors.modelName) setErrors({ ...errors, modelName: '' })
                }}
                placeholder="如：gpt-4"
              />
              {errors.modelName && (
                <p className="text-red-500 text-xs">{errors.modelName}</p>
              )}
            </div>
          )}

          {/* Coding Plan 配置：获取模型列表 */}
          {isCodingPlan && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>模型列表</Label>
                <div className="flex gap-2">
                  {availableModels.length > 0 && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleAllModels(true)}
                      >
                        全选
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleAllModels(false)}
                      >
                        取消全选
                      </Button>
                    </>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleFetchModels}
                    disabled={fetchingModels}
                  >
                    {fetchingModels ? (
                      <>
                        <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                        获取中...
                      </>
                    ) : (
                      '获取模型'
                    )}
                  </Button>
                </div>
              </div>

              {fetchError && (
                <p className="text-red-500 text-xs">{fetchError}</p>
              )}

              {availableModels.length > 0 ? (
                <div className="border rounded-lg max-h-48 overflow-y-auto">
                  {availableModels.map(model => (
                    <div
                      key={model.id}
                      className="flex items-center gap-3 p-2 border-b last:border-b-0 hover:bg-muted/50"
                    >
                      <Checkbox
                        checked={model.is_enabled}
                        onCheckedChange={() => toggleModelEnabled(model.id)}
                      />
                      <span className={model.is_enabled ? '' : 'text-muted-foreground'}>
                        {model.name}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                !fetchError && (
                  <p className="text-sm text-muted-foreground">
                    点击"获取模型"按钮加载可用模型列表
                  </p>
                )
              )}

              {errors.models && (
                <p className="text-red-500 text-xs">{errors.models}</p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '添加中...' : '添加配置'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
