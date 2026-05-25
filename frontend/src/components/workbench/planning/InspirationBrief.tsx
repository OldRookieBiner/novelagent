// 灵感简报组件 — 展示 AI 搭档生成的灵感简报，支持编辑和预览

import { useState } from 'react'

interface InspirationBriefProps
{
  brief: string
  onBriefChange?: (brief: string) => void
  readOnly?: boolean
}

/** 移除危险的 HTML 标签和事件处理器 */
function sanitizeHtml(text: string): string
{
  return text
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/\bon\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\bon\w+\s*=\s*'[^']*'/gi, '')
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
}

function InspirationBrief({ brief, onBriefChange, readOnly = false }: InspirationBriefProps)
{
  const [isEditing, setIsEditing] = useState(false)

  // 简洁的 Markdown 风格渲染
  const renderBrief = (text: string) =>
  {
    if (!text)
    {
      return '<div class="text-muted-foreground text-sm italic">AI 搭档尚未创建灵感简报，请在右侧对话中描述你的创作灵感。</div>'
    }
    const sanitized = sanitizeHtml(text)
    return sanitized
      .split('\n')
      .map(line =>
      {
        if (line.startsWith('## ')) return `<h3 class="text-base font-semibold mt-4 mb-1">${line.slice(3)}</h3>`
        if (line.startsWith('# ')) return `<h2 class="text-lg font-bold mt-4 mb-2">${line.slice(2)}</h2>`
        if (line.startsWith('- ')) return `<li class="ml-4">${line.slice(2)}</li>`
        if (line.match(/^\d+\. /)) return `<li class="ml-4">${line.replace(/^\d+\. /, '')}</li>`
        if (line.trim() === '') return '<br/>'
        return `<p class="mb-1">${line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')}</p>`
      })
      .join('')
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-auto p-4 prose prose-sm max-w-none">
        {isEditing ? (
          <textarea
            className="w-full h-full min-h-[400px] p-3 border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-ring text-sm"
            value={brief}
            onChange={(e) => onBriefChange?.(e.target.value)}
            placeholder="开始撰写你的灵感简报..."
          />
        ) : (
          <div
            className="brief-content"
            dangerouslySetInnerHTML={{ __html: renderBrief(brief) }}
          />
        )}
      </div>
      {!readOnly && (
        <div className="flex justify-end pt-2 px-4 pb-2 border-t">
          <button
            className="text-xs px-3 py-1 border rounded hover:bg-accent"
            onClick={() => setIsEditing(!isEditing)}
          >
            {isEditing ? '预览' : '编辑'}
          </button>
        </div>
      )}
    </div>
  )
}

export default InspirationBrief
