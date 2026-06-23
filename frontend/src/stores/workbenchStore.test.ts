/**
 * workbenchStore 关键状态切换回归测试
 *
 * 当前覆盖：切换 currentProjectId 时必须重置 selectedChapterNumber，
 * 避免上一个项目残留章节号被传给 Agent。
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkbenchStore } from './workbenchStore'

describe('useWorkbenchStore.setCurrentProjectId', () => {
  beforeEach(() => {
    // 重置到初始态
    useWorkbenchStore.setState({
      currentProjectId: null,
      selectedChapterNumber: null,
      aiMessages: [],
      pendingImpacts: [],
      agentWarnings: [],
      knowledgeVersion: 0,
      activeConversationId: null,
    })
  })

  it('切换项目时应重置 selectedChapterNumber 为 null', () => {
    const { setSelectedChapterNumber, setCurrentProjectId } = useWorkbenchStore.getState()
    // 模拟在项目 1 选中第 8 章
    setCurrentProjectId(1)
    setSelectedChapterNumber(8)
    expect(useWorkbenchStore.getState().selectedChapterNumber).toBe(8)

    // 切到项目 2
    setCurrentProjectId(2)
    expect(useWorkbenchStore.getState().currentProjectId).toBe(2)
    expect(useWorkbenchStore.getState().selectedChapterNumber).toBeNull()
  })

  it('切换项目时同步清空 aiMessages / pendingImpacts / activeConversationId', () => {
    const store = useWorkbenchStore.getState()
    store.setCurrentProjectId(1)
    store.addAiMessage({
      id: 'm1',
      role: 'user',
      content: 'hi',
      segments: [],
      timestamp: Date.now(),
    })
    store.setActiveConversationId(42)
    expect(useWorkbenchStore.getState().aiMessages.length).toBe(1)
    expect(useWorkbenchStore.getState().activeConversationId).toBe(42)

    useWorkbenchStore.getState().setCurrentProjectId(2)
    expect(useWorkbenchStore.getState().aiMessages).toEqual([])
    expect(useWorkbenchStore.getState().activeConversationId).toBeNull()
  })
})
