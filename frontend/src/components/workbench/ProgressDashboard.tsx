// ProgressDashboard.tsx — 底栏进度仪表盘

interface ProgressDashboardProps {
  rhythmData?: number[]      // 最近章节节奏评分
  pendingForeshadowings?: number  // 待回收伏笔数
  overdueForeshadowings?: number  // 超期伏笔数
  styleStatus?: 'stable' | 'drift' | 'unknown'  // 风格状态
  currentBlock?: string     // 当前情节块
  progress?: number         // 整体进度 0-100
}

export function ProgressDashboard({
  rhythmData = [],
  pendingForeshadowings = 0,
  overdueForeshadowings = 0,
  styleStatus = 'unknown',
  currentBlock = '',
  progress = 0,
}: ProgressDashboardProps)
{
  // 迷你节奏折线图
  const rhythmSvg = rhythmData.length > 1 ? (
    <svg width="60" height="14" className="vertical-align-middle">
      <polyline
        points={rhythmData
          .map((v, i) => `${(i / (rhythmData.length - 1)) * 60},${14 - (v / 5) * 14}`)
          .join(' ')}
        fill="none"
        stroke="currentColor"
        className="text-primary"
        strokeWidth="1.5"
      />
    </svg>
  ) : null

  return (
    <div className="h-8 bg-white border-t border-gray-200 flex items-center px-4 gap-6 text-[10px] text-muted-foreground flex-shrink-0">
      {/* 节奏 */}
      <div className="flex items-center gap-1">
        <span>📊 节奏</span>
        {rhythmSvg}
      </div>

      {/* 伏笔 */}
      <div>
        🎯 伏笔{' '}
        <span className={overdueForeshadowings > 0 ? 'text-amber-500 font-medium' : ''}>
          {pendingForeshadowings}
        </span>
        {overdueForeshadowings > 0 && (
          <span className="text-red-500 ml-1">⚠{overdueForeshadowings}</span>
        )}
        待回收
      </div>

      {/* 风格 */}
      <div>
        🎨 风格{' '}
        <span
          className={
            styleStatus === 'stable'
              ? 'bg-green-100 text-green-700 px-1 rounded'
              : styleStatus === 'drift'
                ? 'bg-amber-100 text-amber-700 px-1 rounded'
                : 'text-muted-foreground'
          }
        >
          {styleStatus === 'stable' ? '稳定' : styleStatus === 'drift' ? '漂移' : '--'}
        </span>
      </div>

      {/* 当前情节块 */}
      {currentBlock && <div>📖 {currentBlock}</div>}

      {/* 整体进度 */}
      <div className="ml-auto">
        距结局 {progress}%
      </div>
    </div>
  )
}
