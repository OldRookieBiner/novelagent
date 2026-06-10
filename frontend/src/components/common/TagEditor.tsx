// TagEditor.tsx — 标签列表编辑器（可增删）

import { useState } from 'react'

export interface TagEditorProps
{
    items: string[]
    setItems: (v: string[]) => void
    placeholder: string
}

export function TagEditor({ items, setItems, placeholder }: TagEditorProps)
{
    const [newVal, setNewVal] = useState('')

    return (
        <div className="space-y-1">
            <div className="flex flex-wrap gap-1">
                {items.map((item, i) => (
                    <span key={i} className="flex items-center gap-0.5 bg-muted text-[10px] px-1.5 py-0.5 rounded">
                        {item}
                        <button onClick={() => setItems(items.filter((_, idx) => idx !== i))} className="text-muted-foreground hover:text-red-500 ml-0.5">×</button>
                    </span>
                ))}
            </div>
            <div className="flex gap-1">
                <input
                    value={newVal}
                    onChange={(e) => setNewVal(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && newVal.trim())
                        {
                            setItems([...items, newVal.trim()])
                            setNewVal('')
                            e.preventDefault()
                        }
                    }}
                    placeholder={placeholder}
                    className="flex-1 text-xs border rounded px-2 py-1 outline-none focus:border-primary"
                />
                <button
                    onClick={() => {
                        if (newVal.trim())
                        {
                            setItems([...items, newVal.trim()])
                            setNewVal('')
                        }
                    }}
                    className="text-[10px] px-2 py-1 border rounded hover:bg-muted/50"
                >添加</button>
            </div>
        </div>
    )
}
