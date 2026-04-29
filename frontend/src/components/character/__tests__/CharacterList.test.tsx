/**
 * CharacterList 组件测试
 * 测试人物列表的加载、空状态、渲染和交互
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import CharacterList from '../CharacterList'
import type { Character } from '@/types'

// 模拟人物数据
const mockCharacters: Character[] = [
  {
    id: 1,
    project_id: 1,
    name: '李明',
    role: '主角',
    personality: '勇敢正义',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
  {
    id: 2,
    project_id: 1,
    name: '王芳',
    role: '重要配角',
    personality: '聪明机智',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
]

describe('CharacterList', () => {
  it('加载中显示 LoadingSpinner', () => {
    render(
      <CharacterList
        characters={[]}
        loading={true}
        selectedCharacterId={null}
        onSelectCharacter={vi.fn()}
      />
    )
    expect(screen.getByText('加载中...')).toBeInTheDocument()
  })

  it('无人物时显示空状态提示', () => {
    render(
      <CharacterList
        characters={[]}
        loading={false}
        selectedCharacterId={null}
        onSelectCharacter={vi.fn()}
      />
    )
    expect(screen.getByText(/暂无人物/)).toBeInTheDocument()
  })

  it('渲染人物卡片并响应点击事件', () => {
    const onSelectCharacter = vi.fn()
    render(
      <CharacterList
        characters={mockCharacters}
        loading={false}
        selectedCharacterId={null}
        onSelectCharacter={onSelectCharacter}
      />
    )

    // 验证人物名称和角色显示
    expect(screen.getByText('李明')).toBeInTheDocument()
    expect(screen.getByText('主角')).toBeInTheDocument()
    expect(screen.getByText('王芳')).toBeInTheDocument()
    expect(screen.getByText('聪明机智')).toBeInTheDocument()

    // 点击第一张卡片
    fireEvent.click(screen.getByText('李明'))
    expect(onSelectCharacter).toHaveBeenCalledTimes(1)
    expect(onSelectCharacter).toHaveBeenCalledWith(mockCharacters[0])
  })
})
