// frontend/src/hooks/useProjectData.ts
import { useState, useEffect, useCallback } from 'react'
import { projectsApi, outlineApi, chapterOutlinesApi, workflowApi } from '@/lib/api'
import { useProjectStore } from '@/stores/projectStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import type { ProjectDetail, ChapterOutline, Outline, WorkflowStateResponse } from '@/types'

interface UseProjectDataResult
{
  project: ProjectDetail | null
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  workflowState: WorkflowStateResponse | null
  loading: boolean
  setSelectedChapter: (chapter: ChapterOutline | null) => void
  refreshProject: () => Promise<void>
  refreshOutline: () => Promise<void>
  refreshChapterOutlines: () => Promise<void>
  refreshWorkflowState: () => Promise<void>
}

/**
 * 项目数据获取 Hook
 * 统一管理项目、大纲、章节大纲、工作流状态的获取和更新
 */
export function useProjectData(projectId: number | null): UseProjectDataResult
{
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [outline, setOutline] = useState<Outline | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [workflowState, setWorkflowState] = useState<WorkflowStateResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Store actions
  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)
  const setProjectOutline = useProjectStore((state) => state.setOutline)
  const setProjectChapterOutlines = useProjectStore((state) => state.setChapterOutlines)
  const setWorkflowStage = useWorkflowStore((state) => state.setStage)
  const setWorkflowProjectId = useWorkflowStore((state) => state.setProjectId)

  // 刷新项目数据
  const refreshProject = useCallback(async () =>
  {
    if (!projectId) return
    try
    {
      const projectData = await projectsApi.get(projectId)
      setProject(projectData)
      setCurrentProject(projectData)
    } catch (err)
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
    } catch (err)
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
    } catch (err)
    {
      console.error('Failed to refresh chapter outlines:', err)
    }
  }, [projectId, setProjectChapterOutlines, selectedChapter])

  // 刷新工作流状态
  const refreshWorkflowState = useCallback(async () =>
  {
    if (!projectId) return
    try
    {
      const state = await workflowApi.getWorkflowState(projectId)
      setWorkflowState(state)
      setWorkflowProjectId(projectId)
      setWorkflowStage(state.stage)
    } catch (err)
    {
      console.error('Failed to refresh workflow state:', err)
    }
  }, [projectId, setWorkflowProjectId, setWorkflowStage])

  // 初始数据加载
  useEffect(() =>
  {
    const fetchData = async () =>
    {
      if (!projectId) return

      setLoading(true)
      try
      {
        // 并行获取项目和大纲
        const [projectData, outlineData] = await Promise.all([
          projectsApi.get(projectId),
          outlineApi.get(projectId),
        ])
        setProject(projectData)
        setCurrentProject(projectData)
        setOutline(outlineData)
        setProjectOutline(outlineData)

        // 获取章节大纲
        const chaptersData = await chapterOutlinesApi.list(projectId)
        setChapterOutlines(chaptersData)
        setProjectChapterOutlines(chaptersData)
        if (chaptersData.length > 0)
        {
          setSelectedChapter(chaptersData[0])
        }
      } catch (err)
      {
        console.error('Failed to fetch project:', err)
      } finally
      {
        setLoading(false)
      }
    }

    fetchData()
  }, [projectId, setCurrentProject, setProjectOutline, setProjectChapterOutlines])

  // 获取工作流状态
  useEffect(() =>
  {
    refreshWorkflowState()
  }, [refreshWorkflowState])

  return {
    project,
    outline,
    chapterOutlines,
    selectedChapter,
    workflowState,
    loading,
    setSelectedChapter,
    refreshProject,
    refreshOutline,
    refreshChapterOutlines,
    refreshWorkflowState,
  }
}
