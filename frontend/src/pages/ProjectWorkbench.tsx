// ProjectWorkbench.tsx — 创作智能体工作台页面

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { WorkbenchLayout } from '@/components/workbench/WorkbenchLayout'
import { WritingTab } from '@/components/workbench/creation/WritingTab'
import { KnowledgeTab } from '@/components/workbench/knowledge/KnowledgeTab'
import { StructureTab } from '@/components/workbench/structure/StructureTab'
import { TrackingTab } from '@/components/workbench/tracking/TrackingTab'
import { useProjectData } from '@/hooks/useProjectData'
import { knowledgeApi, projectsApi } from '@/lib/api'
import type { PlotBlockGroup } from '@/components/workbench/WorkbenchLayout'

export default function ProjectWorkbench() {
  const { id } = useParams<{ id: string }>()
  const projectId = id ? parseInt(id) : null
  const { activeTab, setCurrentProjectId, phase, setPhase } = useWorkbenchStore()
  const { project, loading, refreshProject } = useProjectData(projectId)

  // 情节块数据（从知识库 API 加载）
  const [plotBlocks, setPlotBlocks] = useState<PlotBlockGroup[]>([])

  // 进入/切换项目时设置当前项目 ID
  useEffect(() => {
    if (projectId) {
      setCurrentProjectId(projectId)
    }
  }, [projectId, setCurrentProjectId])

  // 同步后端工作流阶段到前端（phase 已在 useProjectData 中同步）
  useEffect(() => {
    if (project?.workflow_state?.stage) {
      const stage = project.workflow_state.stage
      if (stage !== phase) {
        setPhase(stage as any)
      }
    }
  }, [project?.workflow_state?.stage, phase, setPhase])

  // 加载情节块数据
  const loadPlotBlocks = useCallback(async () => {
    if (!projectId) return
    try {
      const blocks = await knowledgeApi.getPlotBlocks(projectId)
      const grouped: PlotBlockGroup[] = blocks.map((block: any) => ({
        title: block.title,
        isActive: false,
        chapters: [],
      }))
      setPlotBlocks(grouped)
    } catch {
      setPlotBlocks([])
    }
  }, [projectId])

  useEffect(() => {
    loadPlotBlocks()
  }, [loadPlotBlocks])

  // 修改项目名
  const handleNameChange = async (newName: string) => {
    if (!projectId) return
    await projectsApi.update(projectId, { name: newName })
    await refreshProject()
  }

  if (loading || !project) {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  // 渲染当前标签页内容
  const renderTabContent = () => {
    switch (activeTab) {
      case 'writing':
        return <WritingTab projectId={projectId!} />
      case 'knowledge':
        return <KnowledgeTab projectId={projectId!} />
      case 'structure':
        return <StructureTab projectId={projectId!} />
      case 'tracking':
        return <TrackingTab projectId={projectId!} />
      default:
        return null
    }
  }

  const showChapterList = false
  return (
    <WorkbenchLayout
      projectName={project.name}
      onNameChange={handleNameChange}
      progress={project.progress_percentage || 0}
      plotBlocks={plotBlocks}
      showChapterList={showChapterList}
    >
      {renderTabContent()}
    </WorkbenchLayout>
  )
}
