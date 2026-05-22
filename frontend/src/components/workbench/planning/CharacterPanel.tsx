// frontend/src/components/workbench/planning/CharacterPanel.tsx

import { useState, useEffect } from 'react'
import { Users, Plus, Edit, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useWorkbenchStore } from '@/stores/workbenchStore'
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
import { characterApi } from '@/lib/characterApi'
import type { Character, CharacterCreate, CharacterUpdate } from '@/types/character'

interface CharacterPanelProps
{
  projectId: number
}

const ROLE_COLORS: Record<string, string> = {
  '主角': 'bg-yellow-100 text-yellow-800',
  '核心反派': 'bg-red-100 text-red-800',
  '重要配角': 'bg-blue-100 text-blue-800',
  '配角': 'bg-gray-100 text-gray-800',
  '次要': 'bg-purple-100 text-purple-800',
}

export function CharacterPanel({ projectId }: CharacterPanelProps)
{
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)
  // AI 更新标记
  const aiUpdateMarkers = useWorkbenchStore((s) => s.aiUpdateMarkers)
  const charactersUpdated = !!aiUpdateMarkers.characters

  // Dialog 状态
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null)
  // 表单字段
  const [formName, setFormName] = useState('')
  const [formRole, setFormRole] = useState('配角')
  const [formPersonality, setFormPersonality] = useState('')
  const [formMotivation, setFormMotivation] = useState('')
  const [formCatchphrase, setFormCatchphrase] = useState('')
  const [formBackstory, setFormBackstory] = useState('')
  const [formAppearance, setFormAppearance] = useState('')
  const [formHabitAction, setFormHabitAction] = useState('')
  const [formDeepFear, setFormDeepFear] = useState('')
  const [formGrowthArc, setFormGrowthArc] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() =>
  {
    const fetchCharacters = async () =>
    {
      try
      {
        const data = await characterApi.list(projectId)
        setCharacters(Array.isArray(data?.characters) ? data.characters : [])
      }
      catch (err)
      {
        console.error('Failed to fetch characters:', err)
        toast.error('加载人物失败，请重试')
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchCharacters()
  }, [projectId])

  // 打开新增弹窗
  const openCreateDialog = () =>
  {
    setEditingCharacter(null)
    resetForm()
    setDialogOpen(true)
  }

  // 打开编辑弹窗（预填数据）
  const openEditDialog = (character: Character) =>
  {
    setEditingCharacter(character)
    setFormName(character.name)
    setFormRole(character.role)
    setFormPersonality(character.personality || '')
    setFormMotivation(character.core_motivation || '')
    setFormCatchphrase(character.catchphrase || '')
    setFormBackstory(character.backstory || '')
    setFormAppearance(character.appearance || '')
    setFormHabitAction(character.habit_action || '')
    setFormDeepFear(character.deep_fear || '')
    setFormGrowthArc(character.growth_arc || '')
    setDialogOpen(true)
  }

  // 重置表单
  const resetForm = () =>
  {
    setFormName('')
    setFormRole('配角')
    setFormPersonality('')
    setFormMotivation('')
    setFormCatchphrase('')
    setFormBackstory('')
    setFormAppearance('')
    setFormHabitAction('')
    setFormDeepFear('')
    setFormGrowthArc('')
  }

  // 提交表单
  const handleSubmit = async () =>
  {
    if (!formName.trim())
    {
      toast.error('请输入人物姓名')
      return
    }

    setSubmitting(true)
    try
    {
      if (editingCharacter)
      {
        // 更新人物
        const data: CharacterUpdate = {
          name: formName,
          role: formRole,
          personality: formPersonality,
          core_motivation: formMotivation,
          catchphrase: formCatchphrase,
          backstory: formBackstory,
          appearance: formAppearance,
          habit_action: formHabitAction,
          deep_fear: formDeepFear,
          growth_arc: formGrowthArc,
        }

        const updated = await characterApi.update(projectId, editingCharacter.id, data)
        setCharacters(characters.map(c => c.id === updated.id ? updated : c))
        toast.success('人物已更新')
      }
      else
      {
        // 创建人物
        const data: CharacterCreate = {
          name: formName,
          role: formRole,
          personality: formPersonality,
          core_motivation: formMotivation,
          catchphrase: formCatchphrase,
          backstory: formBackstory,
          appearance: formAppearance,
          habit_action: formHabitAction,
          deep_fear: formDeepFear,
          growth_arc: formGrowthArc,
        }

        const created = await characterApi.create(projectId, data)
        setCharacters([...characters, created])
        toast.success('人物已创建')
      }

      setDialogOpen(false)
      resetForm()
    }
    catch (err)
    {
      console.error('Failed to save character:', err)
      toast.error('保存失败')
    }
    finally
    {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) =>
  {
    if (!confirm('确定要删除这个人物吗？')) return
    try
    {
      await characterApi.delete(projectId, id)
      setCharacters(characters.filter(c => c.id !== id))
      toast.success('人物已删除')
    }
    catch (err)
    {
      console.error('Failed to delete character:', err)
      toast.error('删除人物失败，请重试')
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
          <Users className="h-5 w-5" />
          人物管理
          {charactersUpdated && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-200 animate-pulse">
              🤖 AI 已更新
            </span>
          )}
        </h2>
        <Button size="sm" onClick={openCreateDialog}>
          <Plus className="h-4 w-4 mr-2" />
          新增人物
        </Button>
      </div>

      {/* 大卡片网格 */}
      <div className="grid grid-cols-2 gap-6">
        {characters.map((character) => (
          <Card key={character.id} className="min-h-[200px]">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-lg font-medium">
                    {character.name.charAt(0)}
                  </div>
                  <div>
                    <CardTitle className="text-lg">{character.name}</CardTitle>
                    <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${ROLE_COLORS[character.role] || 'bg-gray-100'}`}>
                      {character.role}
                    </span>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {character.personality && (
                <div>
                  <span className="text-xs text-muted-foreground">性格</span>
                  <p className="text-sm line-clamp-2">{character.personality}</p>
                </div>
              )}
              {character.core_motivation && (
                <div>
                  <span className="text-xs text-muted-foreground">核心动机</span>
                  <p className="text-sm line-clamp-1">{character.core_motivation}</p>
                </div>
              )}
              {character.catchphrase && (
                <div>
                  <span className="text-xs text-muted-foreground">口头禅</span>
                  <p className="text-sm italic">"{character.catchphrase}"</p>
                </div>
              )}
              {character.habit_action && (
                <div>
                  <span className="text-xs text-muted-foreground">习惯动作</span>
                  <p className="text-sm line-clamp-1">{character.habit_action}</p>
                </div>
              )}
              {character.appearance && (
                <div>
                  <span className="text-xs text-muted-foreground">外貌</span>
                  <p className="text-sm line-clamp-2">{character.appearance}</p>
                </div>
              )}
              {character.backstory && (
                <div>
                  <span className="text-xs text-muted-foreground">背景故事</span>
                  <p className="text-sm line-clamp-2">{character.backstory}</p>
                </div>
              )}
              {character.deep_fear && (
                <div>
                  <span className="text-xs text-muted-foreground">深层恐惧</span>
                  <p className="text-sm line-clamp-1">{character.deep_fear}</p>
                </div>
              )}
              {character.growth_arc && (
                <div>
                  <span className="text-xs text-muted-foreground">成长弧线</span>
                  <p className="text-sm line-clamp-2">{character.growth_arc}</p>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t">
                <span className="text-xs text-muted-foreground">关系: 0</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(character)}>
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(character.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* 添加新人物卡片 */}
        <Card
          className="min-h-[280px] border-dashed flex items-center justify-center cursor-pointer hover:bg-muted/50 transition-colors"
          onClick={openCreateDialog}
        >
          <div className="text-center text-muted-foreground">
            <Plus className="h-8 w-8 mx-auto mb-2" />
            <span>添加新人物</span>
          </div>
        </Card>
      </div>

      {/* 人物新增/编辑弹窗 */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>{editingCharacter ? '编辑人物' : '新增人物'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label htmlFor="char-name">姓名 <span className="text-red-500">*</span></Label>
                <Input
                  id="char-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="人物姓名"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="char-role">角色定位</Label>
                <Select value={formRole} onValueChange={setFormRole}>
                  <SelectTrigger id="char-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="主角">主角</SelectItem>
                    <SelectItem value="核心反派">核心反派</SelectItem>
                    <SelectItem value="重要配角">重要配角</SelectItem>
                    <SelectItem value="配角">配角</SelectItem>
                    <SelectItem value="次要">次要</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1">
              <Label>性格特点</Label>
              <Textarea
                value={formPersonality}
                onChange={(e) => setFormPersonality(e.target.value)}
                placeholder="描述人物性格特点"
                rows={2}
              />
            </div>

            <div className="space-y-1">
              <Label>核心动机</Label>
              <Input
                value={formMotivation}
                onChange={(e) => setFormMotivation(e.target.value)}
                placeholder="人物的核心驱动力"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>口头禅</Label>
                <Input
                  value={formCatchphrase}
                  onChange={(e) => setFormCatchphrase(e.target.value)}
                  placeholder="人物的口头禅或标志性语言"
                />
              </div>
              <div className="space-y-1">
                <Label>习惯动作</Label>
                <Input
                  value={formHabitAction}
                  onChange={(e) => setFormHabitAction(e.target.value)}
                  placeholder="人物的习惯动作"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label>外貌描写</Label>
              <Textarea
                value={formAppearance}
                onChange={(e) => setFormAppearance(e.target.value)}
                placeholder="描述人物外貌特征"
                rows={2}
              />
            </div>

            <div className="space-y-1">
              <Label>背景故事</Label>
              <Textarea
                value={formBackstory}
                onChange={(e) => setFormBackstory(e.target.value)}
                placeholder="人物的身世和经历"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>深层恐惧</Label>
                <Input
                  value={formDeepFear}
                  onChange={(e) => setFormDeepFear(e.target.value)}
                  placeholder="人物内心深处的恐惧"
                />
              </div>
              <div className="space-y-1">
                <Label>成长弧线</Label>
                <Input
                  value={formGrowthArc}
                  onChange={(e) => setFormGrowthArc(e.target.value)}
                  placeholder="人物的成长轨迹"
                />
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