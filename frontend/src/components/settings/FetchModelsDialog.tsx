import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { modelConfigsApi } from '@/lib/api'

interface FetchModelsDialogProps
{
  open: boolean
  onClose: () => void
  existingModelIds: string[]
  onAddModel: (model: { id: string; name: string }) => void
  onRemoveModel: (modelId: string) => void
  provider: string
  baseUrl: string
  apiKey: string
  configId?: number  // 已有配置的 ID，优先从后端解密 api_key
}

// 模型项类型（API 返回）
interface FetchedModel
{
  id: string
  name: string
}

export default function FetchModelsDialog({
  open,
  onClose,
  existingModelIds,
  onAddModel,
  onRemoveModel,
  provider,
  baseUrl,
  apiKey,
  configId,
}: FetchModelsDialogProps)
{
  // 搜索关键字
  const [searchQuery, setSearchQuery] = useState('')
  // 获取到的模型列表
  const [models, setModels] = useState<FetchedModel[]>([])
  // 加载状态
  const [loading, setLoading] = useState(false)
  // 错误状态
  const [error, setError] = useState<string | null>(null)

  // 对话框打开时自动获取模型列表
  useEffect(() =>
  {
    if (!open) return

    let cancelled = false
    const fetchModels = async () =>
    {
      setLoading(true)
      setError(null)
      setModels([])
      setSearchQuery('')

      try
      {
        const result = await modelConfigsApi.fetchModels({
          provider,
          base_url: baseUrl,
          api_key: apiKey,
          config_id: configId,
        })

        if (cancelled) return

        if (result.error)
        {
          setError(result.error)
        }
        else
        {
          setModels(result.models)
        }
      }
      catch (err)
      {
        if (cancelled) return
        setError(err instanceof Error ? err.message : '获取模型列表失败')
      }
      finally
      {
        if (!cancelled) setLoading(false)
      }
    }

    fetchModels()
    return () => { cancelled = true }
  }, [open, provider, baseUrl, apiKey, configId])

  // 按搜索关键字过滤模型
  const filteredModels = searchQuery.trim()
    ? models.filter(m =>
        m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.id.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : models

  // 已添加模型数量
  const addedCount = filteredModels.filter(m => existingModelIds.includes(m.id)).length

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose() }}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>获取模型</DialogTitle>
          <DialogDescription>
            从 API 获取可用模型，选择要添加的模型
          </DialogDescription>
        </DialogHeader>

        {/* 搜索输入框 */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索模型名称..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* 模型列表区域 */}
        <div className="border rounded-lg overflow-hidden">
          {loading ? (
            // 加载状态
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              <span className="animate-spin mr-2 h-4 w-4 border-2 border-current border-t-transparent rounded-full" />
              正在获取模型列表...
            </div>
          ) : error ? (
            // 错误状态
            <div className="flex flex-col items-center justify-center py-12 text-sm text-red-500">
              <span>{error}</span>
            </div>
          ) : filteredModels.length === 0 ? (
            // 空状态
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              {models.length === 0 ? '暂无模型' : '没有匹配的模型'}
            </div>
          ) : (
            // 模型列表
            <ScrollArea className="h-[280px]">
              {filteredModels.map(model =>
              {
                const isAdded = existingModelIds.includes(model.id)

                return (
                  <div
                    key={model.id}
                    className={`flex items-center px-3 py-2.5 border-b last:border-b-0 ${
                      isAdded ? 'bg-green-50' : ''
                    }`}
                  >
                    {/* 模型名称 */}
                    <span
                      className={`text-[13px] flex-1 truncate ${
                        isAdded ? 'text-green-800' : ''
                      }`}
                    >
                      {model.name}
                    </span>

                    {/* 已添加标签 */}
                    {isAdded && (
                      <span className="text-[10px] text-green-600 mr-2 whitespace-nowrap">
                        ✓ 已添加
                      </span>
                    )}

                    {/* 操作按钮 */}
                    {isAdded ? (
                      <button
                        onClick={() => onRemoveModel(model.id)}
                        className="px-2.5 py-[3px] border border-red-300 rounded bg-white text-[11px] text-red-500 hover:bg-red-50 transition-colors"
                      >
                        移除
                      </button>
                    ) : (
                      <button
                        onClick={() => onAddModel({ id: model.id, name: model.name })}
                        className="px-2.5 py-[3px] border border-blue-400 rounded bg-white text-[11px] text-blue-500 hover:bg-blue-50 transition-colors"
                      >
                        添加
                      </button>
                    )}
                  </div>
                )
              })}
            </ScrollArea>
          )}
        </div>

        {/* 底部：已添加数量 + 关闭按钮 */}
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-muted-foreground">
            已添加 {addedCount} 个模型
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm border rounded hover:bg-muted transition-colors"
          >
            关闭
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
