// frontend/src/pages/ProjectWorkbench.tsx

import { useParams } from 'react-router-dom'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { WorkbenchLayout } from '@/components/workbench/WorkbenchLayout'
import { InspirationPanel } from '@/components/workbench/planning/InspirationPanel'
import { CharacterPanel } from '@/components/workbench/planning/CharacterPanel'
import { RelationPanel } from '@/components/workbench/planning/RelationPanel'
import { OutlinePanel } from '@/components/workbench/creation/OutlinePanel'
import { ChapterOutlinePanel } from '@/components/workbench/creation/ChapterOutlinePanel'
import { WritingPanel } from '@/components/workbench/creation/WritingPanel'
import { useProjectData } from '@/hooks/useProjectData'

export default function ProjectWorkbench()
{
  const { id } = useParams<{ id: string }>()
  const projectId = id ? parseInt(id) : null
  const { activeTab, activeMenuItem } = useWorkbenchStore()
  const { project, loading } = useProjectData(projectId)

  if (loading || !project)
  {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  // 渲染当前 Tab/菜单对应的面板
  const renderContent = () =>
  {
    switch (activeTab)
    {
      // 章节大纲和章节正文是独立 Tab，直接渲染面板
      case 'chapter_outlines':
        return <ChapterOutlinePanel projectId={projectId!} />
      case 'writing':
        return <WritingPanel projectId={projectId!} />

      // 规划 Tab 按侧边栏菜单项渲染
      case 'planning':
        switch (activeMenuItem)
        {
          case 'inspiration':
            return <InspirationPanel projectId={projectId!} />
          case 'outline':
            return <OutlinePanel projectId={projectId!} />
          case 'characters':
            return <CharacterPanel projectId={projectId!} />
          case 'relations':
            return <RelationPanel projectId={projectId!} />
          default:
            return null
        }

      default:
        return null
    }
  }

  return (
    <WorkbenchLayout
      projectName={project.name}
      progress={project.progress_percentage || 0}
    >
      {renderContent()}
    </WorkbenchLayout>
  )
}
