// frontend/src/components/writing/ChapterEditor.tsx
import DOMPurify from 'dompurify'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import TipTapEditor from '@/components/common/TipTapEditor'
import ErrorMessage from '@/components/common/ErrorMessage'

interface ChapterEditorProps
{
  projectId: string
  chapterNumber: number
  chapterTitle: string
  chapterOutline: {
    scene?: string
    characters?: string
    plot?: string
    conflict?: string
    ending?: string
  }
  content: string
  wordCount: number
  mode: 'preview' | 'edit'
  isGenerating: boolean
  isSaving: boolean
  error: string | null
  onGenerate: () => void
  onStop: () => void
  onSave: () => void
  onContentChange: (content: string) => void
  onModeChange: (mode: 'preview' | 'edit') => void
  onClearError: () => void
}

/**
 * 写作页面编辑器组件
 * 包含章节大纲展示、内容预览/编辑、操作按钮
 */
export default function ChapterEditor({
  projectId,
  chapterNumber,
  chapterTitle,
  chapterOutline,
  content,
  wordCount,
  mode,
  isGenerating,
  isSaving,
  error,
  onGenerate,
  onStop,
  onSave,
  onContentChange,
  onModeChange,
  onClearError,
}: ChapterEditorProps)
{
  const navigate = useNavigate()

  return (
    <div className="flex-1 flex flex-col">
      {/* 章节大纲 */}
      <div className="border-b p-4 bg-background">
        <h3 className="font-semibold mb-3">
          第{chapterNumber}章：{chapterTitle || '未命名'}
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div><span className="text-muted-foreground">场景：</span>{chapterOutline.scene || '-'}</div>
          <div><span className="text-muted-foreground">人物：</span>{chapterOutline.characters || '-'}</div>
          <div className="col-span-2"><span className="text-muted-foreground">情节：</span>{chapterOutline.plot || '-'}</div>
          <div><span className="text-muted-foreground">冲突：</span>{chapterOutline.conflict || '-'}</div>
          <div><span className="text-muted-foreground">结局：</span>{chapterOutline.ending || '-'}</div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="px-4 py-2 bg-destructive/10 border-b">
          <ErrorMessage message={error} onDismiss={onClearError} />
        </div>
      )}

      {/* 内容区域 */}
      <div className="flex-1 flex flex-col">
        {/* 状态栏 */}
        <div className="px-4 py-2 border-b bg-muted/30 flex justify-between items-center">
          <div className="flex items-center gap-2">
            {isGenerating ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm text-green-600">正在生成...</span>
              </>
            ) : wordCount > 0 ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full" />
                <span className="text-sm text-green-600">生成完成</span>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">未生成</span>
            )}
          </div>
          <span className="text-sm text-muted-foreground">
            {wordCount > 0 ? `共 ${wordCount} 字` : ''}
          </span>
        </div>

        {/* 内容区：预览或编辑 */}
        <div className="flex-1 overflow-y-auto p-6 bg-background">
          {mode === 'edit' ? (
            <TipTapEditor
              content={content}
              onChange={onContentChange}
              placeholder="开始写作..."
            />
          ) : (
            <div className="prose max-w-none">
              {(() => {
                // 检测是否包含 HTML 标签
                const hasHtmlTags = /<[a-zA-Z][^>]*>/.test(content)
                const sanitizedContent = hasHtmlTags ? DOMPurify.sanitize(content) : content

                return sanitizedContent ? (
                  hasHtmlTags ? (
                    <div
                      className="prose-content"
                      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
                    />
                  ) : (
                    sanitizedContent.split('\n').filter(p => p.trim()).map((paragraph, i) => (
                      <p key={i} className="mb-4 leading-relaxed" style={{ textIndent: '2em' }}>
                        {paragraph}
                      </p>
                    ))
                  )
                ) : (
                  <p className="text-muted-foreground">点击下方按钮生成内容</p>
                )
              })()}
            </div>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="px-4 py-3 border-t bg-muted/30 flex gap-2">
          {mode === 'edit' ? (
            <>
              <Button onClick={onSave} disabled={isSaving}>
                {isSaving ? '保存中...' : '保存'}
              </Button>
              <Button variant="outline" onClick={() => onModeChange('preview')}>
                返回预览
              </Button>
            </>
          ) : isGenerating ? (
            <Button variant="destructive" onClick={onStop}>
              停止生成
            </Button>
          ) : (
            <>
              <Button onClick={onGenerate}>
                {wordCount > 0 ? '重新生成' : 'AI 生成'}
              </Button>
              {wordCount > 0 && (
                <>
                  <Button variant="outline" onClick={() => onModeChange('edit')}>
                    编辑
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate(`/project/${projectId}/read/${chapterNumber}`)}
                  >
                    审核
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
