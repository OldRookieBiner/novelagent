// CharactersListView.tsx — 角色设定标签页

import type { Character } from '@/types/character'
import { cn } from '@/lib/utils'

interface CharactersListViewProps
{
    data: Character[]
    loading: boolean
}

const roleConfig: Record<string, { label: string; color: string; bg: string }> = {
    '主角': { label: '主角', color: 'text-red-600', bg: 'bg-red-50' },
    '核心反派': { label: '反派', color: 'text-purple-600', bg: 'bg-purple-50' },
    '重要配角': { label: '重要', color: 'text-blue-600', bg: 'bg-blue-50' },
    '配角': { label: '配角', color: 'text-gray-600', bg: 'bg-gray-50' },
}

export function CharactersListView({ data, loading }: CharactersListViewProps)
{
    if (loading) return <LoadingSkeleton />
    if (!data?.length) return <EmptyState label="角色将在创意孵化阶段生成" />

    // 按角色类型分组
    const grouped = data.reduce<Record<string, Character[]>>((acc, char) =>
    {
        const role = char.role || '配角'
        if (!acc[role]) acc[role] = []
        acc[role].push(char)
        return acc
    }, {})

    return (
        <div className="space-y-4">
            <h3 className="text-sm font-semibold">角色设定</h3>
            {Object.entries(grouped).map(([role, chars]) =>
            {
                const config = roleConfig[role] || roleConfig['配角']
                return (
                    <div key={role}>
                        <div className="text-[10px] text-muted-foreground mb-2 flex items-center gap-2">
                            <span className={cn('px-1.5 py-0.5 rounded', config.bg, config.color)}>{config.label}</span>
                            <span>{chars.length}人</span>
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                            {chars.map((char) => (
                                <div key={char.id} className="border rounded-lg p-3 space-y-1.5">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium">{char.name}</span>
                                    </div>
                                    {char.personality && (
                                        <div className="text-xs text-muted-foreground">
                                            <span className="font-medium">性格：</span>{char.personality}
                                        </div>
                                    )}
                                    {char.core_motivation && (
                                        <div className="text-xs text-muted-foreground">
                                            <span className="font-medium">动机：</span>{char.core_motivation}
                                        </div>
                                    )}
                                    {char.growth_arc && (
                                        <div className="text-xs text-muted-foreground">
                                            <span className="font-medium">成长：</span>{char.growth_arc}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

function EmptyState({ label }: { label: string })
{
    return (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-xs">
            <p>{label}</p>
        </div>
    )
}

function LoadingSkeleton()
{
    return (
        <div className="space-y-3">
            <div className="h-5 w-24 bg-muted rounded animate-pulse" />
            <div className="h-20 w-full bg-muted rounded animate-pulse" />
            <div className="h-20 w-full bg-muted rounded animate-pulse" />
        </div>
    )
}
