// frontend/src/components/common/TipTapEditor.tsx
import { useEffect, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Button } from '@/components/ui/button'
import { Bold, Italic, Undo, Redo } from 'lucide-react'

interface TipTapEditorProps {
  content: string
  onChange: (content: string) => void
  placeholder?: string
  readOnly?: boolean
}

export default function TipTapEditor({
  content,
  onChange,
  placeholder = '开始写作...',
  readOnly = false,
}: TipTapEditorProps) {
  // Track if update is from external source (not user input)
  const isExternalUpdate = useRef(false)

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder,
      }),
    ],
    content,
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      // Skip if this update was triggered by external content change
      if (isExternalUpdate.current) {
        isExternalUpdate.current = false
        return
      }
      // Use getHTML() to preserve formatting (bold, italic, etc.)
      onChange(editor.getHTML())
    },
  })

  // Sync external content changes to editor
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      isExternalUpdate.current = true
      // Store current cursor position
      const { from, to } = editor.state.selection

      // Check if content is plain text (no HTML tags)
      // Use regex to detect actual HTML tags (avoids false positives like "a < b")
      const hasHtmlTags = /<[a-zA-Z][^>]*>/.test(content)
      // Convert plain text to HTML paragraphs if needed
      const htmlContent = hasHtmlTags
        ? content
        : content
            .split('\n')
            .filter(p => p.trim())
            .map(p => `<p>${p}</p>`)
            .join('')

      // Update content
      editor.commands.setContent(htmlContent, false)
      // Restore cursor position if possible
      try {
        editor.commands.setTextSelection({ from, to })
      } catch {
        // If cursor position is invalid, move to end
        editor.commands.focus('end')
      }
    }
  }, [content, editor])

  if (!editor) {
    return null
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {!readOnly && (
        <div className="border-b bg-muted/50 p-2 flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={editor.isActive('bold') ? 'bg-muted' : ''}
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={editor.isActive('italic') ? 'bg-muted' : ''}
          >
            <Italic className="h-4 w-4" />
          </Button>
          <div className="w-px bg-border mx-1" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
          >
            <Undo className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
          >
            <Redo className="h-4 w-4" />
          </Button>
        </div>
      )}
      <EditorContent
        editor={editor}
        className="prose max-w-none p-4 min-h-[400px] focus:outline-none"
      />
    </div>
  )
}