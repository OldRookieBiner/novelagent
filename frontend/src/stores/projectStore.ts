import { create } from 'zustand'
import type { ProjectDetail, Outline, ChapterOutline } from '@/types'

interface ProjectState {
  currentProject: ProjectDetail | null
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  currentChapterNum: number
  setCurrentProject: (project: ProjectDetail | null) => void
  setOutline: (outline: Outline | null) => void
  setChapterOutlines: (outlines: ChapterOutline[]) => void
  setCurrentChapterNum: (num: number) => void
  clear: () => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  outline: null,
  chapterOutlines: [],
  currentChapterNum: 1,
  setCurrentProject: (project) => set({ currentProject: project }),
  setOutline: (outline) => set({ outline }),
  setChapterOutlines: (outlines) => set({ chapterOutlines: outlines }),
  setCurrentChapterNum: (num) => set({ currentChapterNum: num }),
  clear: () => set({
    currentProject: null,
    outline: null,
    chapterOutlines: [],
    currentChapterNum: 1,
  }),
}))