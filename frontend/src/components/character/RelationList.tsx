import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { RelationWithCharacters } from '@/types'

interface RelationListProps
{
    relations: RelationWithCharacters[]
    loading: boolean
    selectedRelationId: number | null
    onSelectRelation: (relation: RelationWithCharacters) => void
}

export default function RelationList({
    relations,
    loading,
    selectedRelationId,
    onSelectRelation,
}: RelationListProps)
{
    if (loading)
    {
        return (
            <div className="col-span-4 flex justify-center py-10">
                <LoadingSpinner text="加载中..." />
            </div>
        )
    }

    if (relations.length === 0)
    {
        return (
            <div className="col-span-4 text-center py-10 text-muted-foreground">
                暂无关系，点击右上角"新增关系"按钮添加
            </div>
        )
    }

    return (
        <>
            {relations.map((relation) => (
                <Card
                    key={relation.id}
                    className={`cursor-pointer transition-all hover:shadow-md ${selectedRelationId === relation.id
                        ? 'ring-2 ring-primary'
                        : ''
                        }`}
                    onClick={() => onSelectRelation(relation)}
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
            ))}
        </>
    )
}
