import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { Character, RelationCreate, RelationUpdate, RelationWithCharacters } from '@/types'

// 关系类型选项
const RELATION_TYPES = ['信任', '敌对', '感情', '合作', '利用', '陌生']

// 关系方向选项
const DIRECTION_OPTIONS = ['双向', '单向A→B', '单向B→A']

interface RelationFormDialogProps
{
    open: boolean
    saving: boolean
    characters: Character[]
    onClose: () => void
    onSubmit: (data: RelationCreate | RelationUpdate) => void
    relation?: RelationWithCharacters
}

export default function RelationFormDialog({
    open,
    saving,
    characters,
    onClose,
    onSubmit,
    relation,
}: RelationFormDialogProps)
{
    if (!open) return null

    return (
        <RelationFormDialogInner
            saving={saving}
            characters={characters}
            onClose={onClose}
            onSubmit={onSubmit}
            relation={relation}
        />
    )
}

function RelationFormDialogInner({
    saving,
    characters,
    onClose,
    onSubmit,
    relation,
}: Omit<RelationFormDialogProps, 'open'>)
{
    const isEditing = !!relation
    const [form, setForm] = useState<RelationCreate | RelationUpdate>(
        relation ? {
            relation_type: relation.relation_type,
            direction: relation.direction,
            trust_level: relation.trust_level,
        } : {
            character_a_id: 0,
            character_b_id: 0,
            relation_type: '陌生',
            direction: '双向',
            trust_level: 50,
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
                    <CardTitle>{isEditing ? '编辑关系' : '新增关系'}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div>
                        <Label>人物 A</Label>
                        <Select
                            value={form.character_a_id.toString()}
                            onValueChange={(value) => setForm({ ...form, character_a_id: parseInt(value) })}
                        >
                            <SelectTrigger className="mt-1">
                                <SelectValue placeholder="请选择人物" />
                            </SelectTrigger>
                            <SelectContent>
                                {characters.map((c) => (
                                    <SelectItem key={c.id} value={c.id.toString()}>{c.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>人物 B</Label>
                        <Select
                            value={form.character_b_id.toString()}
                            onValueChange={(value) => setForm({ ...form, character_b_id: parseInt(value) })}
                        >
                            <SelectTrigger className="mt-1">
                                <SelectValue placeholder="请选择人物" />
                            </SelectTrigger>
                            <SelectContent>
                                {characters.map((c) => (
                                    <SelectItem key={c.id} value={c.id.toString()}>{c.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>关系类型</Label>
                        <Select
                            value={form.relation_type}
                            onValueChange={(value) => setForm({ ...form, relation_type: value })}
                        >
                            <SelectTrigger className="mt-1">
                                <SelectValue placeholder="选择关系类型" />
                            </SelectTrigger>
                            <SelectContent>
                                {RELATION_TYPES.map((type) => (
                                    <SelectItem key={type} value={type}>{type}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>方向</Label>
                        <Select
                            value={form.direction}
                            onValueChange={(value) => setForm({ ...form, direction: value })}
                        >
                            <SelectTrigger className="mt-1">
                                <SelectValue placeholder="选择方向" />
                            </SelectTrigger>
                            <SelectContent>
                                {DIRECTION_OPTIONS.map((dir) => (
                                    <SelectItem key={dir} value={dir}>{dir}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>信任度 (0-100)</Label>
                        <Input
                            type="number"
                            min={0}
                            max={100}
                            value={form.trust_level}
                            onChange={(e) => setForm({ ...form, trust_level: parseInt(e.target.value) || 50 })}
                            className="mt-1"
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
