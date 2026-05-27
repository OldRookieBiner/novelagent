// VolumePanel.tsx — 卷管理面板

import { BookOpen, ChevronRight, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Volume data */
export interface VolumeInfo {
  volumeNumber: number
  title: string | null
  chapterOffset: number
  chapterCount: number
  status: 'active' | 'completed'
  unreclaimedForeshadowings: number
  activeSubplots: number
  characterSnapshot?: { name: string; growthArc?: string }[]
  lastBlockSummary?: string
}

interface VolumePanelProps {
  volumes: VolumeInfo[]
  currentVolume: number
  onVolumeClick?: (volumeNumber: number) => void
}

export function VolumePanel({ volumes, currentVolume, onVolumeClick }: VolumePanelProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <BookOpen className="h-3 w-3" />
        卷管理
      </div>

      {volumes.length === 0 ? (
        <div className="px-2 py-3 text-[11px] text-muted-foreground text-center">
          尚无卷信息
        </div>
      ) : (
        volumes.map((vol) => (
          <button
            key={vol.volumeNumber}
            onClick={() => onVolumeClick?.(vol.volumeNumber)}
            className={cn(
              'w-full flex items-start gap-2 px-2 py-2 text-left rounded-md transition-colors',
              vol.volumeNumber === currentVolume
                ? 'bg-primary/5 border border-primary/20'
                : 'hover:bg-muted/50'
            )}
          >
            {/* 卷号指示器 */}
            <div
              className={cn(
                'flex-shrink-0 w-6 h-6 rounded flex items-center justify-center text-[10px] font-semibold',
                vol.volumeNumber === currentVolume
                  ? 'bg-primary text-primary-foreground'
                  : vol.status === 'completed'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-muted text-muted-foreground'
              )}
            >
              {vol.volumeNumber}
            </div>

            {/* 卷信息 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-medium truncate">
                  {vol.title || `第${vol.volumeNumber}卷`}
                </span>
                {vol.volumeNumber === currentVolume && (
                  <span className="text-[9px] bg-primary/10 text-primary px-1 rounded">
                    当前
                  </span>
                )}
              </div>

              <div className="text-[10px] text-muted-foreground mt-0.5">
                第{vol.chapterOffset + 1}–{vol.chapterOffset + vol.chapterCount}章
                {' · '}
                {vol.chapterCount}章
              </div>

              {/* 跨卷追踪摘要 */}
              {(vol.unreclaimedForeshadowings > 0 || vol.activeSubplots > 0) && (
                <div className="flex items-center gap-2 mt-1">
                  {vol.unreclaimedForeshadowings > 0 && (
                    <span className="flex items-center gap-0.5 text-[9px] text-amber-600">
                      <AlertTriangle className="h-2.5 w-2.5" />
                      {vol.unreclaimedForeshadowings}个跨卷伏笔
                    </span>
                  )}
                  {vol.activeSubplots > 0 && (
                    <span className="text-[9px] text-blue-600">
                      {vol.activeSubplots}条跨卷支线
                    </span>
                  )}
                </div>
              )}

              {/* 最后一卷摘要预览 */}
              {vol.lastBlockSummary && vol.status === 'completed' && (
                <div className="text-[9px] text-muted-foreground mt-1 line-clamp-2">
                  {vol.lastBlockSummary.slice(0, 80)}
                </div>
              )}
            </div>

            <ChevronRight className="h-3 w-3 text-muted-foreground flex-shrink-0 mt-1" />
          </button>
        ))
      )}
    </div>
  )
}
