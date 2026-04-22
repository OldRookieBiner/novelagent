import { Button } from '@/components/ui/button'
import type { ModelConfig } from '@/types'

interface ModelConfigCardProps {
  config: ModelConfig
  onHealthCheck: () => void
  onEdit: () => void
  onSetDefault: () => void
  onToggleEnabled: () => void
  onDelete?: () => void
  checkingHealth: boolean
}

export default function ModelConfigCard({
  config,
  onHealthCheck,
  onEdit,
  onSetDefault,
  onToggleEnabled,
  onDelete,
  checkingHealth,
}: ModelConfigCardProps) {
  // 状态指示器颜色
  const statusColor: Record<string, string> = {
    healthy: 'bg-green-500',
    unhealthy: 'bg-red-500',
    unknown: 'bg-gray-300',
  }

  // 卡片样式：启用的模型显示蓝色边框
  const cardClasses = config.is_enabled
    ? 'border-2 border-blue-500 bg-blue-50'
    : 'border rounded-lg opacity-60'

  return (
    <div className={`${cardClasses} p-4 mb-4 transition-all hover:shadow-md`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* 状态指示点 */}
          <div className={`w-3 h-3 rounded-full ${statusColor[config.health_status || 'unknown']}`} />

          <div>
            <div className="font-medium">{config.name}</div>
            <div className="text-sm text-gray-500">模型: {config.model_name}</div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* 健康状态 */}
          {config.health_status === 'healthy' && config.health_latency && (
            <span className="text-sm text-green-600">延迟: {config.health_latency}ms</span>
          )}
          {config.health_status === 'unhealthy' && (
            <span className="text-sm text-red-500">连接失败</span>
          )}
          {!config.has_api_key && (
            <span className="text-sm text-gray-400">未配置 API Key</span>
          )}
          {!config.is_enabled && (
            <span className="text-sm text-gray-400">已停用</span>
          )}

          {/* 默认标签 */}
          {config.is_default && (
            <span className="text-xs bg-blue-500 text-white px-2 py-1 rounded">默认</span>
          )}
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2 mt-3 flex-wrap">
        {config.has_api_key && (
          <Button
            variant="outline"
            size="sm"
            onClick={onHealthCheck}
            disabled={checkingHealth}
          >
            {checkingHealth ? '检查中...' : '健康检查'}
          </Button>
        )}

        {!config.has_api_key && (
          <Button size="sm" onClick={onEdit}>
            配置 API Key
          </Button>
        )}

        {config.has_api_key && !config.is_default && (
          <Button variant="outline" size="sm" onClick={onEdit}>
            编辑
          </Button>
        )}

        {config.is_enabled && !config.is_default && (
          <Button variant="outline" size="sm" onClick={onSetDefault}>
            设为默认
          </Button>
        )}

        {!config.is_enabled && (
          <Button variant="outline" size="sm" onClick={onToggleEnabled}>
            启用
          </Button>
        )}

        {config.is_enabled && !config.is_default && (
          <Button variant="outline" size="sm" onClick={onToggleEnabled}>
            停用
          </Button>
        )}

        {!config.is_default && onDelete && (
          <Button variant="outline" size="sm" className="text-red-500 hover:bg-red-50" onClick={onDelete}>
            删除
          </Button>
        )}
      </div>
    </div>
  )
}
