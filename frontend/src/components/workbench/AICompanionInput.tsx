import { useState } from 'react'
import { Send, PenTool, Search, Sparkles, FileText, Users } from 'lucide-react'

interface QuickCommand
{
  label: string
  icon: React.ComponentType<{ className?: string }>
  prompt: string
  showWhen: string[]
}

const QUICK_COMMANDS: QuickCommand[] = [
  { label: '写下一章', icon: PenTool, prompt: '请继续写下一章', showWhen: ['writing'] },
  { label: '审核本章', icon: Search, prompt: '请审核当前章节', showWhen: ['writing'] },
  { label: '润色本章', icon: Sparkles, prompt: '请润色当前章节的文笔，保持情节不变', showWhen: ['writing'] },
  { label: '查看大纲', icon: FileText, prompt: '请展示当前大纲概要', showWhen: ['outline', 'chapter_outlines', 'characters', 'relations', 'settings'] },
  { label: '查看角色', icon: Users, prompt: '请展示所有角色', showWhen: ['characters', 'relations'] },
]

interface AICompanionInputProps
{
  onSend: (message: string) => void
  disabled?: boolean
  disabledReason?: string
  activeTab?: string
}

export function AICompanionInput({ onSend, disabled, disabledReason, activeTab }: AICompanionInputProps)
{
  const [input, setInput] = useState('')

  const handleSubmit = (e: React.FormEvent) =>
  {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleQuickCommand = (prompt: string) =>
  {
    setInput(prompt)
  }

  const visibleCommands = QUICK_COMMANDS.filter(
    (cmd) => !activeTab || cmd.showWhen.includes(activeTab)
  )

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 p-2">
      {disabled && disabledReason && (
        <div className="text-[10px] text-amber-600 mb-1.5 text-center">{disabledReason}</div>
      )}

      {/* 快捷指令按钮 */}
      {visibleCommands.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {visibleCommands.map((cmd) => (
            <button
              key={cmd.label}
              type="button"
              onClick={() => handleQuickCommand(cmd.prompt)}
              disabled={disabled}
              className="flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700 disabled:opacity-50 transition-colors"
            >
              <cmd.icon className="h-3 w-3" />
              {cmd.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="说说你的想法..."
          disabled={disabled}
          className="flex-1 bg-gray-50 border border-gray-200 rounded-md px-3 py-2 text-xs text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white px-3 py-2 rounded-md text-xs transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </form>
  )
}
