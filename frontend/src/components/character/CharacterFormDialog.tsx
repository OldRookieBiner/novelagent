import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { CharacterCreate, CharacterUpdate, Character } from '@/types'

// 角色类型选项
const ROLE_OPTIONS = ['主角', '核心反派', '重要配角', '配角']

interface CharacterFormDialogProps
{
    open: boolean
    saving: boolean
    onClose: () => void
    onSubmit: (data: CharacterCreate | CharacterUpdate) => void
    character?: Character
}

export default function CharacterFormDialog({
    open,
    saving,
    onClose,
    onSubmit,
    character,
}: CharacterFormDialogProps)
{
    if (!open) return null

    // 表单状态由容器管理，通过内部 state 管理
    // 这里使用独立状态管理表单数据
    return <CharacterFormDialogInner saving={saving} onClose={onClose} onSubmit={onSubmit} character={character} />
}

function CharacterFormDialogInner({
    saving,
    onClose,
    onSubmit,
    character,
}: Omit<CharacterFormDialogProps, 'open'>)
{
    const isEditing = !!character
    const [form, setForm] = useState<CharacterCreate | CharacterUpdate>(
        character ? {
            name: character.name,
            role: character.role,
            personality: character.personality || '',
            backstory: character.backstory || '',
            appearance: character.appearance || '',
            core_motivation: character.core_motivation || '',
            knowledge_boundary: character.knowledge_boundary || '',
        } : {
            name: '',
            role: '配角',
        }
    )

    const handleSubmit = () =>
    {
        onSubmit(form)
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <Card className="w-[400px]">
                <CardHeader>
                    <CardTitle>{isEditing ? '编辑人物' : '新增人物'}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div>
                        <Label>姓名 *</Label>
                        <Input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            placeholder="请输入人物姓名"
                            className="mt-1"
                        />
                    </div>
                    <div>
                        <Label>角色</Label>
                        <Select
                            value={form.role}
                            onValueChange={(value) => setForm({ ...form, role: value })}
                        >
                            <SelectTrigger className="mt-1">
                                <SelectValue placeholder="选择角色定位" />
                            </SelectTrigger>
                            <SelectContent>
                                {ROLE_OPTIONS.map((role) => (
                                    <SelectItem key={role} value={role}>{role}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>性格特点</Label>
                        <Textarea
                            value={form.personality || ''}
                            onChange={(e) => setForm({ ...form, personality: e.target.value })}
                            placeholder="描述人物的性格特点"
                            className="mt-1"
                            rows={3}
                        />
                    </div>
                    <div>
                        <Label>知识边界（防 OOC）</Label>
                        <Textarea
                            value={form.knowledge_boundary || ''}
                            onChange={(e) => setForm({ ...form, knowledge_boundary: e.target.value })}
                            placeholder="不知道：……；误以为：……"
                            className="mt-1"
                            rows={2}
                        />
                    </div>
                    <div className="flex gap-2 pt-2">
                        <Button variant="outline" onClick={onClose} className="flex-1">
                            取消
                        </Button>
                        <Button onClick={handleSubmit} disabled={saving} className="flex-1">
                            {saving ? (isEditing ? '保存中...' : '创建中...') : (isEditing ? '保存' : '创建')}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
