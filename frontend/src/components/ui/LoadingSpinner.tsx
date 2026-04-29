import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps
{
  size?: 'sm' | 'md' | 'lg'
  text?: string
  fullPage?: boolean
}

/**
 * 通用加载状态组件
 * 统一项目中所有加载状态的展示方式
 */
export default function LoadingSpinner({
  size = 'md',
  text,
  fullPage = false,
}: LoadingSpinnerProps)
{
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  const spinner = (
    <Loader2 className={`animate-spin ${sizeClasses[size]} text-primary`} />
  )

  if (fullPage)
  {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-2">
        {spinner}
        {text && <p className="text-muted-foreground text-sm">{text}</p>}
      </div>
    )
  }

  if (text)
  {
    return (
      <div className="flex items-center gap-2">
        {spinner}
        <span className="text-muted-foreground text-sm">{text}</span>
      </div>
    )
  }

  return spinner
}