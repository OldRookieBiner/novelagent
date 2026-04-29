import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { Character } from '@/types'

interface CharacterListProps
{
    characters: Character[]
    loading: boolean
    selectedCharacterId: number | null
    onSelectCharacter: (character: Character) => void
}

export default function CharacterList({
    characters,
    loading,
    selectedCharacterId,
    onSelectCharacter,
}: CharacterListProps)
{
    if (loading)
    {
        return (
            <div className="col-span-4 flex justify-center py-10">
                <LoadingSpinner text="加载中..." />
            </div>
        )
    }

    if (characters.length === 0)
    {
        return (
            <div className="col-span-4 text-center py-10 text-muted-foreground">
                暂无人物，点击右上角"新增人物"按钮添加
            </div>
        )
    }

    return (
        <>
            {characters.map((character) => (
                <Card
                    key={character.id}
                    className={`cursor-pointer transition-all hover:shadow-md ${selectedCharacterId === character.id
                        ? 'ring-2 ring-primary'
                        : ''
                        }`}
                    onClick={() => onSelectCharacter(character)}
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
            ))}
        </>
    )
}
