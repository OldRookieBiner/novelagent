// frontend/src/components/common/ErrorMessage.tsx
import { AlertCircle, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ErrorMessageProps {
  message: string
  onRetry?: () => void
  onDismiss?: () => void
}

export default function ErrorMessage({ message, onRetry, onDismiss }: ErrorMessageProps) {
  return (
    <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
      <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-destructive">{message}</p>
        {(onRetry || onDismiss) && (
          <div className="flex gap-2 mt-2">
            {onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                重试
              </Button>
            )}
            {onDismiss && (
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}