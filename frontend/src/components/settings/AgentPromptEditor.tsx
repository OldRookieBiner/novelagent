import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { AgentPrompt } from '@/types'

interface AgentPromptEditorProps {
  prompt: AgentPrompt
  onSave: (content: string) => Promise<void>
  onReset?: () => Promise<void>
  isProjectLevel?: boolean
  onCancel?: () => void
}

export function AgentPromptEditor({
  prompt,
  onSave,
  onReset,
  isProjectLevel = false,
  onCancel,
}: AgentPromptEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [content, setContent] = useState(prompt.prompt_content)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(content)
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to save prompt:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!onReset) return
    if (!confirm('确定要重置为默认值吗？您的修改将丢失。')) return

    setResetting(true)
    try {
      await onReset()
      setIsEditing(false)
    } catch (error) {
      console.error('Failed to reset prompt:', error)
    } finally {
      setResetting(false)
    }
  }

  const handleCancel = () => {
    setContent(prompt.prompt_content)
    setIsEditing(false)
    onCancel?.()
  }

  if (!isEditing) {
    return (
      <div className="border rounded-lg p-4 mb-3 bg-white hover:border-blue-300 transition-colors">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h4 className="font-medium text-gray-900">{prompt.agent_name}</h4>
            <p className="text-sm text-gray-500">{prompt.description}</p>
          </div>
          <div className="flex items-center gap-2">
            {!prompt.is_default && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                已修改
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsEditing(true)}
            >
              编辑
            </Button>
          </div>
        </div>
        <div className="text-sm text-gray-600 line-clamp-2 font-mono bg-gray-50 p-2 rounded">
          {prompt.prompt_content.slice(0, 100)}...
        </div>
      </div>
    )
  }

  return (
    <div className="border-2 border-blue-300 rounded-lg p-4 mb-3 bg-blue-50/30">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-blue-700">
          {prompt.agent_name} {isProjectLevel && '(本项目自定义)'}
        </h4>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={handleCancel}>
            取消
          </Button>
          {onReset && !isProjectLevel && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              disabled={resetting}
            >
              {resetting ? '重置中...' : '重置默认'}
            </Button>
          )}
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? '保存中...' : '保存'}
          </Button>
        </div>
      </div>

      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-[200px] font-mono text-sm"
        placeholder="输入 Prompt 内容..."
      />

      <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
        <span>可用变量:</span>
        <div className="flex flex-wrap gap-1">
          {prompt.variables.map((v) => (
            <code
              key={v}
              className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono"
            >
              {`{${v}}`}
            </code>
          ))}
        </div>
      </div>
    </div>
  )
}