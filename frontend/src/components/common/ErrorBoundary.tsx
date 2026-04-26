// frontend/src/components/common/ErrorBoundary.tsx
import { Component, ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props
{
  children: ReactNode
  fallback?: ReactNode
}

interface State
{
  hasError: boolean
  error: Error | null
}

/**
 * 全局错误边界组件
 * 捕获 React 组件树中的 JavaScript 错误，显示友好的错误界面
 */
export default class ErrorBoundary extends Component<Props, State>
{
  constructor(props: Props)
  {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State
  {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo)
  {
    // 可以将错误日志上报给服务器
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReset = () =>
  {
    this.setState({ hasError: false, error: null })
    // 刷新页面
    window.location.reload()
  }

  render()
  {
    if (this.state.hasError)
    {
      // 如果提供了自定义 fallback，使用它
      if (this.props.fallback)
      {
        return this.props.fallback
      }

      // 默认错误界面
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="text-destructive">出错了</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-muted-foreground">
                应用遇到了一个错误，请尝试刷新页面。如果问题持续存在，请联系支持。
              </p>

              {import.meta.env.DEV && this.state.error && (
                <div className="p-3 bg-muted rounded-md overflow-auto">
                  <p className="text-sm font-mono text-destructive">
                    {this.state.error.message}
                  </p>
                  {this.state.error.stack && (
                    <pre className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap">
                      {this.state.error.stack}
                    </pre>
                  )}
                </div>
              )}

              <div className="flex gap-2">
                <Button onClick={this.handleReset}>
                  刷新页面
                </Button>
                <Button variant="outline" onClick={() => window.history.back()}>
                  返回上一页
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}
