// frontend/src/pages/CharacterSetting.tsx
import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Plus, Users, Heart, X, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Label } from '@/components/ui/label'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { projectsApi } from '@/lib/api'
import { useCharacters } from '@/components/character/hooks/useCharacters'
import CharacterList from '@/components/character/CharacterList'
import CharacterDetail from '@/components/character/CharacterDetail'
import CharacterFormDialog from '@/components/character/CharacterFormDialog'
import RelationList from '@/components/character/RelationList'
import RelationFormDialog from '@/components/character/RelationFormDialog'
import type { Character, CharacterCreate, RelationWithCharacters, RelationCreate } from '@/types'
import type { Project } from '@/types'

// 标签页类型
type TabType = 'characters' | 'relations'

export default function CharacterSetting()
{
    const { id } = useParams<{ id: string }>()
    const projectId = id ? parseInt(id) : null

    // 项目状态
    const [project, setProject] = useState<Project | null>(null)
    const [loading, setLoading] = useState(true)

    // 标签页状态
    const [activeTab, setActiveTab] = useState<TabType>('characters')

    // 数据钩子
    const {
        characters,
        charactersLoading,
        relations,
        relationsLoading,
        saving,
        createCharacter,
        updateCharacter,
        deleteCharacter,
        createRelation,
        deleteRelation,
    } = useCharacters(projectId, activeTab)

    // 选中状态
    const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)
    const [selectedRelation, setSelectedRelation] = useState<RelationWithCharacters | null>(null)

    // 人物编辑状态
    const [isEditing, setIsEditing] = useState(false)
    const [editForm, setEditForm] = useState<Partial<Character>>({})

    // 弹窗状态
    const [showAddDialog, setShowAddDialog] = useState(false)
    const [showAddRelationDialog, setShowAddRelationDialog] = useState(false)

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
        if (!selectedCharacter) return
        const updated = await updateCharacter(selectedCharacter.id, editForm)
        if (updated)
        {
            setSelectedCharacter(updated)
            setIsEditing(false)
            setEditForm({})
        }
    }

    // 删除人物
    const handleDeleteCharacter = async () =>
    {
        if (!selectedCharacter) return
        if (!confirm(`确定要删除人物 "${selectedCharacter.name}" 吗？`)) return
        const ok = await deleteCharacter(selectedCharacter.id)
        if (ok) setSelectedCharacter(null)
    }

    // 创建新人物
    const handleCreateCharacter = async (data: CharacterCreate) =>
    {
        if (!data.name.trim())
        {
            toast.error('请输入人物名称')
            return
        }
        const created = await createCharacter(data)
        if (created) setShowAddDialog(false)
    }

    // 创建新关系
    const handleCreateRelation = async (data: RelationCreate) =>
    {
        if (!data.character_a_id || !data.character_b_id)
        {
            toast.error('请选择两个人物')
            return
        }
        if (data.character_a_id === data.character_b_id)
        {
            toast.error('不能选择相同的人物')
            return
        }
        const ok = await createRelation(data)
        if (ok) setShowAddRelationDialog(false)
    }

    // 删除关系
    const handleDeleteRelation = async () =>
    {
        if (!selectedRelation) return
        if (!confirm('确定要删除这个关系吗？')) return
        const ok = await deleteRelation(selectedRelation.id)
        if (ok) setSelectedRelation(null)
    }

    if (loading)
    {
        return <LoadingSpinner fullPage text="加载中..." />
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
                        <CharacterList
                            characters={characters}
                            loading={charactersLoading}
                            selectedCharacterId={selectedCharacter?.id ?? null}
                            onSelectCharacter={handleCharacterClick}
                        />
                    </div>
                )}

                {/* 关系列表 */}
                {activeTab === 'relations' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <RelationList
                            relations={relations}
                            loading={relationsLoading}
                            selectedRelationId={selectedRelation?.id ?? null}
                            onSelectRelation={handleRelationClick}
                        />
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
                        <CharacterDetail
                            character={selectedCharacter}
                            isEditing={isEditing}
                            editForm={editForm}
                            saving={saving}
                            onStartEdit={handleStartEdit}
                            onCancelEdit={handleCancelEdit}
                            onSaveEdit={handleSaveEdit}
                            onDeleteCharacter={handleDeleteCharacter}
                            onEditFormChange={setEditForm}
                        />
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
            <CharacterFormDialog
                open={showAddDialog}
                saving={saving}
                onClose={() => setShowAddDialog(false)}
                onSubmit={handleCreateCharacter}
            />

            {/* 新增关系弹窗 */}
            <RelationFormDialog
                open={showAddRelationDialog}
                saving={saving}
                characters={characters}
                onClose={() => setShowAddRelationDialog(false)}
                onSubmit={handleCreateRelation}
            />
        </div>
    )
}
