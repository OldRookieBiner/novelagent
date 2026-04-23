/**
 * workflowStore 测试
 * 测试工作流状态管理
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkflowStore } from '@/stores/workflowStore'

describe('WorkflowStore', () =>
{
  beforeEach(() =>
  {
    // 重置 store 状态
    useWorkflowStore.setState({
      projectId: null,
      stage: 'inspiration',
      outline: null,
      chapterOutlines: [],
      writtenChapters: [],
      currentChapter: 0,
      totalChapters: 0,
      reviewResult: null,
      isRunning: false,
      waitingForConfirmation: false,
      confirmationType: null,
    })
  })

  describe('基础状态管理', () =>
  {
    it('设置项目 ID', () =>
    {
      useWorkflowStore.getState().setProjectId(123)
      expect(useWorkflowStore.getState().projectId).toBe(123)
    })

    it('设置工作流阶段', () =>
    {
      useWorkflowStore.getState().setStage('outline')
      expect(useWorkflowStore.getState().stage).toBe('outline')
    })

    it('设置当前章节', () =>
    {
      useWorkflowStore.getState().setCurrentChapter(5)
      expect(useWorkflowStore.getState().currentChapter).toBe(5)
    })

    it('设置总章节数', () =>
    {
      useWorkflowStore.getState().setTotalChapters(20)
      expect(useWorkflowStore.getState().totalChapters).toBe(20)
    })
  })

  describe('运行状态管理', () =>
  {
    it('设置运行状态', () =>
    {
      useWorkflowStore.getState().setIsRunning(true)
      expect(useWorkflowStore.getState().isRunning).toBe(true)
    })

    it('设置等待确认状态', () =>
    {
      useWorkflowStore.getState().setWaitingForConfirmation(true, 'outline')
      expect(useWorkflowStore.getState().waitingForConfirmation).toBe(true)
      expect(useWorkflowStore.getState().confirmationType).toBe('outline')
    })

    it('清除等待确认状态', () =>
    {
      useWorkflowStore.getState().setWaitingForConfirmation(true, 'chapter_outlines')
      useWorkflowStore.getState().setWaitingForConfirmation(false, null)
      expect(useWorkflowStore.getState().waitingForConfirmation).toBe(false)
      expect(useWorkflowStore.getState().confirmationType).toBeNull()
    })
  })

  describe('章节大纲管理', () =>
  {
    it('添加章节大纲', () =>
    {
      const outline = { id: 1, chapter_number: 1, title: '第一章', confirmed: false }
      useWorkflowStore.getState().addChapterOutline(outline)
      expect(useWorkflowStore.getState().chapterOutlines).toHaveLength(1)
      expect(useWorkflowStore.getState().chapterOutlines[0]).toEqual(outline)
    })

    it('更新章节大纲', () =>
    {
      const outline = { id: 1, chapter_number: 1, title: '第一章', confirmed: false }
      useWorkflowStore.getState().addChapterOutline(outline)
      useWorkflowStore.getState().updateChapterOutline(1, { confirmed: true })
      expect(useWorkflowStore.getState().chapterOutlines[0].confirmed).toBe(true)
    })
  })

  describe('已写章节管理', () =>
  {
    it('添加已写章节', () =>
    {
      const chapter = { chapter_number: 1, content: '内容...', word_count: 1000 }
      useWorkflowStore.getState().addWrittenChapter(chapter)
      expect(useWorkflowStore.getState().writtenChapters).toHaveLength(1)
      expect(useWorkflowStore.getState().writtenChaptersCount).toBe(1)
    })

    it('计算已写章节数', () =>
    {
      useWorkflowStore.getState().addWrittenChapter({ chapter_number: 1, content: '', word_count: 1000 })
      useWorkflowStore.getState().addWrittenChapter({ chapter_number: 2, content: '', word_count: 2000 })
      expect(useWorkflowStore.getState().writtenChaptersCount).toBe(2)
    })
  })

  describe('重置功能', () =>
  {
    it('重置整个工作流状态', () =>
    {
      // 设置一些状态
      useWorkflowStore.getState().setProjectId(123)
      useWorkflowStore.getState().setStage('writing')
      useWorkflowStore.getState().setCurrentChapter(5)
      useWorkflowStore.getState().setIsRunning(true)

      // 重置
      useWorkflowStore.getState().reset()

      // 验证重置后的状态
      expect(useWorkflowStore.getState().projectId).toBeNull()
      expect(useWorkflowStore.getState().stage).toBe('inspiration')
      expect(useWorkflowStore.getState().currentChapter).toBe(0)
      expect(useWorkflowStore.getState().isRunning).toBe(false)
    })
  })
})
