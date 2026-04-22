import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { modelConfigsApi } from '@/lib/api'
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

  // 测试连接状态
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ status: 'success' | 'error'; message: string } | null>(null)
  const [testedData, setTestedData] = useState<ModelConfigCreate | null>(null)

  const resetForm = () => {
    setName('')
    setBaseUrl('')
    setModelName('')
    setApiKey('')
    setErrors({})
    setTestResult(null)
    setTestedData(null)
  }

  // 获取当前表单数据
  const getFormData = (): ModelConfigCreate => ({
    name: name.trim(),
    provider: 'custom',
    base_url: baseUrl.trim(),
    model_name: modelName.trim(),
    api_key: apiKey.trim() || undefined,
  })

  // 测试连接
  const handleTestConnection = async () => {
    const newErrors: Record<string, string> = {}
    if (!name.trim()) newErrors.name = '请输入显示名称'
    if (!baseUrl.trim()) newErrors.baseUrl = '请输入 API 地址'
    if (!modelName.trim()) newErrors.modelName = '请输入模型名称'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setTesting(true)
    setTestResult(null)

    try {
      const data = getFormData()
      const result = await modelConfigsApi.testConnection(data)

      if (result.status === 'healthy') {
        setTestResult({ status: 'success', message: `连接成功！延迟: ${result.latency}ms` })
        setTestedData(data)
      } else {
        setTestResult({ status: 'error', message: result.error || '连接失败' })
      }
    } catch (err) {
      setTestResult({ status: 'error', message: err instanceof Error ? err.message : '连接测试失败' })
    } finally {
      setTesting(false)
    }
  }

  // 添加模型（仅在测试成功后可用）
  const handleAddModel = async () => {
    if (!testedData) return

    try {
      await onSubmit(testedData)
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

  // 表单字段变化时清除测试结果
  const handleFieldChange = (field: string, value: string, setter: (v: string) => void) => {
    setter(value)
    if (errors[field]) setErrors({ ...errors, [field]: '' })
    if (testResult) {
      setTestResult(null)
      setTestedData(null)
    }
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
              onChange={(e) => handleFieldChange('name', e.target.value, setName)}
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
              onChange={(e) => handleFieldChange('baseUrl', e.target.value, setBaseUrl)}
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
              onChange={(e) => handleFieldChange('modelName', e.target.value, setModelName)}
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
              onChange={(e) => handleFieldChange('apiKey', e.target.value, setApiKey)}
              placeholder="可选，部分服务需要"
            />
            <p className="text-xs text-gray-400 mt-1">部分本地部署服务无需 API Key</p>
          </div>
        </div>

        {/* 测试结果显示 */}
        {testResult && (
          <div className={`mt-4 p-3 rounded-lg ${
            testResult.status === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {testResult.status === 'success' ? '✓ ' : '✕ '}
            {testResult.message}
          </div>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="outline" onClick={handleClose}>
            取消
          </Button>
          <Button variant="outline" onClick={handleTestConnection} disabled={testing}>
            {testing ? '测试中...' : '测试连接'}
          </Button>
          <Button
            onClick={handleAddModel}
            disabled={loading || !testedData}
          >
            {loading ? '添加中...' : '添加模型'}
          </Button>
        </div>
      </div>
    </div>
  )
}
