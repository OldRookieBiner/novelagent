// frontend/src/components/ui/skeleton.tsx
import { cn } from '@/lib/utils'

interface SkeletonProps
{
  className?: string
}

/**
 * Skeleton 组件
 * 用于在加载时显示占位符
 */
function Skeleton({ className }: SkeletonProps)
{
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-muted',
        className
      )}
    />
  )
}

/**
 * 项目卡片骨架屏
 */
export function ProjectCardSkeleton()
{
  return (
    <div className="border-2 border-border rounded-lg bg-card p-4">
      {/* 标题 + 状态标签 */}
      <div className="flex justify-between items-start gap-2 mb-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      {/* 信息行 */}
      <div className="flex flex-col gap-2 mb-4">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-5 w-20" />
        </div>
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-4 w-14" />
        </div>
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      {/* 按钮 */}
      <div className="flex gap-2">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-14 rounded-md" />
      </div>
    </div>
  )
}

export default Skeleton
