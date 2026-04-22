import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { ModelConfigCreate } from '@/types'

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
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [modelName, setModelName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const resetForm = () => {
    setName('')
    setBaseUrl('')
    setModelName('')
    setApiKey('')
    setErrors({})
  }

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {}
    if (!name.trim()) newErrors.name = '请输入显示名称'
    if (!baseUrl.trim()) newErrors.baseUrl = '请输入 API 地址'
    if (!modelName.trim()) newErrors.modelName = '请输入模型名称'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    try {
      await onSubmit({
        name: name.trim(),
        provider: 'custom',
        base_url: baseUrl.trim(),
        model_name: modelName.trim(),
        api_key: apiKey.trim() || undefined,
      })
      resetForm()
      onClose()
    } catch (err) {
      // 错误由父组件处理
    }
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-[420px] max-w-[90vw]">
        <div className="text-lg font-medium mb-4">添加自定义模型</div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              显示名称 <span className="text-red-500">*</span>
            </label>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (errors.name) setErrors({ ...errors, name: '' })
              }}
              placeholder="如：我的 Ollama"
              className={errors.name ? 'border-red-500' : ''}
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              API 地址 <span className="text-red-500">*</span>
            </label>
            <Input
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value)
                if (errors.baseUrl) setErrors({ ...errors, baseUrl: '' })
              }}
              placeholder="如：http://localhost:11434/v1"
              className={errors.baseUrl ? 'border-red-500' : ''}
            />
            {errors.baseUrl && <p className="text-red-500 text-xs mt-1">{errors.baseUrl}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              模型名称 <span className="text-red-500">*</span>
            </label>
            <Input
              value={modelName}
              onChange={(e) => {
                setModelName(e.target.value)
                if (errors.modelName) setErrors({ ...errors, modelName: '' })
              }}
              placeholder="如：llama3"
              className={errors.modelName ? 'border-red-500' : ''}
            />
            {errors.modelName && <p className="text-red-500 text-xs mt-1">{errors.modelName}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">API Key</label>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="可选，部分服务需要"
            />
            <p className="text-xs text-gray-400 mt-1">部分本地部署服务无需 API Key</p>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="outline" onClick={handleClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '添加中...' : '添加模型'}
          </Button>
        </div>
      </div>
    </div>
  )
}
