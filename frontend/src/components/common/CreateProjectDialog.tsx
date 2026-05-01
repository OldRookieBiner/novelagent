import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { projectsApi } from '@/lib/api'

interface CreateProjectDialogProps
{
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export default function CreateProjectDialog({ open, onOpenChange, onCreated }: CreateProjectDialogProps)
{
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async () =>
  {
    if (!name.trim()) return
    if (name.length > 100)
    {
      setError('项目名称不能超过 100 个字符')
      return
    }

    setCreating(true)
    setError('')
    try
    {
      await projectsApi.create({ name })
      setName('')
      onOpenChange(false)
      onCreated()
    } catch (err)
    {
      setError(err instanceof Error ? err.message : '创建项目失败')
    } finally
    {
      setCreating(false)
    }
  }

  const handleOpenChange = (open: boolean) =>
  {
    if (!open)
    {
      setName('')
      setError('')
    }
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建项目</DialogTitle>
          <DialogDescription>输入项目名称开始创作你的小说</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <Input
            placeholder="项目名称"
            value={name}
            onChange={(e) => { setName(e.target.value); setError('') }}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            maxLength={100}
            autoFocus
          />
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleCreate} disabled={creating || !name.trim()}>
            {creating ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}