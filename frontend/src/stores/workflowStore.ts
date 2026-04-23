/**
 * Workflow Store - LangGraph 工作流状态管理
 * 用于管理小说创作工作流的状态
 */

import { create } from 'zustand'
import type {
  WorkflowStage,
  ConfirmationType,
  Outline,
  ChapterOutline,
  WrittenChapter,
  ReviewResponse,
} from '@/types'

interface WorkflowState {
  // ========== 基础状态 ==========
  projectId: number | null
  stage: WorkflowStage
  totalChapters: number

  // ========== 大纲状态 ==========
  outline: Outline | null
  outlineConfirmed: boolean

  // ========== 章节大纲状态 ==========
  chapterOutlines: ChapterOutline[]
  chapterOutlinesConfirmed: boolean

  // ========== 写作状态 ==========
  writtenChapters: WrittenChapter[]
  currentChapter: number
  writtenChaptersCount: number

  // ========== 审核状态 ==========
  reviewResult: ReviewResponse | null
  rewriteCount: number

  // ========== 工作流运行状态 ==========
  isRunning: boolean
  waitingForConfirmation: boolean
  confirmationType: ConfirmationType | null

  // ========== 流式输出状态 ==========
  currentChunk: string
  currentNode: string | null

  // ========== Actions ==========

  // 基础状态
  setProjectId: (projectId: number | null) => void
  setStage: (stage: WorkflowStage) => void
  setTotalChapters: (total: number) => void

  // 大纲
  setOutline: (outline: Outline | null) => void
  setOutlineConfirmed: (confirmed: boolean) => void

  // 章节大纲
  setChapterOutlines: (outlines: ChapterOutline[]) => void
  addChapterOutline: (outline: Partial<ChapterOutline> & { id: number; chapter_number: number }) => void
  updateChapterOutline: (id: number, updates: Partial<ChapterOutline>) => void
  setChapterOutlinesConfirmed: (confirmed: boolean) => void

  // 写作
  addWrittenChapter: (chapter: WrittenChapter) => void
  setCurrentChapter: (chapter: number) => void

  // 审核
  setReviewResult: (result: ReviewResponse | null) => void
  incrementRewriteCount: () => void
  resetRewriteCount: () => void

  // 工作流运行状态
  setIsRunning: (running: boolean) => void
  setWaitingForConfirmation: (waiting: boolean, type: ConfirmationType | null) => void
  clearWaitingForConfirmation: () => void

  // 流式输出
  appendChunk: (chunk: string) => void
  clearChunk: () => void
  setCurrentNode: (node: string | null) => void

  // 重置
  reset: () => void
}

const initialState = {
  projectId: null,
  stage: 'inspiration' as WorkflowStage,
  totalChapters: 0,
  outline: null,
  outlineConfirmed: false,
  chapterOutlines: [],
  chapterOutlinesConfirmed: false,
  writtenChapters: [],
  currentChapter: 0,
  writtenChaptersCount: 0,
  reviewResult: null,
  rewriteCount: 0,
  isRunning: false,
  waitingForConfirmation: false,
  confirmationType: null,
  currentChunk: '',
  currentNode: null,
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  ...initialState,

  // ========== 基础状态 Actions ==========

  setProjectId: (projectId) => set({ projectId }),

  setStage: (stage) => set({ stage }),

  setTotalChapters: (totalChapters) => set({ totalChapters }),

  // ========== 大纲 Actions ==========

  setOutline: (outline) => set({ outline }),

  setOutlineConfirmed: (confirmed) => set({ outlineConfirmed: confirmed }),

  // ========== 章节大纲 Actions ==========

  setChapterOutlines: (outlines) => set({ chapterOutlines: outlines }),

  // 添加单个章节大纲
  addChapterOutline: (outline) => set((state) => ({
    chapterOutlines: [...state.chapterOutlines.filter(o => o.id !== outline.id), outline as ChapterOutline]
  })),

  // 更新单个章节大纲
  updateChapterOutline: (id, updates) => set((state) => ({
    chapterOutlines: state.chapterOutlines.map(o =>
      o.id === id ? { ...o, ...updates } : o
    )
  })),

  setChapterOutlinesConfirmed: (confirmed) => set({ chapterOutlinesConfirmed: confirmed }),

  // ========== 写作 Actions ==========

  addWrittenChapter: (chapter) => set((state) => {
    const newChapters = [...state.writtenChapters.filter(c => c.chapter_number !== chapter.chapter_number), chapter]
    return {
      writtenChapters: newChapters,
      writtenChaptersCount: newChapters.length
    }
  }),

  setCurrentChapter: (chapter) => set({ currentChapter: chapter }),

  // ========== 审核 Actions ==========

  setReviewResult: (result) => set({ reviewResult: result }),

  incrementRewriteCount: () => set((state) => ({ rewriteCount: state.rewriteCount + 1 })),

  resetRewriteCount: () => set({ rewriteCount: 0 }),

  // ========== 工作流运行状态 Actions ==========

  setIsRunning: (running) => set({ isRunning: running }),

  setWaitingForConfirmation: (waiting, type) => set({
    waitingForConfirmation: waiting,
    confirmationType: type
  }),

  clearWaitingForConfirmation: () => set({
    waitingForConfirmation: false,
    confirmationType: null
  }),

  // ========== 流式输出 Actions ==========

  appendChunk: (chunk) => set((state) => ({
    currentChunk: state.currentChunk + chunk
  })),

  clearChunk: () => set({ currentChunk: '' }),

  setCurrentNode: (node) => set({ currentNode: node }),

  // ========== 重置 ==========

  reset: () => set(initialState),
}))
