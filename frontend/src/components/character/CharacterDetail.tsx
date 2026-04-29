import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { Character } from '@/types'

// 角色类型选项
const ROLE_OPTIONS = ['主角', '核心反派', '重要配角', '配角']

interface CharacterDetailProps
{
    character: Character
    isEditing: boolean
    editForm: Partial<Character>
    saving: boolean
    onStartEdit: () => void
    onCancelEdit: () => void
    onSaveEdit: () => void
    onDeleteCharacter: () => void
    onEditFormChange: (form: Partial<Character>) => void
}

export default function CharacterDetail({
    character,
    isEditing,
    editForm,
    saving,
    onStartEdit,
    onCancelEdit,
    onSaveEdit,
    onDeleteCharacter,
    onEditFormChange,
}: CharacterDetailProps)
{
    return (
        <ScrollArea className="flex-1">
            <div className="p-4 space-y-4">
                {isEditing ? (
                    /* 编辑模式 */
                    <>
                        <div>
                            <Label className="text-sm text-muted-foreground">姓名</Label>
                            <Input
                                value={editForm.name || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, name: e.target.value })}
                                className="mt-1"
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">角色</Label>
                            <Select
                                value={editForm.role || ''}
                                onValueChange={(value) => onEditFormChange({ ...editForm, role: value })}
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
                            <Label className="text-sm text-muted-foreground">性格特点</Label>
                            <Textarea
                                value={editForm.personality || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, personality: e.target.value })}
                                className="mt-1"
                                rows={3}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">口头禅</Label>
                            <Input
                                value={editForm.catchphrase || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, catchphrase: e.target.value })}
                                className="mt-1"
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">习惯性动作</Label>
                            <Input
                                value={editForm.habit_action || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, habit_action: e.target.value })}
                                className="mt-1"
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">内心深处的恐惧</Label>
                            <Textarea
                                value={editForm.deep_fear || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, deep_fear: e.target.value })}
                                className="mt-1"
                                rows={2}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">核心动机</Label>
                            <Textarea
                                value={editForm.core_motivation || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, core_motivation: e.target.value })}
                                className="mt-1"
                                rows={2}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">成长弧光</Label>
                            <Textarea
                                value={editForm.growth_arc || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, growth_arc: e.target.value })}
                                className="mt-1"
                                rows={2}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">外貌描写</Label>
                            <Textarea
                                value={editForm.appearance || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, appearance: e.target.value })}
                                className="mt-1"
                                rows={3}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">背景故事</Label>
                            <Textarea
                                value={editForm.backstory || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, backstory: e.target.value })}
                                className="mt-1"
                                rows={4}
                            />
                        </div>
                        <div>
                            <Label className="text-sm text-muted-foreground">标志性物品</Label>
                            <Input
                                value={editForm.signature_item || ''}
                                onChange={(e) => onEditFormChange({ ...editForm, signature_item: e.target.value })}
                                className="mt-1"
                            />
                        </div>
                        <div className="flex gap-2 pt-4">
                            <Button variant="outline" onClick={onCancelEdit} className="flex-1">
                                取消
                            </Button>
                            <Button onClick={onSaveEdit} disabled={saving} className="flex-1">
                                {saving ? '保存中...' : '保存'}
                            </Button>
                        </div>
                    </>
                ) : (
                    /* 查看模式 */
                    <>
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold">{character.name}</h3>
                            <div className="flex gap-1">
                                <Button variant="ghost" size="icon" onClick={onStartEdit}>
                                    <Pencil className="h-4 w-4" />
                                </Button>
                                <Button variant="ghost" size="icon" onClick={onDeleteCharacter}>
                                    <Trash2 className="h-4 w-4 text-destructive" />
                                </Button>
                            </div>
                        </div>
                        <div className="text-sm text-muted-foreground">
                            角色: {character.role}
                        </div>

                        <div className="pt-2 space-y-3">
                            {character.personality && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">性格特点</Label>
                                    <p className="text-sm mt-1">{character.personality}</p>
                                </div>
                            )}
                            {character.catchphrase && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">口头禅</Label>
                                    <p className="text-sm mt-1 italic">"{character.catchphrase}"</p>
                                </div>
                            )}
                            {character.habit_action && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">习惯性动作</Label>
                                    <p className="text-sm mt-1">{character.habit_action}</p>
                                </div>
                            )}
                            {character.deep_fear && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">内心深处的恐惧</Label>
                                    <p className="text-sm mt-1">{character.deep_fear}</p>
                                </div>
                            )}
                            {character.core_motivation && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">核心动机</Label>
                                    <p className="text-sm mt-1">{character.core_motivation}</p>
                                </div>
                            )}
                            {character.growth_arc && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">成长弧光</Label>
                                    <p className="text-sm mt-1">{character.growth_arc}</p>
                                </div>
                            )}
                            {character.appearance && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">外貌描写</Label>
                                    <p className="text-sm mt-1">{character.appearance}</p>
                                </div>
                            )}
                            {character.backstory && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">背景故事</Label>
                                    <p className="text-sm mt-1">{character.backstory}</p>
                                </div>
                            )}
                            {character.signature_item && (
                                <div>
                                    <Label className="text-sm text-muted-foreground">标志性物品</Label>
                                    <p className="text-sm mt-1">{character.signature_item}</p>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </ScrollArea>
    )
}
