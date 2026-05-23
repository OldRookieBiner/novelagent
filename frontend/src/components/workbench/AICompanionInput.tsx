import { useState } from 'react'
import { Send } from 'lucide-react'

interface AICompanionInputProps
{
  onSend: (message: string) => void
  disabled?: boolean
  disabledReason?: string
}

export function AICompanionInput({ onSend, disabled, disabledReason }: AICompanionInputProps)
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

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-700 p-2">
      {disabled && disabledReason && (
        <div className="text-[10px] text-amber-400/80 mb-1.5 text-center">{disabledReason}</div>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="说说你的想法..."
          disabled={disabled}
          className="flex-1 bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
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
