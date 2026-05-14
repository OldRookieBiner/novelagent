import { Star, Plus } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import type { ModelConfig } from '@/types'

/**
 * 模型配置侧边栏 Props
 */
interface ModelConfigSidebarProps
{
  configs: ModelConfig[]
  selectedId: number | null
  onSelect: (id: number) => void
  onToggleEnabled: (id: number, enabled: boolean) => void
  onAdd: () => void
}

/**
 * 健康状态文本映射
 */
function getHealthText(config: ModelConfig): string
{
  if (!config.health_status) return '未检查'
  if (config.health_status === 'healthy') return '健康'
  if (config.health_status === 'unhealthy') return '未连接'
  return config.health_status
}

/**
 * 模型配置侧边栏 — 左侧配置列表，含启用开关
 */
export function ModelConfigSidebar(
  { configs, selectedId, onSelect, onToggleEnabled, onAdd }: ModelConfigSidebarProps
)
{
  return (
    <div className="w-[260px] border-r border-slate-200 bg-slate-50 flex flex-col h-full">
      {/* 标题 */}
      <div className="px-4 py-3 border-b border-slate-200">
        <h2 className="text-sm font-semibold text-slate-700">模型配置</h2>
      </div>

      {/* 配置列表 */}
      <div className="flex-1 overflow-y-auto py-1">
        {configs.length === 0 && (
          <div className="p-4 text-sm text-slate-400 text-center">暂无配置</div>
        )}
        {configs.map((config) =>
        {
          const isSelected = config.id === selectedId
          const modelCount = config.models?.length ?? 0
          const healthText = getHealthText(config)

          return (
            <div
              key={config.id}
              onClick={() => onSelect(config.id)}
              className={`
                px-3 py-2.5 cursor-pointer flex items-center justify-between
                border-l-[3px] transition-colors
                ${isSelected
                  ? 'bg-blue-50 border-l-blue-500'
                  : 'border-l-transparent hover:bg-slate-100'
                }
                ${!config.is_enabled ? 'opacity-60' : ''}
              `}
            >
              {/* 左侧内容区 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center">
                  {/* 默认标记星号 */}
                  {config.is_default ? (
                    <Star className="h-3 w-3 text-amber-500 mr-1.5 shrink-0 fill-amber-500" />
                  ) : (
                    <Star className="h-3 w-3 text-slate-300 mr-1.5 shrink-0" />
                  )}
                  {/* 配置名称，超长省略 */}
                  <span
                    className={`text-[13px] font-medium truncate ${isSelected ? 'text-blue-800' : 'text-slate-700'}`}
                  >
                    {config.name}
                  </span>
                </div>
                {/* 副标题：模型数量 · 健康状态 */}
                <div className="text-[11px] text-slate-500 mt-0.5 pl-[18px]">
                  {modelCount} 个模型 · {healthText}
                </div>
              </div>

              {/* 启用开关 — 阻止冒泡，避免触发选中 */}
              <div
                onClick={(e) => e.stopPropagation()}
                className="shrink-0 ml-2"
              >
                <Switch
                  checked={config.is_enabled}
                  onCheckedChange={(checked) => onToggleEnabled(config.id, checked)}
                  className="scale-[0.8]"
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* 添加配置按钮 */}
      <div className="px-3 py-3 border-t border-slate-200">
        <button
          onClick={onAdd}
          className="w-full py-1.5 border border-dashed border-slate-300 rounded-md bg-white text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-600 transition-colors flex items-center justify-center gap-1"
        >
          <Plus className="h-3.5 w-3.5" />
          添加配置
        </button>
      </div>
    </div>
  )
}
