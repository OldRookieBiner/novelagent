// frontend/src/hooks/useAsyncOperation.ts
import { useState, useCallback } from 'react'
import { toast } from 'sonner'

interface AsyncOperationOptions
{
  successMessage?: string
  errorMessage?: string
  onSuccess?: () => void
  onError?: (error: Error) => void
}

interface AsyncOperationResult<T>
{
  execute: (...args: unknown[]) => Promise<T | undefined>
  loading: boolean
  error: Error | null
}

/**
 * 异步操作 Hook
 * 统一处理加载状态和错误反馈
 */
export function useAsyncOperation<T>(
  operation: (...args: unknown[]) => Promise<T>,
  options: AsyncOperationOptions = {}
): AsyncOperationResult<T>
{
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const execute = useCallback(
    async (...args: unknown[]) =>
    {
      setLoading(true)
      setError(null)

      try
      {
        const result = await operation(...args)

        if (options.successMessage)
        {
          toast.success(options.successMessage)
        }

        options.onSuccess?.()
        return result
      } catch (err)
      {
        const error = err instanceof Error ? err : new Error(String(err))
        setError(error)

        const message = options.errorMessage || error.message || '操作失败'
        toast.error(message)

        options.onError?.(error)
        return undefined
      } finally
      {
        setLoading(false)
      }
    },
    [operation, options]
  )

  return { execute, loading, error }
}

/**
 * 带确认的异步操作 Hook
 * 在执行操作前显示确认对话框
 */
export function useConfirmOperation<T>(
  operation: (...args: unknown[]) => Promise<T>,
  options: AsyncOperationOptions & { confirmMessage: string }
): AsyncOperationResult<T> & { pendingConfirm: boolean; confirm: () => void; cancel: () => void }
{
  const [pendingConfirm, setPendingConfirm] = useState(false)
  const [pendingArgs, setPendingArgs] = useState<unknown[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const execute = useCallback(
    async (...args: unknown[]) =>
    {
      setPendingArgs(args)
      setPendingConfirm(true)
      return undefined
    },
    []
  )

  const confirm = useCallback(
    async () =>
    {
      setPendingConfirm(false)
      setLoading(true)
      setError(null)

      try
      {
        const result = await operation(...pendingArgs)

        if (options.successMessage)
        {
          toast.success(options.successMessage)
        }

        options.onSuccess?.()
        return result
      } catch (err)
      {
        const error = err instanceof Error ? err : new Error(String(err))
        setError(error)

        const message = options.errorMessage || error.message || '操作失败'
        toast.error(message)

        options.onError?.(error)
        return undefined
      } finally
      {
        setLoading(false)
      }
    },
    [operation, pendingArgs, options]
  )

  const cancel = useCallback(() =>
  {
    setPendingConfirm(false)
    setPendingArgs([])
  }, [])

  return { execute, loading, error, pendingConfirm, confirm, cancel }
}
