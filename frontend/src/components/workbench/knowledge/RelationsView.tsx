// RelationsView.tsx — 关系网络标签页

import { useState } from 'react'
import type { Character, RelationWithCharacters, RelationCreate, RelationUpdate } from '@/types/character'
import { relationApi } from '@/lib/characterApi'
import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import RelationFormDialog from '@/components/character/RelationFormDialog'

// 关系类型配色
const relTypeConfig: Record<string, { color: string; bg: string }> = {
    '信任': { color: 'text-green-700', bg: 'bg-green-50' },
    '敌对': { color: 'text-red-700', bg: 'bg-red-50' },
    '感情': { color: 'text-pink-700', bg: 'bg-pink-50' },
    '合作': { color: 'text-blue-700', bg: 'bg-blue-50' },
    '利用': { color: 'text-amber-700', bg: 'bg-amber-50' },
    '陌生': { color: 'text-gray-600', bg: 'bg-gray-50' },
}

interface RelationsViewProps
{
    relations: RelationWithCharacters[]
    characters: Character[]
    loading: boolean
    projectId: number
}

export function RelationsView({ relations, characters, loading, projectId }: RelationsViewProps)
{
    const [showRelationForm, setShowRelationForm] = useState(false)
    const [savingRelation, setSavingRelation] = useState(false)
    const [editingRelation, setEditingRelation] = useState<RelationWithCharacters | undefined>(undefined)

    if (loading) return <LoadingSkeleton />

    const handleCreateRelation = async (formData: RelationCreate | RelationUpdate) =>
    {
        setSavingRelation(true)
        try
        {
            if (editingRelation)
            {
                await relationApi.update(projectId, editingRelation.id, formData as RelationUpdate)
            }
            else
            {
                await relationApi.create(projectId, formData as RelationCreate)
            }
            setShowRelationForm(false)
            setEditingRelation(undefined)
            useWorkbenchStore.getState().incrementKnowledgeVersion()
        }
        catch (err)
        {
            console.error('Failed to save relation:', err)
        }
        finally
        {
            setSavingRelation(false)
        }
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">
                    人物关系
                    {relations.length > 0 && (
                        <span className="text-muted-foreground font-normal ml-1">({relations.length})</span>
                    )}
                </h3>
                {characters.length >= 2 && (
                    <button
                        onClick={() => setShowRelationForm(true)}
                        className="text-[10px] text-primary hover:underline"
                    >
                        + 新增关系
                    </button>
                )}
            </div>

            {relations.length > 0 ? (
                <div className="grid grid-cols-1 gap-2">
                    {relations.map((rel) =>
                    {
                        const tc = relTypeConfig[rel.relation_type] || relTypeConfig['陌生']
                        const nameA = rel.character_a?.name || `角色${rel.character_a_id}`
                        const nameB = rel.character_b?.name || `角色${rel.character_b_id}`
                        return (
                            <RelationCard
                                key={rel.id}
                                rel={rel}
                                nameA={nameA}
                                nameB={nameB}
                                typeConfig={tc}
                                projectId={projectId}
                                onEdit={() => { setEditingRelation(rel); setShowRelationForm(true) }}
                            />
                        )
                    })}
                </div>
            ) : (
                <div className="text-xs text-muted-foreground text-center py-8">
                    暂无人物关系{characters.length >= 2 ? '，点击上方"新增关系"添加' : '，需要至少2个角色'}
                </div>
            )}

            {showRelationForm && (
                <RelationFormDialog
                    open={showRelationForm}
                    saving={savingRelation}
                    characters={characters}
                    onClose={() => { setShowRelationForm(false); setEditingRelation(undefined) }}
                    onSubmit={handleCreateRelation}
                    relation={editingRelation}
                />
            )}
        </div>
    )
}

// 关系卡片
function RelationCard({
    rel,
    nameA,
    nameB,
    typeConfig,
    projectId,
    onEdit,
}: {
    rel: RelationWithCharacters
    nameA: string
    nameB: string
    typeConfig: { color: string; bg: string }
    projectId: number
    onEdit: () => void
})
{
    const [deleting, setDeleting] = useState(false)

    const handleDelete = async () =>
    {
        if (!confirm('确定删除此关系？')) return
        setDeleting(true)
        try
        {
            await relationApi.delete(projectId, rel.id)
            useWorkbenchStore.getState().incrementKnowledgeVersion()
        }
        catch (err)
        {
            console.error('Failed to delete relation:', err)
        }
        finally
        {
            setDeleting(false)
        }
    }

    return (
        <div className="border rounded-lg p-3 space-y-1.5">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">{nameA}</span>
                    <span className={cn('text-[10px] px-1.5 py-0.5 rounded', typeConfig.bg, typeConfig.color)}>
                        {rel.relation_type}
                    </span>
                    <span className="text-xs font-medium">{nameB}</span>
                    <button onClick={onEdit} className="text-[10px] text-muted-foreground hover:text-foreground ml-1">编辑</button>
                </div>
                <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="text-[10px] text-muted-foreground hover:text-red-500 transition-colors disabled:opacity-50"
                >
                    {deleting ? '删除中...' : '删除'}
                </button>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>信任度: {rel.trust_level}</span>
                {rel.direction && <span>方向: {rel.direction}</span>}
                {rel.current_status && <span>状态: {rel.current_status}</span>}
            </div>
        </div>
    )
}

function LoadingSkeleton()
{
    return (
        <div className="space-y-3">
            <div className="h-5 w-24 bg-muted rounded animate-pulse" />
            <div className="h-16 w-full bg-muted rounded animate-pulse" />
            <div className="h-16 w-full bg-muted rounded animate-pulse" />
        </div>
    )
}
