// MessageAnchorRail.tsx — 右侧消息锚点列（快速跳转）

import { useState, useRef, useCallback, useEffect } from 'react'
import type { AiMessage } from '@/stores/workbenchStore'
import { truncateTitle } from './AgentChatPanel'

interface MessageAnchorRailProps
{
  userMessages: AiMessage[]
  activeId: string | null
  onJump: (id: string) => void
}

function cn(...classes: (string | boolean | undefined)[]): string
{
  return classes.filter(Boolean).join(' ')
}

export function MessageAnchorRail({
  userMessages,
  activeId,
  onJump,
}: MessageAnchorRailProps)
{
  const [showTooltip, setShowTooltip] = useState(false)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleEnter = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    setShowTooltip(true)
  }, [])

  const handleLeave = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    closeTimerRef.current = setTimeout(() => setShowTooltip(false), 200)
  }, [])

  useEffect(() => {
    return () =>
    {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    }
  }, [])

  if (userMessages.length < 2) return null

  return (
    <div
      // 视觉宽度 12px（横线在右）；用 pl-2 + w-[20px] 把 hover 热区扩到 20px，避免按钮因 8-12px 横向尺寸命中过窄；外层 pointer-events-none，按钮 pointer-events-auto 捕捉点击
      className="fixed right-3 top-1/2 -translate-y-1/2 flex flex-col items-end gap-1.5 w-[20px] pl-2 z-50 pointer-events-none"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {userMessages.map((msg, i) => {
        const isActive = msg.id === activeId
        return (
          <button
            key={msg.id}
            type="button"
            onClick={() => onJump(msg.id)}
            className={cn(
              'pointer-events-auto rounded-full transition-all duration-150 h-[2px]',
              isActive
                ? 'w-[12px] bg-primary'
                : 'w-[8px] bg-muted-foreground/30 hover:bg-muted-foreground/60'
            )}
            aria-label={`跳转到第 ${i + 1} 条消息`}
            title={truncateTitle(msg.content)}
          />
        )
      })}

      {showTooltip && (
        <div
          role="tooltip"
          className="pointer-events-auto absolute right-full top-1/2 -translate-y-1/2 mr-2 max-w-[280px] min-w-[180px] bg-white border border-gray-200 rounded shadow-md z-50 py-1 overflow-y-auto max-h-[50vh]"
          onMouseEnter={handleEnter}
          onMouseLeave={handleLeave}
        >
          {userMessages.map((msg, i) => {
            const isActive = msg.id === activeId
            return (
              <button
                key={msg.id}
                type="button"
                onClick={() => {
                  onJump(msg.id)
                  setShowTooltip(false)
                }}
                className={cn(
                  'w-full text-left px-2.5 py-1 text-[10px] hover:bg-muted/50 transition-colors truncate',
                  isActive ? 'text-primary font-medium' : 'text-foreground'
                )}
              >
                {i + 1}. {truncateTitle(msg.content)}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
