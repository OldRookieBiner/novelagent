import { useState } from 'react'
import { ChevronDown, Star, Trash2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ModelConfig } from '@/types'

interface ModelConfigItemProps {
  config: ModelConfig
  onSetDefault?: (id: number) => void
  onDelete?: (id: number) => void
  onRefresh?: (id: number) => void
}

export default function ModelConfigItem({
  config,
  onSetDefault,
  onDelete,
  onRefresh,
}: ModelConfigItemProps) {
  const [expanded, setExpanded] = useState(false)

  // 健康状态颜色
  const getHealthColor = (status?: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600'
      case 'unhealthy':
        return 'text-red-600'
      default:
        return 'text-gray-400'
    }
  }

  // 健康状态文本
  const getHealthText = (status?: string) => {
    switch (status) {
      case 'healthy':
        return '健康'
      case 'unhealthy':
        return '异常'
      default:
        return '未知'
    }
  }

  // 单模型配置
  if (config.provider_type === 'single') {
    return (
      <div className="flex items-center p-3 border rounded-lg hover:bg-muted/50 transition-colors">
        {/* 默认标记 */}
        {config.is_default ? (
          <Star className="h-4 w-4 text-yellow-500 mr-2 fill-yellow-500" />
        ) : (
          <button
            onClick={() => onSetDefault?.(config.id)}
            className="h-4 w-4 mr-2 text-gray-300 hover:text-yellow-500 transition-colors"
            title="设为默认"
          >
            <Star className="h-4 w-4" />
          </button>
        )}

        {/* 名称 */}
        <span className="font-medium flex-1">{config.name}</span>

        {/* 健康状态 */}
        <span className={cn('text-sm mr-3', getHealthColor(config.health_status))}>
          {getHealthText(config.health_status)}
          {config.health_latency && ` · ${config.health_latency}ms`}
        </span>

        {/* 操作按钮 */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onRefresh?.(config.id)}
          title="健康检查"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete?.(config.id)}
          title="删除"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  // Coding Plan 配置（可展开）
  const enabledCount = config.models?.filter(m => m.is_enabled).length || 0

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* 标题行 */}
      <div
        className="flex items-center p-3 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronDown
          className={cn('h-4 w-4 mr-2 transition-transform', expanded && 'rotate-180')}
        />

        {/* 默认标记 */}
        {config.is_default ? (
          <Star className="h-4 w-4 text-yellow-500 mr-2 fill-yellow-500" />
        ) : (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onSetDefault?.(config.id)
            }}
            className="h-4 w-4 mr-2 text-gray-300 hover:text-yellow-500 transition-colors"
            title="设为默认"
          >
            <Star className="h-4 w-4" />
          </button>
        )}

        {/* 名称 */}
        <span className="font-medium flex-1">{config.name}</span>

        {/* 模型数量 */}
        <span className="text-muted-foreground text-sm mr-3">
          {enabledCount} 个模型
        </span>
      </div>

      {/* 展开的模型列表 */}
      {expanded && config.models && (
        <div className="border-t bg-muted/30 p-3 pl-10 space-y-2">
          {config.models.map((model) => (
            <div key={model.id} className="flex items-center text-sm">
              <span className={cn('flex-1', !model.is_enabled && 'text-muted-foreground')}>
                {model.name}
              </span>
              <span className={cn('mr-3', getHealthColor(model.health_status))}>
                {getHealthText(model.health_status)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
