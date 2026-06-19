// frontend/src/hooks/useProjectData.ts
import { useState, useEffect, useCallback } from 'react'
import { projectsApi, outlineApi, chapterOutlinesApi } from '@/lib/api'
import { useProjectStore } from '@/stores/projectStore'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import type { ProjectDetail, ChapterOutline, Outline } from '@/types'

interface UseProjectDataResult
{
  project: ProjectDetail | null
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  loading: boolean
  setSelectedChapter: (chapter: ChapterOutline | null) => void
  refreshProject: () => Promise<void>
  refreshOutline: () => Promise<void>
  refreshChapterOutlines: () => Promise<void>
}

/**
 * 项目数据获取 Hook
 * 统一管理项目、大纲、章节大纲的获取和更新
 */
export function useProjectData(projectId: number | null): UseProjectDataResult
{
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [outline, setOutline] = useState<Outline | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)

  // Store actions
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)
  const setProjectOutline = useProjectStore((state) => state.setOutline)
  const setProjectChapterOutlines = useProjectStore((state) => state.setChapterOutlines)

  // 刷新项目数据
  const refreshProject = useCallback(async () =>
  {
    if (!projectId) return
    try
    {
      const projectData = await projectsApi.get(projectId)
      setProject(projectData)
      setCurrentProject(projectData)

      // 同步工作流阶段到 workbenchStore
      if (projectData.workflow_state?.stage)
      {
        const { phase, setPhase } = useWorkbenchStore.getState()
        if (projectData.workflow_state.stage !== phase)
        {
          setPhase(projectData.workflow_state.stage as any)
        }
      }
    }
    catch (err)
    {
      console.error('Failed to refresh project:', err)
    }
  }, [projectId, setCurrentProject])

  // 刷新大纲数据
  const refreshOutline = useCallback(async () =>
  {
    if (!projectId) return
    try
    {
      const outlineData = await outlineApi.get(projectId)
      setOutline(outlineData)
      setProjectOutline(outlineData)
    }
    catch (err)
    {
      console.error('Failed to refresh outline:', err)
    }
  }, [projectId, setProjectOutline])

  // 刷新章节大纲数据
  const refreshChapterOutlines = useCallback(async () =>
  {
    if (!projectId) return
    try
    {
      const chaptersData = await chapterOutlinesApi.list(projectId)
      setChapterOutlines(chaptersData)
      setProjectChapterOutlines(chaptersData)
      if (chaptersData.length > 0 && !selectedChapter)
      {
        setSelectedChapter(chaptersData[0])
      }
    }
    catch (err)
    {
      console.error('Failed to refresh chapter outlines:', err)
    }
  }, [projectId, setProjectChapterOutlines, selectedChapter])

  // 初始数据加载
  useEffect(() =>
  {
    const fetchData = async () =>
    {
      if (!projectId) return

      setLoading(true)
      // 独立加载各数据，任一失败不影响其他
      let projectData: ProjectDetail | null = null

      // 加载项目数据（核心，失败则不设 project）
      try
      {
        projectData = await projectsApi.get(projectId)
        setProject(projectData)
        setCurrentProject(projectData)

        // 同步工作流阶段
        if (projectData.workflow_state?.stage)
        {
          useWorkbenchStore.getState().setPhase(projectData.workflow_state.stage as any)
        }
      }
      catch (err)
      {
        console.error('Failed to fetch project:', err)
      }

      // 加载大纲数据（非核心，失败不影响页面渲染）
      try
      {
        const outlineData = await outlineApi.get(projectId)
        setOutline(outlineData)
        setProjectOutline(outlineData)
      }
      catch (err)
      {
        console.error('Failed to fetch outline:', err)
      }

      // 加载章节大纲数据（非核心，失败不影响页面渲染）
      try
      {
        const chaptersData = await chapterOutlinesApi.list(projectId)
        setChapterOutlines(chaptersData)
        setProjectChapterOutlines(chaptersData)
        if (chaptersData.length > 0)
        {
          setSelectedChapter(chaptersData[0])
        }
      }
      catch (err)
      {
        console.error('Failed to fetch chapter outlines:', err)
      }

      setLoading(false)
    }

    fetchData()
  }, [projectId, setCurrentProject, setProjectOutline, setProjectChapterOutlines])

  return {
    project,
    outline,
    chapterOutlines,
    selectedChapter,
    loading,
    setSelectedChapter,
    refreshProject,
    refreshOutline,
    refreshChapterOutlines,
  }
}
