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
  Arc,
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

  // ========== 章节大纲生成状态 ==========
  chapterOutlineGenerating: boolean
  chapterOutlineReplaning: boolean
  chapterOutlineProgress: {
    current: number
    total: number
    currentTitle?: string
    completed?: string[]
  } | null
  chapterOutlineAbortController: AbortController | null

  // ========== 弧纲生成状态 ==========
  arcs: Arc[]
  arcOutlineGenerating: boolean
  arcOutlineStreamingContent: string
  arcOutlineStreamingArcIndex: number | null

  // ========== 按弧章节大纲生成状态 ==========
  arcChapterGenerating: boolean
  arcChapterStreamingContent: string
  arcChapterStreamingChapterNumber: number | null
  arcChapterProgress: {
    arcIndex: number
    currentChapter: number
    totalInArc: number
  } | null

  // ========== 章节正文生成状态 ==========
  writingChapterGenerating: boolean
  writingGeneratingChapterId: number | null

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

  // 章节大纲生成
  setChapterOutlineGenerating: (generating: boolean) => void
  setChapterOutlineReplaning: (replaning: boolean) => void
  setChapterOutlineProgress: (progress: {
    current: number
    total: number
    currentTitle?: string
    completed?: string[]
  } | null) => void
  setChapterOutlineAbortController: (controller: AbortController | null) => void
  cancelChapterOutlineGeneration: () => void
  clearChapterOutlineGenerationState: () => void

  // 弧纲
  setArcs: (arcs: Arc[]) => void
  updateArc: (arcId: number, updates: Partial<Arc>) => void
  setArcOutlineGenerating: (generating: boolean) => void
  setArcOutlineStreamingContent: (content: string) => void
  appendArcOutlineChunk: (chunk: string) => void
  setArcOutlineStreamingArcIndex: (index: number | null) => void
  clearArcOutlineState: () => void

  // 按弧章节大纲
  setArcChapterGenerating: (generating: boolean) => void
  setArcChapterStreamingContent: (content: string) => void
  appendArcChapterChunk: (chunk: string) => void
  setArcChapterStreamingChapterNumber: (num: number | null) => void
  setArcChapterProgress: (progress: {
    arcIndex: number
    currentChapter: number
    totalInArc: number
  } | null) => void
  clearArcChapterState: () => void

  // 写作
  addWrittenChapter: (chapter: WrittenChapter) => void
  setCurrentChapter: (chapter: number) => void

  // 章节正文生成
  setWritingChapterGenerating: (generating: boolean) => void
  setWritingGeneratingChapterId: (id: number | null) => void
  clearWritingGenerationState: () => void

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
  chapterOutlineGenerating: false,
  chapterOutlineReplaning: false,
  chapterOutlineProgress: null,
  chapterOutlineAbortController: null,
  arcs: [],
  arcOutlineGenerating: false,
  arcOutlineStreamingContent: '',
  arcOutlineStreamingArcIndex: null,
  arcChapterGenerating: false,
  arcChapterStreamingContent: '',
  arcChapterStreamingChapterNumber: null,
  arcChapterProgress: null,
  writingChapterGenerating: false,
  writingGeneratingChapterId: null,
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

  // ========== 章节大纲生成 Actions ==========

  setChapterOutlineGenerating: (generating) => set({ chapterOutlineGenerating: generating }),

  setChapterOutlineReplaning: (replaning) => set({ chapterOutlineReplaning: replaning }),

  setChapterOutlineProgress: (progress) => set({ chapterOutlineProgress: progress }),

  setChapterOutlineAbortController: (controller) => set({ chapterOutlineAbortController: controller }),

  // 取消章节大纲生成（用户主动取消时调用）
  cancelChapterOutlineGeneration: () =>
  {
    const state = useWorkflowStore.getState()
    if (state.chapterOutlineAbortController)
    {
      state.chapterOutlineAbortController.abort()
    }
    set({
      chapterOutlineGenerating: false,
      chapterOutlineReplaning: false,
      chapterOutlineProgress: null,
      chapterOutlineAbortController: null,
    })
  },

  // 清理章节大纲生成状态（生成完成后调用）
  clearChapterOutlineGenerationState: () => set({
    chapterOutlineGenerating: false,
    chapterOutlineReplaning: false,
    chapterOutlineProgress: null,
    chapterOutlineAbortController: null,
  }),

  // ========== 弧纲 Actions ==========

  setArcs: (arcs) => set({ arcs }),

  updateArc: (arcId, updates) => set((state) => ({
    arcs: state.arcs.map(a =>
      a.id === arcId ? { ...a, ...updates } : a
    )
  })),

  setArcOutlineGenerating: (generating) => set({ arcOutlineGenerating: generating }),

  setArcOutlineStreamingContent: (content) => set({ arcOutlineStreamingContent: content }),

  appendArcOutlineChunk: (chunk) => set((state) => ({
    arcOutlineStreamingContent: state.arcOutlineStreamingContent + chunk
  })),

  setArcOutlineStreamingArcIndex: (index) => set({ arcOutlineStreamingArcIndex: index }),

  clearArcOutlineState: () => set({
    arcOutlineGenerating: false,
    arcOutlineStreamingContent: '',
    arcOutlineStreamingArcIndex: null,
  }),

  // ========== 按弧章节大纲 Actions ==========

  setArcChapterGenerating: (generating) => set({ arcChapterGenerating: generating }),

  setArcChapterStreamingContent: (content) => set({ arcChapterStreamingContent: content }),

  appendArcChapterChunk: (chunk) => set((state) => ({
    arcChapterStreamingContent: state.arcChapterStreamingContent + chunk
  })),

  setArcChapterStreamingChapterNumber: (num) => set({ arcChapterStreamingChapterNumber: num }),

  setArcChapterProgress: (progress) => set({ arcChapterProgress: progress }),

  clearArcChapterState: () => set({
    arcChapterGenerating: false,
    arcChapterStreamingContent: '',
    arcChapterStreamingChapterNumber: null,
    arcChapterProgress: null,
  }),

  // ========== 写作 Actions ==========

  addWrittenChapter: (chapter) => set((state) => {
    const newChapters = [...state.writtenChapters.filter(c => c.chapter_number !== chapter.chapter_number), chapter]
    return {
      writtenChapters: newChapters,
      writtenChaptersCount: newChapters.length
    }
  }),

  setCurrentChapter: (chapter) => set({ currentChapter: chapter }),

  // ========== 章节正文生成 Actions ==========

  setWritingChapterGenerating: (generating) => set({ writingChapterGenerating: generating }),

  setWritingGeneratingChapterId: (id) => set({ writingGeneratingChapterId: id }),

  // 生成完成后清理状态
  clearWritingGenerationState: () => set({
    writingChapterGenerating: false,
    writingGeneratingChapterId: null,
  }),

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

  reset: () =>
  {
    const state = useWorkflowStore.getState()
    if (state.chapterOutlineAbortController)
    {
      state.chapterOutlineAbortController.abort()
    }
    set(initialState)
  },
}))
