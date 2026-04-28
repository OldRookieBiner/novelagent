// frontend/src/pages/CharacterSetting.tsx
import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Plus, Users, Heart, X, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { characterApi, relationApi } from '@/lib/characterApi'
import { projectsApi } from '@/lib/api'
import type { Character, CharacterCreate, RelationWithCharacters, RelationCreate } from '@/types'
import type { Project } from '@/types'

// 标签页类型
type TabType = 'characters' | 'relations'

// 角色类型选项
const ROLE_OPTIONS = ['主角', '核心反派', '重要配角', '配角']

// 关系类型选项
const RELATION_TYPES = ['信任', '敌对', '感情', '合作', '利用', '陌生']

// 关系方向选项
const DIRECTION_OPTIONS = ['双向', '单向A->B', '单向B->A']

export default function CharacterSetting()
{
    const { id } = useParams<{ id: string }>()
    const projectId = id ? parseInt(id) : null

    // 项目状态
    const [project, setProject] = useState<Project | null>(null)
    const [loading, setLoading] = useState(true)

    // 标签页状态
    const [activeTab, setActiveTab] = useState<TabType>('characters')

    // 人物列表状态
    const [characters, setCharacters] = useState<Character[]>([])
    const [charactersLoading, setCharactersLoading] = useState(false)
    const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)

    // 关系列表状态
    const [relations, setRelations] = useState<RelationWithCharacters[]>([])
    const [relationsLoading, setRelationsLoading] = useState(false)
    const [selectedRelation, setSelectedRelation] = useState<RelationWithCharacters | null>(null)

    // 编辑状态
    const [isEditing, setIsEditing] = useState(false)
    const [editForm, setEditForm] = useState<Partial<Character>>({})
    const [saving, setSaving] = useState(false)

    // 新增人物弹窗状态
    const [showAddDialog, setShowAddDialog] = useState(false)
    const [newCharacter, setNewCharacter] = useState<CharacterCreate>({
        name: '',
        role: '配角',
    })

    // 新增关系弹窗状态
    const [showAddRelationDialog, setShowAddRelationDialog] = useState(false)
    const [newRelation, setNewRelation] = useState<RelationCreate>({
        character_a_id: 0,
        character_b_id: 0,
        relation_type: '陌生',
        direction: '双向',
        trust_level: 50,
    })

    // 加载项目信息
    useEffect(() =>
    {
        const fetchProject = async () =>
        {
            if (!projectId) return
            try
            {
                const data = await projectsApi.get(projectId)
                setProject(data)
            }
            catch (err)
            {
                console.error('Failed to fetch project:', err)
                toast.error('加载项目失败')
            }
            finally
            {
                setLoading(false)
            }
        }
        fetchProject()
    }, [projectId])

    // 加载人物列表
    useEffect(() =>
    {
        const fetchCharacters = async () =>
        {
            if (!projectId) return
            setCharactersLoading(true)
            try
            {
                const data = await characterApi.list(projectId)
                setCharacters(data.characters)
            }
            catch (err)
            {
                console.error('Failed to fetch characters:', err)
            }
            finally
            {
                setCharactersLoading(false)
            }
        }
        if (activeTab === 'characters')
        {
            fetchCharacters()
        }
    }, [projectId, activeTab])

    // 加载关系列表
    useEffect(() =>
    {
        const fetchRelations = async () =>
        {
            if (!projectId) return
            setRelationsLoading(true)
            try
            {
                const data = await relationApi.list(projectId)
                setRelations(data.relations)
            }
            catch (err)
            {
                console.error('Failed to fetch relations:', err)
            }
            finally
            {
                setRelationsLoading(false)
            }
        }
        if (activeTab === 'relations')
        {
            fetchRelations()
        }
    }, [projectId, activeTab])

    // 选择人物时重置编辑状态
    useEffect(() =>
    {
        setIsEditing(false)
        setEditForm({})
    }, [selectedCharacter])

    // 处理人物卡片点击
    const handleCharacterClick = (character: Character) =>
    {
        setSelectedCharacter(character)
        setSelectedRelation(null)
    }

    // 处理关系卡片点击
    const handleRelationClick = (relation: RelationWithCharacters) =>
    {
        setSelectedRelation(relation)
        setSelectedCharacter(null)
    }

    // 关闭侧边栏
    const handleCloseSidebar = () =>
    {
        setSelectedCharacter(null)
        setSelectedRelation(null)
        setIsEditing(false)
        setEditForm({})
    }

    // 开始编辑人物
    const handleStartEdit = () =>
    {
        if (selectedCharacter)
        {
            setEditForm({ ...selectedCharacter })
            setIsEditing(true)
        }
    }

    // 取消编辑
    const handleCancelEdit = () =>
    {
        setIsEditing(false)
        setEditForm({})
    }

    // 保存人物编辑
    const handleSaveEdit = async () =>
    {
        if (!projectId || !selectedCharacter) return
        setSaving(true)
        try
        {
            const updated = await characterApi.update(projectId, selectedCharacter.id, editForm)
            setCharacters((prev) =>
                prev.map((c) => (c.id === updated.id ? updated : c))
            )
            setSelectedCharacter(updated)
            setIsEditing(false)
            setEditForm({})
            toast.success('保存成功')
        }
        catch (err)
        {
            console.error('Failed to save character:', err)
            toast.error('保存失败')
        }
        finally
        {
            setSaving(false)
        }
    }

    // 删除人物
    const handleDeleteCharacter = async () =>
    {
        if (!projectId || !selectedCharacter) return
        if (!confirm(`确定要删除人物 "${selectedCharacter.name}" 吗？`)) return

        try
        {
            await characterApi.delete(projectId, selectedCharacter.id)
            setCharacters((prev) => prev.filter((c) => c.id !== selectedCharacter.id))
            setSelectedCharacter(null)
            toast.success('删除成功')
        }
        catch (err)
        {
            console.error('Failed to delete character:', err)
            toast.error('删除失败')
        }
    }

    // 创建新人物
    const handleCreateCharacter = async () =>
    {
        if (!projectId || !newCharacter.name.trim())
        {
            toast.error('请输入人物名称')
            return
        }

        setSaving(true)
        try
        {
            const created = await characterApi.create(projectId, newCharacter)
            setCharacters((prev) => [...prev, created])
            setShowAddDialog(false)
            setNewCharacter({ name: '', role: '配角' })
            toast.success('创建成功')
        }
        catch (err)
        {
            console.error('Failed to create character:', err)
            toast.error('创建失败')
        }
        finally
        {
            setSaving(false)
        }
    }

    // 创建新关系
    const handleCreateRelation = async () =>
    {
        if (!projectId) return
        if (!newRelation.character_a_id || !newRelation.character_b_id)
        {
            toast.error('请选择两个人物')
            return
        }
        if (newRelation.character_a_id === newRelation.character_b_id)
        {
            toast.error('不能选择相同的人物')
            return
        }

        setSaving(true)
        try
        {
            const created = await relationApi.create(projectId, newRelation)
            // 重新加载关系列表以获取人物详情
            const data = await relationApi.list(projectId)
            setRelations(data.relations)
            setShowAddRelationDialog(false)
            setNewRelation({
                character_a_id: 0,
                character_b_id: 0,
                relation_type: '陌生',
                direction: '双向',
                trust_level: 50,
            })
            toast.success('创建成功')
        }
        catch (err)
        {
            console.error('Failed to create relation:', err)
            toast.error('创建失败')
        }
        finally
        {
            setSaving(false)
        }
    }

    // 删除关系
    const handleDeleteRelation = async () =>
    {
        if (!projectId || !selectedRelation) return
        if (!confirm('确定要删除这个关系吗？')) return

        try
        {
            await relationApi.delete(projectId, selectedRelation.id)
            setRelations((prev) => prev.filter((r) => r.id !== selectedRelation.id))
            setSelectedRelation(null)
            toast.success('删除成功')
        }
        catch (err)
        {
            console.error('Failed to delete relation:', err)
            toast.error('删除失败')
        }
    }

    if (loading)
    {
        return <div className="text-center py-10">加载中...</div>
    }

    if (!project)
    {
        return <div className="text-center py-10">项目不存在</div>
    }

    return (
        <div className="flex flex-1">
            {/* 主内容区 */}
            <div className="flex-1 p-6">
                {/* 头部 */}
                <div className="mb-6">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-4">
                            <Link to={`/project/${projectId}`}>
                                <Button variant="ghost" size="sm">
                                    <ArrowLeft className="h-4 w-4 mr-2" />
                                    返回项目
                                </Button>
                            </Link>
                            <h1 className="text-2xl font-bold">人物设定</h1>
                        </div>
                        <Button onClick={() =>
                        {
                            if (activeTab === 'characters')
                            {
                                setShowAddDialog(true)
                            }
                            else
                            {
                                setShowAddRelationDialog(true)
                            }
                        }}>
                            <Plus className="h-4 w-4 mr-2" />
                            新增{activeTab === 'characters' ? '人物' : '关系'}
                        </Button>
                    </div>
                    <p className="text-muted-foreground">{project.name}</p>
                </div>

                {/* 标签页切换 */}
                <div className="border-b mb-6">
                    <div className="flex">
                        <button
                            onClick={() => setActiveTab('characters')}
                            className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors ${activeTab === 'characters'
                                ? 'bg-background border-b-2 border-primary font-medium text-foreground'
                                : 'text-muted-foreground hover:text-foreground'
                                }`}
                        >
                            <Users className="h-4 w-4" />
                            人物
                        </button>
                        <button
                            onClick={() => setActiveTab('relations')}
                            className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors ${activeTab === 'relations'
                                ? 'bg-background border-b-2 border-primary font-medium text-foreground'
                                : 'text-muted-foreground hover:text-foreground'
                                }`}
                        >
                            <Heart className="h-4 w-4" />
                            关系
                        </button>
                    </div>
                </div>

                {/* 人物列表 */}
                {activeTab === 'characters' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {charactersLoading ? (
                            <div className="col-span-4 text-center py-10 text-muted-foreground">
                                加载中...
                            </div>
                        ) : characters.length === 0 ? (
                            <div className="col-span-4 text-center py-10 text-muted-foreground">
                                暂无人物，点击右上角"新增人物"按钮添加
                            </div>
                        ) : (
                            characters.map((character) => (
                                <Card
                                    key={character.id}
                                    className={`cursor-pointer transition-all hover:shadow-md ${selectedCharacter?.id === character.id
                                        ? 'ring-2 ring-primary'
                                        : ''
                                        }`}
                                    onClick={() => handleCharacterClick(character)}
                                >
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-base flex items-center justify-between">
                                            <span className="truncate">{character.name}</span>
                                            <span className="text-xs text-muted-foreground font-normal">
                                                {character.role}
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-sm text-muted-foreground line-clamp-2">
                                            {character.personality || '暂无性格描述'}
                                        </p>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                )}

                {/* 关系列表 */}
                {activeTab === 'relations' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {relationsLoading ? (
                            <div className="col-span-4 text-center py-10 text-muted-foreground">
                                加载中...
                            </div>
                        ) : relations.length === 0 ? (
                            <div className="col-span-4 text-center py-10 text-muted-foreground">
                                暂无关系，点击右上角"新增关系"按钮添加
                            </div>
                        ) : (
                            relations.map((relation) => (
                                <Card
                                    key={relation.id}
                                    className={`cursor-pointer transition-all hover:shadow-md ${selectedRelation?.id === relation.id
                                        ? 'ring-2 ring-primary'
                                        : ''
                                        }`}
                                    onClick={() => handleRelationClick(relation)}
                                >
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-sm flex items-center justify-between">
                                            <span className="truncate">
                                                {relation.character_a?.name || '?'} - {relation.character_b?.name || '?'}
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">{relation.relation_type}</span>
                                            <span className="text-xs text-muted-foreground">
                                                信任度: {relation.trust_level}
                                            </span>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* 右侧详情侧边栏 */}
            {(selectedCharacter || selectedRelation) && (
                <div className="w-[400px] border-l bg-background flex flex-col">
                    {/* 侧边栏头部 */}
                    <div className="flex items-center justify-between p-4 border-b">
                        <h2 className="font-semibold">
                            {selectedCharacter ? '人物详情' : '关系详情'}
                        </h2>
                        <Button variant="ghost" size="icon" onClick={handleCloseSidebar}>
                            <X className="h-4 w-4" />
                        </Button>
                    </div>

                    {/* 人物详情 */}
                    {selectedCharacter && (
                        <ScrollArea className="flex-1">
                            <div className="p-4 space-y-4">
                                {isEditing ? (
                                    /* 编辑模式 */
                                    <>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">姓名</Label>
                                            <Input
                                                value={editForm.name || ''}
                                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                                className="mt-1"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">角色</Label>
                                            <select
                                                value={editForm.role || ''}
                                                onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                                                className="mt-1 w-full px-3 py-2 border rounded-md"
                                            >
                                                {ROLE_OPTIONS.map((role) => (
                                                    <option key={role} value={role}>{role}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">性格特点</Label>
                                            <Textarea
                                                value={editForm.personality || ''}
                                                onChange={(e) => setEditForm({ ...editForm, personality: e.target.value })}
                                                className="mt-1"
                                                rows={3}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">口头禅</Label>
                                            <Input
                                                value={editForm.catchphrase || ''}
                                                onChange={(e) => setEditForm({ ...editForm, catchphrase: e.target.value })}
                                                className="mt-1"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">习惯性动作</Label>
                                            <Input
                                                value={editForm.habit_action || ''}
                                                onChange={(e) => setEditForm({ ...editForm, habit_action: e.target.value })}
                                                className="mt-1"
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">内心深处的恐惧</Label>
                                            <Textarea
                                                value={editForm.deep_fear || ''}
                                                onChange={(e) => setEditForm({ ...editForm, deep_fear: e.target.value })}
                                                className="mt-1"
                                                rows={2}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">核心动机</Label>
                                            <Textarea
                                                value={editForm.core_motivation || ''}
                                                onChange={(e) => setEditForm({ ...editForm, core_motivation: e.target.value })}
                                                className="mt-1"
                                                rows={2}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">成长弧光</Label>
                                            <Textarea
                                                value={editForm.growth_arc || ''}
                                                onChange={(e) => setEditForm({ ...editForm, growth_arc: e.target.value })}
                                                className="mt-1"
                                                rows={2}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">外貌描写</Label>
                                            <Textarea
                                                value={editForm.appearance || ''}
                                                onChange={(e) => setEditForm({ ...editForm, appearance: e.target.value })}
                                                className="mt-1"
                                                rows={3}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">背景故事</Label>
                                            <Textarea
                                                value={editForm.backstory || ''}
                                                onChange={(e) => setEditForm({ ...editForm, backstory: e.target.value })}
                                                className="mt-1"
                                                rows={4}
                                            />
                                        </div>
                                        <div>
                                            <Label className="text-sm text-muted-foreground">标志性物品</Label>
                                            <Input
                                                value={editForm.signature_item || ''}
                                                onChange={(e) => setEditForm({ ...editForm, signature_item: e.target.value })}
                                                className="mt-1"
                                            />
                                        </div>
                                        <div className="flex gap-2 pt-4">
                                            <Button variant="outline" onClick={handleCancelEdit} className="flex-1">
                                                取消
                                            </Button>
                                            <Button onClick={handleSaveEdit} disabled={saving} className="flex-1">
                                                {saving ? '保存中...' : '保存'}
                                            </Button>
                                        </div>
                                    </>
                                ) : (
                                    /* 查看模式 */
                                    <>
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-lg font-semibold">{selectedCharacter.name}</h3>
                                            <div className="flex gap-1">
                                                <Button variant="ghost" size="icon" onClick={handleStartEdit}>
                                                    <Pencil className="h-4 w-4" />
                                                </Button>
                                                <Button variant="ghost" size="icon" onClick={handleDeleteCharacter}>
                                                    <Trash2 className="h-4 w-4 text-destructive" />
                                                </Button>
                                            </div>
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            角色: {selectedCharacter.role}
                                        </div>

                                        <div className="pt-2 space-y-3">
                                            {selectedCharacter.personality && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">性格特点</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.personality}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.catchphrase && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">口头禅</Label>
                                                    <p className="text-sm mt-1 italic">"{selectedCharacter.catchphrase}"</p>
                                                </div>
                                            )}
                                            {selectedCharacter.habit_action && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">习惯性动作</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.habit_action}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.deep_fear && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">内心深处的恐惧</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.deep_fear}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.core_motivation && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">核心动机</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.core_motivation}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.growth_arc && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">成长弧光</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.growth_arc}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.appearance && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">外貌描写</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.appearance}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.backstory && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">背景故事</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.backstory}</p>
                                                </div>
                                            )}
                                            {selectedCharacter.signature_item && (
                                                <div>
                                                    <Label className="text-sm text-muted-foreground">标志性物品</Label>
                                                    <p className="text-sm mt-1">{selectedCharacter.signature_item}</p>
                                                </div>
                                            )}
                                        </div>
                                    </>
                                )}
                            </div>
                        </ScrollArea>
                    )}

                    {/* 关系详情 */}
                    {selectedRelation && (
                        <ScrollArea className="flex-1">
                            <div className="p-4 space-y-4">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold">
                                        {selectedRelation.character_a?.name} & {selectedRelation.character_b?.name}
                                    </h3>
                                    <Button variant="ghost" size="icon" onClick={handleDeleteRelation}>
                                        <Trash2 className="h-4 w-4 text-destructive" />
                                    </Button>
                                </div>

                                <div className="space-y-3">
                                    <div>
                                        <Label className="text-sm text-muted-foreground">关系类型</Label>
                                        <p className="text-sm mt-1">{selectedRelation.relation_type}</p>
                                    </div>
                                    <div>
                                        <Label className="text-sm text-muted-foreground">方向</Label>
                                        <p className="text-sm mt-1">{selectedRelation.direction}</p>
                                    </div>
                                    <div>
                                        <Label className="text-sm text-muted-foreground">信任度</Label>
                                        <div className="flex items-center gap-2 mt-1">
                                            <div className="flex-1 bg-secondary rounded-full h-2">
                                                <div
                                                    className="bg-primary rounded-full h-2"
                                                    style={{ width: `${selectedRelation.trust_level}%` }}
                                                />
                                            </div>
                                            <span className="text-sm">{selectedRelation.trust_level}</span>
                                        </div>
                                    </div>
                                    {selectedRelation.current_status && (
                                        <div>
                                            <Label className="text-sm text-muted-foreground">当前状态</Label>
                                            <p className="text-sm mt-1">{selectedRelation.current_status}</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </ScrollArea>
                    )}
                </div>
            )}

            {/* 新增人物弹窗 */}
            {showAddDialog && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-[400px]">
                        <CardHeader>
                            <CardTitle>新增人物</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div>
                                <Label>姓名 *</Label>
                                <Input
                                    value={newCharacter.name}
                                    onChange={(e) => setNewCharacter({ ...newCharacter, name: e.target.value })}
                                    placeholder="请输入人物姓名"
                                    className="mt-1"
                                />
                            </div>
                            <div>
                                <Label>角色</Label>
                                <select
                                    value={newCharacter.role}
                                    onChange={(e) => setNewCharacter({ ...newCharacter, role: e.target.value })}
                                    className="mt-1 w-full px-3 py-2 border rounded-md"
                                >
                                    {ROLE_OPTIONS.map((role) => (
                                        <option key={role} value={role}>{role}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <Label>性格特点</Label>
                                <Textarea
                                    value={newCharacter.personality || ''}
                                    onChange={(e) => setNewCharacter({ ...newCharacter, personality: e.target.value })}
                                    placeholder="描述人物的性格特点"
                                    className="mt-1"
                                    rows={3}
                                />
                            </div>
                            <div className="flex gap-2 pt-2">
                                <Button variant="outline" onClick={() => setShowAddDialog(false)} className="flex-1">
                                    取消
                                </Button>
                                <Button onClick={handleCreateCharacter} disabled={saving} className="flex-1">
                                    {saving ? '创建中...' : '创建'}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* 新增关系弹窗 */}
            {showAddRelationDialog && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <Card className="w-[400px]">
                        <CardHeader>
                            <CardTitle>新增关系</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div>
                                <Label>人物 A</Label>
                                <select
                                    value={newRelation.character_a_id}
                                    onChange={(e) => setNewRelation({ ...newRelation, character_a_id: parseInt(e.target.value) })}
                                    className="mt-1 w-full px-3 py-2 border rounded-md"
                                >
                                    <option value={0}>请选择人物</option>
                                    {characters.map((c) => (
                                        <option key={c.id} value={c.id}>{c.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <Label>人物 B</Label>
                                <select
                                    value={newRelation.character_b_id}
                                    onChange={(e) => setNewRelation({ ...newRelation, character_b_id: parseInt(e.target.value) })}
                                    className="mt-1 w-full px-3 py-2 border rounded-md"
                                >
                                    <option value={0}>请选择人物</option>
                                    {characters.map((c) => (
                                        <option key={c.id} value={c.id}>{c.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <Label>关系类型</Label>
                                <select
                                    value={newRelation.relation_type}
                                    onChange={(e) => setNewRelation({ ...newRelation, relation_type: e.target.value })}
                                    className="mt-1 w-full px-3 py-2 border rounded-md"
                                >
                                    {RELATION_TYPES.map((type) => (
                                        <option key={type} value={type}>{type}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <Label>方向</Label>
                                <select
                                    value={newRelation.direction}
                                    onChange={(e) => setNewRelation({ ...newRelation, direction: e.target.value })}
                                    className="mt-1 w-full px-3 py-2 border rounded-md"
                                >
                                    {DIRECTION_OPTIONS.map((dir) => (
                                        <option key={dir} value={dir}>{dir}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <Label>信任度 (0-100)</Label>
                                <Input
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={newRelation.trust_level}
                                    onChange={(e) => setNewRelation({ ...newRelation, trust_level: parseInt(e.target.value) || 50 })}
                                    className="mt-1"
                                />
                            </div>
                            <div className="flex gap-2 pt-2">
                                <Button variant="outline" onClick={() => setShowAddRelationDialog(false)} className="flex-1">
                                    取消
                                </Button>
                                <Button onClick={handleCreateRelation} disabled={saving} className="flex-1">
                                    {saving ? '创建中...' : '创建'}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    )
}
