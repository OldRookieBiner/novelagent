import { useState, useEffect, useCallback } from 'react'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  fetchConversations, activateConversation, renameConversation, deleteConversation,
} from '@/lib/agentApi'
import type { ConversationItem } from '@/lib/agentApi'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import { useWorkbenchStore } from '@/stores/workbenchStore'

interface ConversationHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSwitchConversation: (conversation: ConversationItem) => void
  isAgentSending: boolean
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return `${Math.floor(diffDay / 7)}周前`
}

export function ConversationHistoryDialog({
  open, onOpenChange, onSwitchConversation, isAgentSending,
}: ConversationHistoryDialogProps) {
  const currentProjectId = useWorkbenchStore((s) => s.currentProjectId)
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [renamingId, setRenamingId] = useState<number | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConversations = useCallback(async () => {
    if (!currentProjectId) return
    setLoading(true)
    setError(null)
    try {
      const list = await fetchConversations(currentProjectId)
      setConversations(list)
    } catch {
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }, [currentProjectId])

  useEffect(() => {
    if (open) loadConversations()
  }, [open, loadConversations])

  const handleActivate = async (conv: ConversationItem) => {
    if (conv.is_active || !currentProjectId || isAgentSending) return
    try {
      const updated = await activateConversation(currentProjectId, conv.id)
      onSwitchConversation(updated)
      await loadConversations()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '切换失败')
    }
  }

  const handleRenameConfirm = async () => {
    if (!renamingId || !renameValue.trim() || !currentProjectId) return
    try {
      await renameConversation(currentProjectId, renamingId, renameValue.trim())
      setRenamingId(null)
      await loadConversations()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '重命名失败')
    }
  }

  const handleRenameStart = (conv: ConversationItem) => {
    setRenamingId(conv.id)
    setRenameValue(conv.title)
  }

  const handleRenameCancel = () => {
    setRenamingId(null)
    setRenameValue('')
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget || !currentProjectId) return
    setDeleting(true)
    try {
      await deleteConversation(currentProjectId, deleteTarget.id)
      setDeleteTarget(null)
      await loadConversations()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[380px]">
          <DialogHeader>
            <DialogTitle>会话历史</DialogTitle>
          </DialogHeader>
          {error && (
            <div className="text-xs text-red-500 px-3">{error}</div>
          )}
          <div className="max-h-[400px] overflow-y-auto py-2">
            {loading && conversations.length === 0 && (
              <div className="text-center text-muted-foreground text-xs py-6">加载中...</div>
            )}
            {!loading && conversations.length === 0 && (
              <div className="text-center text-muted-foreground text-xs py-6">暂无会话</div>
            )}
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`flex items-center gap-2 px-3 py-2 mx-1 rounded-md mb-0.5 ${
                  conv.is_active ? 'bg-primary/5' : 'hover:bg-muted/50'
                }`}
              >
                <div className="flex-1 min-w-0">
                  {renamingId === conv.id ? (
                    <div className="flex items-center gap-1">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && renameValue.trim()) handleRenameConfirm()
                          if (e.key === 'Escape') handleRenameCancel()
                        }}
                        className="flex-1 text-[11px] border border-primary rounded px-1.5 py-0.5 outline-none"
                        autoFocus
                        maxLength={50}
                      />
                      <button
                        onClick={handleRenameConfirm}
                        disabled={!renameValue.trim()}
                        className="p-0.5 text-primary hover:text-primary/80 disabled:opacity-40"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={handleRenameCancel} className="p-0.5 text-muted-foreground hover:text-foreground">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div
                      className={`text-[11px] cursor-pointer truncate ${
                        conv.is_active ? 'font-medium text-primary' : 'text-foreground'
                      } ${isAgentSending && !conv.is_active ? 'opacity-50 pointer-events-none' : ''}`}
                      onClick={() => handleActivate(conv)}
                    >
                      {conv.title || '未命名会话'}
                    </div>
                  )}
                  <div className="text-[9px] text-muted-foreground mt-0.5">
                    {conv.message_count}条消息 · {formatRelativeTime(conv.updated_at || conv.created_at)}
                  </div>
                </div>
                {conv.is_active && renamingId !== conv.id && (
                  <span className="text-[9px] text-primary bg-primary/10 px-1.5 py-0.5 rounded shrink-0">当前</span>
                )}
                {renamingId !== conv.id && (
                  <button
                    onClick={() => handleRenameStart(conv)}
                    className="p-1 text-muted-foreground hover:text-foreground shrink-0"
                    title="重命名"
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                )}
                {!conv.is_active && renamingId !== conv.id && (
                  <button
                    onClick={() => setDeleteTarget(conv)}
                    className="p-1 text-muted-foreground/50 hover:text-red-500 shrink-0"
                    title="删除"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        title="删除会话"
        message={`确定要删除「${deleteTarget?.title || '未命名会话'}」吗？删除后无法恢复。`}
        confirmText="删除"
        variant="danger"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        loading={deleting}
      />
    </>
  )
}
