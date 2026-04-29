// frontend/src/components/workbench/planning/RelationPanel.tsx

import { useState, useEffect } from 'react'
import { Link, Plus, Edit, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { relationApi, characterApi } from '@/lib/characterApi'
import type { RelationWithCharacters } from '@/types'
import type { Character } from '@/types/character'

interface RelationPanelProps
{
  projectId: number
}

const RELATION_COLORS: Record<string, string> = {
  '信任': 'bg-green-100 text-green-800',
  '敌对': 'bg-red-100 text-red-800',
  '感情': 'bg-pink-100 text-pink-800',
  '合作': 'bg-blue-100 text-blue-800',
  '利用': 'bg-orange-100 text-orange-800',
  '陌生': 'bg-gray-100 text-gray-800',
}

export function RelationPanel({ projectId }: RelationPanelProps)
{
  const [relations, setRelations] = useState<RelationWithCharacters[]>([])
  const [loading, setLoading] = useState(true)

  // Dialog 状态
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRelation, setEditingRelation] = useState<RelationWithCharacters | null>(null)
  const [characterList, setCharacterList] = useState<Character[]>([])
  // 表单字段
  const [formCharAId, setFormCharAId] = useState<number | string>('')
  const [formCharBId, setFormCharBId] = useState<number | string>('')
  const [formRelationType, setFormRelationType] = useState('陌生')
  const [formStatus, setFormStatus] = useState('')
  const [formTrustLevel, setFormTrustLevel] = useState(50)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() =>
  {
    const fetchRelations = async () =>
    {
      try
      {
        const data = await relationApi.list(projectId)
        setRelations(data.relations)
      }
      catch (err)
      {
        console.error('Failed to fetch relations:', err)
        toast.error('加载关系失败，请重试')
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchRelations()
  }, [projectId])

  const resetForm = () =>
  {
    setFormCharAId('')
    setFormCharBId('')
    setFormRelationType('陌生')
    setFormStatus('')
    setFormTrustLevel(50)
  }

  // 打开新增弹窗
  const openCreateDialog = async () =>
  {
    setEditingRelation(null)
    resetForm()
    try
    {
      const data = await characterApi.list(projectId)
      setCharacterList(data.characters)
    }
    catch (err)
    {
      console.error('Failed to load characters:', err)
      toast.error('加载人物列表失败')
    }
    setDialogOpen(true)
  }

  // 打开编辑弹窗（预填数据）
  const openEditDialog = async (relation: RelationWithCharacters) =>
  {
    setEditingRelation(relation)
    setFormCharAId(relation.character_a_id)
    setFormCharBId(relation.character_b_id)
    setFormRelationType(relation.relation_type)
    setFormStatus(relation.current_status || '')
    setFormTrustLevel(relation.trust_level)
    try
    {
      const data = await characterApi.list(projectId)
      setCharacterList(data.characters)
    }
    catch (err)
    {
      console.error('Failed to load characters:', err)
      toast.error('加载人物列表失败')
    }
    setDialogOpen(true)
  }

  // 提交表单
  const handleSubmit = async () =>
  {
    if (!formCharAId || !formCharBId)
    {
      toast.error('请选择两个人物')
      return
    }
    if (typeof formCharAId === 'string' || typeof formCharBId === 'string')
    {
      toast.error('请选择有效的人物')
      return
    }
    if (formCharAId === formCharBId)
    {
      toast.error('不能选择同一个人物')
      return
    }

    setSubmitting(true)
    try
    {
      if (editingRelation)
      {
        await relationApi.update(
          projectId,
          editingRelation.id,
          {
            character_a_id: formCharAId as number,
            character_b_id: formCharBId as number,
            relation_type: formRelationType,
            current_status: formStatus,
            trust_level: formTrustLevel,
          }
        )
        toast.success('关系已更新')
      }
      else
      {
        await relationApi.create(projectId, {
          character_a_id: formCharAId as number,
          character_b_id: formCharBId as number,
          relation_type: formRelationType,
          current_status: formStatus,
          trust_level: formTrustLevel,
        })
        toast.success('关系已创建')
      }

      // 重新加载列表
      const data = await relationApi.list(projectId)
      setRelations(data.relations)
      setDialogOpen(false)
      resetForm()
    }
    catch (err)
    {
      console.error('Failed to save relation:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) =>
  {
    if (!confirm('确定要删除这个关系吗？')) return
    try
    {
      await relationApi.delete(projectId, id)
      setRelations(relations.filter(r => r.id !== id))
      toast.success('关系已删除')
    }
    catch (err)
    {
      console.error('Failed to delete relation:', err)
      toast.error('删除关系失败，请重试')
    }
  }

  if (loading)
  {
    return <div className="flex items-center justify-center h-full">加载中...</div>
  }

  return (
    <div className="p-6 overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Link className="h-5 w-5" />
          人物关系
        </h2>
        <Button size="sm" onClick={openCreateDialog}>
          <Plus className="h-4 w-4 mr-2" />
          新增关系
        </Button>
      </div>

      {/* 关系列表表格 */}
      <div className="bg-white rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left text-sm font-medium">人物A</th>
              <th className="px-4 py-3 text-left text-sm font-medium">关系类型</th>
              <th className="px-4 py-3 text-left text-sm font-medium">人物B</th>
              <th className="px-4 py-3 text-left text-sm font-medium">当前状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium">信任度</th>
              <th className="px-4 py-3 text-left text-sm font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {relations.map((relation) => (
              <tr key={relation.id} className="border-b last:border-b-0 hover:bg-muted/30">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm">
                      {relation.character_a?.name?.charAt(0) || '?'}
                    </div>
                    <span className="font-medium">{relation.character_a?.name || '未知'}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 text-xs rounded-full ${RELATION_COLORS[relation.relation_type] || 'bg-gray-100'}`}>
                    {relation.relation_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm">
                      {relation.character_b?.name?.charAt(0) || '?'}
                    </div>
                    <span className="font-medium">{relation.character_b?.name || '未知'}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {relation.current_status || '-'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${relation.trust_level > 60 ? 'bg-green-500' : relation.trust_level > 30 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${relation.trust_level}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{relation.trust_level}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => openEditDialog(relation)}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(relation.id)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {relations.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">
            <Link className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>暂无人物关系</p>
            <p className="text-sm mt-1">点击上方按钮添加人物关系</p>
          </div>
        )}
      </div>

      {/* 关系新增/编辑弹窗 */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingRelation ? '编辑关系' : '新增关系'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-1">
              <Label htmlFor="char-a">人物A <span className="text-red-500">*</span></Label>
              <Select
                value={String(formCharAId)}
                onValueChange={(v) => setFormCharAId(parseInt(v))}
              >
                <SelectTrigger id="char-a">
                  <SelectValue placeholder="选择人物" />
                </SelectTrigger>
                <SelectContent>
                  {characterList.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="relation-type">关系类型</Label>
              <Select value={formRelationType} onValueChange={setFormRelationType}>
                <SelectTrigger id="relation-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="信任">信任</SelectItem>
                  <SelectItem value="敌对">敌对</SelectItem>
                  <SelectItem value="感情">感情</SelectItem>
                  <SelectItem value="合作">合作</SelectItem>
                  <SelectItem value="利用">利用</SelectItem>
                  <SelectItem value="陌生">陌生</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="char-b">人物B <span className="text-red-500">*</span></Label>
              <Select
                value={String(formCharBId)}
                onValueChange={(v) => setFormCharBId(parseInt(v))}
              >
                <SelectTrigger id="char-b">
                  <SelectValue placeholder="选择人物" />
                </SelectTrigger>
                <SelectContent>
                  {characterList.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>当前状态</Label>
              <Input
                value={formStatus}
                onChange={(e) => setFormStatus(e.target.value)}
                placeholder="描述当前关系状态"
              />
            </div>

            <div className="space-y-1">
              <Label>信任度 ({formTrustLevel})</Label>
              <input
                type="range"
                min="0"
                max="100"
                value={formTrustLevel}
                onChange={(e) => setFormTrustLevel(parseInt(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0</span>
                <span>100</span>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>取消</Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? '保存中...' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
