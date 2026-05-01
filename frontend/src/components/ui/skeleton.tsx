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
      <div className="flex justify-between items-start gap-2 mb-3">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="flex items-center gap-3 mb-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="mb-3 space-y-1">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-8" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-14 rounded-md" />
      </div>
    </div>
  )
}

/**
 * 大纲信息骨架屏
 */
export function OutlineSkeleton()
{
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </div>
  )
}

/**
 * 章节列表骨架屏
 */
export function ChapterListSkeleton()
{
  return (
    <div className="w-64 shrink-0 space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded" />
      ))}
    </div>
  )
}

/**
 * 章节详情骨架屏
 */
export function ChapterDetailSkeleton()
{
  return (
    <div className="flex-1 space-y-4">
      <Skeleton className="h-8 w-1/3" />
      <div className="space-y-3">
        <div>
          <Skeleton className="h-4 w-16 mb-1" />
          <Skeleton className="h-5 w-full" />
        </div>
        <div>
          <Skeleton className="h-4 w-16 mb-1" />
          <Skeleton className="h-5 w-full" />
        </div>
        <div>
          <Skeleton className="h-4 w-16 mb-1" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    </div>
  )
}

export default Skeleton
