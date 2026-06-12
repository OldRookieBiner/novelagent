// EvolutionView.tsx — 关系演变标签页

import { useState, useEffect, useCallback } from 'react'
import type { RelationWithCharacters, EvolutionPlan, EvolutionRecord, EvolutionPlanCreate } from '@/types/character'
import { evolutionPlanApi, evolutionRecordApi } from '@/lib/characterApi'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { cn } from '@/lib/utils'

interface EvolutionViewProps
{
    relations: RelationWithCharacters[]
    projectId: number
}

export function EvolutionView({ relations, projectId }: EvolutionViewProps)
{
    const [selectedRelationId, setSelectedRelationId] = useState<number | null>(null)
    const [plans, setPlans] = useState<EvolutionPlan[]>([])
    const [records, setRecords] = useState<EvolutionRecord[]>([])
    const [loading, setLoading] = useState(false)

    // 默认选中第一个关系
    useEffect(() =>
    {
        if (relations.length > 0 && selectedRelationId === null)
        {
            setSelectedRelationId(relations[0].id)
        }
    }, [relations, selectedRelationId])

    // 加载演变数据
    const loadEvolutionData = useCallback(async () =>
    {
        if (!selectedRelationId) return
        setLoading(true)
        try
        {
            const [plansRes, recordsRes] = await Promise.allSettled([
                evolutionPlanApi.list(projectId, selectedRelationId),
                evolutionRecordApi.list(projectId, selectedRelationId),
            ])
            if (plansRes.status === 'fulfilled') setPlans(plansRes.value?.plans || [])
            if (recordsRes.status === 'fulfilled') setRecords(recordsRes.value?.records || [])
        }
        catch (err)
        {
            console.error('Failed to load evolution data:', err)
        }
        finally
        {
            setLoading(false)
        }
    }, [projectId, selectedRelationId])

    useEffect(() =>
    {
        loadEvolutionData()
    }, [loadEvolutionData])

    if (relations.length === 0)
    {
        return (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
                <p>需要至少一条人物关系才能查看演变</p>
            </div>
        )
    }

    return (
        <div className="space-y-4">
            {/* 关系选择器 */}
            <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">选择关系：</span>
                {relations.map((rel) =>
                {
                    const nameA = rel.character_a?.name || `角色${rel.character_a_id}`
                    const nameB = rel.character_b?.name || `角色${rel.character_b_id}`
                    const isActive = selectedRelationId === rel.id
                    return (
                        <button
                            key={rel.id}
                            onClick={() => setSelectedRelationId(rel.id)}
                            className={cn(
                                'text-[11px] px-3 py-1 rounded-full border transition-colors',
                                isActive
                                    ? 'bg-primary text-primary-foreground border-primary'
                                    : 'bg-white text-muted-foreground border-border hover:bg-muted/50'
                            )}
                        >
                            {nameA} ↔ {nameB}
                        </button>
                    )
                })}
            </div>

            {loading ? (
                <div className="space-y-3">
                    <div className="h-5 w-32 bg-muted rounded animate-pulse" />
                    <div className="h-24 w-full bg-muted rounded animate-pulse" />
                </div>
            ) : (
                <>
                    {/* 演变规划表格 */}
                    <EvolutionPlansTable
                        plans={plans}
                        projectId={projectId}
                        relationId={selectedRelationId!}
                        onCreated={loadEvolutionData}
                    />

                    {/* 演变记录表格 */}
                    <EvolutionRecordsTable records={records} />
                </>
            )}
        </div>
    )
}

