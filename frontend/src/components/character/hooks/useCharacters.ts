import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { characterApi, relationApi } from '@/lib/characterApi'
import type { Character, CharacterCreate, RelationWithCharacters, RelationCreate } from '@/types'

type TabType = 'characters' | 'relations'

export function useCharacters(projectId: number | null, activeTab: TabType)
{
    const [characters, setCharacters] = useState<Character[]>([])
    const [charactersLoading, setCharactersLoading] = useState(false)
    const [relations, setRelations] = useState<RelationWithCharacters[]>([])
    const [relationsLoading, setRelationsLoading] = useState(false)
    const [saving, setSaving] = useState(false)

    // 加载人物列表
    const loadCharacters = useCallback(async () =>
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
    }, [projectId])

    // 加载关系列表
    const loadRelations = useCallback(async () =>
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
    }, [projectId])

    // 根据标签页自动加载
    useEffect(() =>
    {
        if (activeTab === 'characters')
        {
            loadCharacters()
        }
    }, [activeTab, loadCharacters])

    useEffect(() =>
    {
        if (activeTab === 'relations')
        {
            loadRelations()
        }
    }, [activeTab, loadRelations])

    // 创建新人物
    const createCharacter = useCallback(async (data: CharacterCreate) =>
    {
        if (!projectId) return
        setSaving(true)
        try
        {
            const created = await characterApi.create(projectId, data)
            setCharacters((prev) => [...prev, created])
            toast.success('创建成功')
            return created
        }
        catch (err)
        {
            console.error('Failed to create character:', err)
            toast.error('创建失败')
            return null
        }
        finally
        {
            setSaving(false)
        }
    }, [projectId])

    // 更新人物
    const updateCharacter = useCallback(async (characterId: number, data: Partial<Character>) =>
    {
        if (!projectId) return null
        setSaving(true)
        try
        {
            const updated = await characterApi.update(projectId, characterId, data)
            setCharacters((prev) =>
                prev.map((c) => (c.id === updated.id ? updated : c))
            )
            toast.success('保存成功')
            return updated
        }
        catch (err)
        {
            console.error('Failed to save character:', err)
            toast.error('保存失败')
            return null
        }
        finally
        {
            setSaving(false)
        }
    }, [projectId])

    // 删除人物
    const deleteCharacter = useCallback(async (characterId: number) =>
    {
        if (!projectId) return false
        try
        {
            await characterApi.delete(projectId, characterId)
            setCharacters((prev) => prev.filter((c) => c.id !== characterId))
            toast.success('删除成功')
            return true
        }
        catch (err)
        {
            console.error('Failed to delete character:', err)
            toast.error('删除失败')
            return false
        }
    }, [projectId])

    // 创建新关系
    const createRelation = useCallback(async (data: RelationCreate) =>
    {
        if (!projectId) return false
        setSaving(true)
        try
        {
            await relationApi.create(projectId, data)
            // 重新加载关系列表以获取人物详情
            const result = await relationApi.list(projectId)
            setRelations(result.relations)
            toast.success('创建成功')
            return true
        }
        catch (err)
        {
            console.error('Failed to create relation:', err)
            toast.error('创建失败')
            return false
        }
        finally
        {
            setSaving(false)
        }
    }, [projectId])

    // 删除关系
    const deleteRelation = useCallback(async (relationId: number) =>
    {
        if (!projectId) return false
        try
        {
            await relationApi.delete(projectId, relationId)
            setRelations((prev) => prev.filter((r) => r.id !== relationId))
            toast.success('删除成功')
            return true
        }
        catch (err)
        {
            console.error('Failed to delete relation:', err)
            toast.error('删除失败')
            return false
        }
    }, [projectId])

    return {
        characters,
        charactersLoading,
        relations,
        relationsLoading,
        saving,
        loadCharacters,
        loadRelations,
        createCharacter,
        updateCharacter,
        deleteCharacter,
        createRelation,
        deleteRelation,
    }
}
