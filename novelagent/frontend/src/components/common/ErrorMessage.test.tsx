import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import ErrorMessage from '@/components/common/ErrorMessage'

describe('ErrorMessage', () => {
  it('renders error message', () => {
    render(<ErrorMessage message="Something went wrong" />)

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('shows retry button when onRetry provided', () => {
    const onRetry = vi.fn()
    render(<ErrorMessage message="Error" onRetry={onRetry} />)

    const retryButton = screen.getByText('重试')
    expect(retryButton).toBeInTheDocument()

    fireEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows dismiss button when onDismiss provided', () => {
    const onDismiss = vi.fn()
    render(<ErrorMessage message="Error" onDismiss={onDismiss} />)

    // Find button with X icon (no text, just icon)
    const dismissButton = screen.getByRole('button', { name: '' })
    expect(dismissButton).toBeInTheDocument()

    fireEvent.click(dismissButton)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('shows both buttons when both callbacks provided', () => {
    render(
      <ErrorMessage
        message="Error"
        onRetry={() => {}}
        onDismiss={() => {}}
      />
    )

    expect(screen.getByText('重试')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '' })).toBeInTheDocument()
  })

  it('has correct styling for error state', () => {
    render(<ErrorMessage message="Error" />)

    const container = screen.getByText('Error').closest('div')
    expect(container?.parentElement).toHaveClass('bg-destructive/10')
  })
})