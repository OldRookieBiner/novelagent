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
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <div className="flex gap-4">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
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

/**
 * 项目详情页面骨架屏
 */
export function ProjectDetailSkeleton()
{
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-24" />
      </div>
      <div className="flex gap-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-20" />
      </div>

      {/* Step Navigation */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-24" />
        ))}
      </div>

      {/* Content */}
      <div className="flex gap-6">
        <ChapterListSkeleton />
        <ChapterDetailSkeleton />
      </div>
    </div>
  )
}

export default Skeleton
