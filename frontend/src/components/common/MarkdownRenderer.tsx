// MarkdownRenderer.tsx — Markdown 内容渲染组件

import ReactMarkdown from 'react-markdown'
import { cn } from '@/lib/utils'

interface MarkdownRendererProps {
  /** Markdown 文本内容 */
  content: string
  /** 额外的 className */
  className?: string
  /** 是否禁用链接在新标签页打开 */
  disableExternalLinks?: boolean
}

/**
 * 统一的 Markdown 渲染组件
 * 支持标题、列表、引用、粗体、链接等基础语法
 */
export function MarkdownRenderer({ content, className, disableExternalLinks }: MarkdownRendererProps) {
  if (!content?.trim()) {
    return null
  }

  return (
    <div className={cn('markdown-content', className)}>
      <ReactMarkdown
        components={{
          // 标题样式
          h1: ({ children }) => (
            <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-semibold mt-3 mb-1.5">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium mt-2 mb-1">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-xs font-medium mt-2 mb-1">{children}</h4>
          ),
          // 段落和列表样式
          p: ({ children }) => (
            <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="text-sm">{children}</li>
          ),
          // 引用样式
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-primary/30 pl-3 py-1 my-2 text-sm text-muted-foreground bg-muted/30 rounded-r">
              {children}
            </blockquote>
          ),
          // 代码样式
          code: ({ className, children, ...props }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono" {...props}>
                  {children}
                </code>
              )
            }
            return (
              <code className={cn(className, 'block bg-muted p-2 rounded text-xs font-mono my-2 overflow-x-auto')} {...props}>
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre className="bg-muted p-3 rounded text-xs font-mono my-2 overflow-x-auto">
              {children}
            </pre>
          ),
          // 链接样式
          a: ({ href, children, ...props }) => {
            const isExternal = href?.startsWith('http')
            if (isExternal && !disableExternalLinks) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                  {...props}
                >
                  {children}
                </a>
              )
            }
            return (
              <a href={href} className="text-primary hover:underline" {...props}>
                {children}
              </a>
            )
          },
          // 表格样式
          table: ({ children }) => (
            <div className="overflow-x-auto my-2">
              <table className="w-full text-xs border-collapse">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border bg-muted px-2 py-1 text-left font-medium">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border px-2 py-1">{children}</td>
          ),
          // 分隔线
          hr: () => <hr className="my-4 border-muted" />,
          // 强调
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