// 演变规划表格
function EvolutionPlansTable({
    plans,
    projectId,
    relationId,
    onCreated,
}: {
    plans: EvolutionPlan[]
    projectId: number
    relationId: number
    onCreated: () => void
})
{
    const [showForm, setShowForm] = useState(false)
    const [saving, setSaving] = useState(false)
    const [form, setForm] = useState<EvolutionPlanCreate>({
        trigger_chapter: 1,
        event_description: '',
        status_after: '',
    })

    const handleCreate = async () =>
    {
        if (!form.event_description || !form.status_after) return
        setSaving(true)
        try
        {
            await evolutionPlanApi.create(projectId, relationId, form)
            setShowForm(false)
            setForm({ trigger_chapter: 1, event_description: '', status_after: '' })
            useWorkbenchStore.getState().incrementKnowledgeVersion()
            onCreated()
        }
        catch (err)
        {
            console.error('Failed to create evolution plan:', err)
        }
        finally
        {
            setSaving(false)
        }
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold">演变规划（未来计划）</h4>
                <button
                    onClick={() => setShowForm(!showForm)}
                    className="text-[10px] text-primary hover:underline"
                >
                    + 新增规划
                </button>
            </div>

            {showForm && (
                <div className="border rounded-lg p-3 mb-3 space-y-2 bg-muted/20">
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-[10px] text-muted-foreground">触发章节</label>
                            <input
                                type="number"
                                min={1}
                                value={form.trigger_chapter}
                                onChange={(e) => setForm({ ...form, trigger_chapter: parseInt(e.target.value) || 1 })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] text-muted-foreground">事件描述</label>
                            <input
                                type="text"
                                value={form.event_description}
                                onChange={(e) => setForm({ ...form, event_description: e.target.value })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                                placeholder="描述触发事件"
                            />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-[10px] text-muted-foreground">变化前状态</label>
                            <input
                                type="text"
                                value={form.status_before || ''}
                                onChange={(e) => setForm({ ...form, status_before: e.target.value || undefined })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                                placeholder="可选"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] text-muted-foreground">变化后状态</label>
                            <input
                                type="text"
                                value={form.status_after}
                                onChange={(e) => setForm({ ...form, status_after: e.target.value })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                                placeholder="必填"
                            />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <div>
                            <label className="text-[10px] text-muted-foreground">变化前信任度</label>
                            <input
                                type="number"
                                min={0}
                                max={100}
                                value={form.trust_before ?? ''}
                                onChange={(e) => setForm({ ...form, trust_before: e.target.value ? parseInt(e.target.value) : undefined })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                                placeholder="0-100"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] text-muted-foreground">变化后信任度</label>
                            <input
                                type="number"
                                min={0}
                                max={100}
                                value={form.trust_after ?? ''}
                                onChange={(e) => setForm({ ...form, trust_after: e.target.value ? parseInt(e.target.value) : undefined })}
                                className="w-full text-xs border rounded px-2 py-1 mt-0.5"
                                placeholder="0-100"
                            />
                        </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                        <button
                            onClick={handleCreate}
                            disabled={saving || !form.event_description || !form.status_after}
                            className="text-xs px-3 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
                        >
                            {saving ? '创建中...' : '创建'}
                        </button>
                        <button
                            onClick={() => setShowForm(false)}
                            className="text-xs px-3 py-1 border rounded hover:bg-muted/50"
                        >
                            取消
                        </button>
                    </div>
                </div>
            )}

            {plans.length === 0 ? (
                <div className="text-xs text-muted-foreground text-center py-6 border rounded-lg">
                    暂无演变规划
                </div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                        <thead className="bg-muted/50">
                            <tr>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">触发章节</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">事件</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">状态变化</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">信任度</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            {plans.map((plan) => (
                                <tr key={plan.id} className="border-t">
                                    <td className="px-3 py-2">第 {plan.trigger_chapter} 章</td>
                                    <td className="px-3 py-2">{plan.event_description}</td>
                                    <td className="px-3 py-2">
                                        {plan.status_before || '—'} → {plan.status_after}
                                    </td>
                                    <td className="px-3 py-2">
                                        <TrustChange
                                            before={plan.trust_before}
                                            after={plan.trust_after}
                                        />
                                    </td>
                                    <td className="px-3 py-2">
                                        <PlanStatusTag isTriggered={plan.is_triggered} />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}

// 演变记录表格
function EvolutionRecordsTable({ records }: { records: EvolutionRecord[] })
{
    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold">
                    演变记录（已发生）
                    {records.length > 0 && (
                        <span className="text-muted-foreground font-normal ml-1">({records.length})</span>
                    )}
                </h4>
            </div>
            {records.length === 0 ? (
                <div className="text-xs text-muted-foreground text-center py-6 border rounded-lg">
                    暂无演变记录，将在写作过程中自动生成
                </div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                        <thead className="bg-muted/50">
                            <tr>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">章节</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">事件</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">状态变化</th>
                                <th className="text-left px-3 py-2 font-medium text-muted-foreground">信任度变化</th>
                            </tr>
                        </thead>
                        <tbody>
                            {records.map((record) => (
                                <tr
                                    key={record.id}
                                    className={cn(
                                        'border-t',
                                        record.trust_change && record.trust_change < 0 ? 'bg-red-50/30' : 'bg-blue-50/30'
                                    )}
                                >
                                    <td className="px-3 py-2 font-medium">第 {record.chapter_number} 章</td>
                                    <td className="px-3 py-2">{record.content}</td>
                                    <td className="px-3 py-2">{record.status_change || '—'}</td>
                                    <td className="px-3 py-2">
                                        {record.trust_change != null ? (
                                            <span className={record.trust_change > 0 ? 'text-green-600' : 'text-red-600'}>
                                                {record.trust_change > 0 ? '+' : ''}{record.trust_change}
                                            </span>
                                        ) : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    )
}

// 信任度变化组件
function TrustChange({ before, after }: { before?: number | null; after?: number | null })
{
    if (before == null || after == null) return <span>—</span>
    const diff = after - before
    return (
        <span className={diff > 0 ? 'text-green-600' : diff < 0 ? 'text-red-600' : ''}>
            {before} → {after} ({diff > 0 ? '+' : ''}{diff})
        </span>
    )
}

// 规划状态标签
function PlanStatusTag({ isTriggered }: { isTriggered: boolean })
{
    if (isTriggered)
    {
        return (
            <span className="text-[10px] bg-green-50 text-green-700 px-1.5 py-0.5 rounded">已触发</span>
        )
    }
    return (
        <span className="text-[10px] bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded">未触发</span>
    )
}
