import { Button } from '@/components/ui/button'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
  loading?: boolean
  variant?: 'default' | 'danger'
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  onConfirm,
  onCancel,
  loading = false,
  variant = 'default',
}: ConfirmDialogProps) {
  if (!open) return null

  const confirmButtonClass = variant === 'danger'
    ? 'bg-red-500 hover:bg-red-600 text-white'
    : 'bg-gray-600 hover:bg-gray-700 text-white'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-[420px] max-w-[90vw]">
        <div className="text-lg font-medium mb-3">{title}</div>
        <div className="text-sm text-gray-600 mb-6 leading-relaxed">{message}</div>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading}
            className={confirmButtonClass}
          >
            {loading ? '处理中...' : confirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}
