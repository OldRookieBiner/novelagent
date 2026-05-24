// 灵感字段组容器 — 卡片式布局 + Agent 状态标签

import type { ReactNode } from 'react'
import type { FieldStatus } from '@/lib/inspiration/types'

interface InspirationFieldGroupProps
{
  title: string
  icon: string
  required?: boolean
  children: ReactNode
  /** 字段组内所有字段的最高优先级状态 */
  groupStatus?: FieldStatus
  /** 是否可折叠 */
  collapsible?: boolean
  collapsed?: boolean
  onToggleCollapse?: () => void
  /** 已填选填项数 */
  optionalFilledCount?: number
}

const STATUS_CONFIG: Record<string, { label: string; borderClass: string; headerBg: string; badgeClass: string }> = {
  agent_populated: {
    label: 'Agent 已提取',
    borderClass: 'border-indigo-200',
    headerBg: 'bg-indigo-50',
    badgeClass: 'bg-indigo-600 text-white',
  },
  agent_asking: {
    label: 'Agent 询问中',
    borderClass: 'border-amber-300',
    headerBg: 'bg-amber-50',
    badgeClass: 'bg-amber-500 text-white',
  },
  empty: {
    label: '',
    borderClass: 'border-gray-200',
    headerBg: 'bg-white',
    badgeClass: '',
  },
  user_filled: {
    label: '',
    borderClass: 'border-gray-200',
    headerBg: 'bg-white',
    badgeClass: '',
  },
}

export function InspirationFieldGroup({
  title, icon, required, children, groupStatus = 'empty',
  collapsible, collapsed, onToggleCollapse, optionalFilledCount,
}: InspirationFieldGroupProps)
{
  const config = STATUS_CONFIG[groupStatus] || STATUS_CONFIG.empty

  return (
    <div className={`rounded-lg border overflow-hidden ${config.borderClass}`}>
      <div className={`flex items-center justify-between px-3.5 py-2.5 ${config.headerBg}`}>
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-xs font-bold text-slate-800">
            {title}
            {required && <span className="text-red-500 ml-1 text-[10px]">*必填</span>}
          </span>
          {!required && optionalFilledCount !== undefined && optionalFilledCount > 0 && (
            <span className="text-[10px] text-indigo-500">· 已填 {optionalFilledCount} 项</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {config.label && (
            <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${config.badgeClass}`}>
              {config.label}
            </span>
          )}
          {collapsible && (
            <button onClick={onToggleCollapse} className="text-xs text-muted-foreground hover:text-foreground">
              {collapsed ? '▾ 点击展开' : '▴ 收起'}
            </button>
          )}
        </div>
      </div>
      {!collapsed && <div className="p-3.5">{children}</div>}
    </div>
  )
}
