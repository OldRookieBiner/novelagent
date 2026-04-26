// frontend/src/pages/ProjectDetail.tsx
import { useState, useEffect } from 'react'
import { useParams, Link, useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProjectDetailSkeleton } from '@/components/ui/skeleton'
import { outlineApi, chapterOutlinesApi, workflowApi } from '@/lib/api'
import { useProjectData } from '@/hooks/useProjectData'
import { useWorkflowStore } from '@/stores/workflowStore'
import OutlineWorkflow from '@/components/project/OutlineWorkflow'
import StepNavigation, { HistoryBanner, STEPS } from '@/components/project/StepNavigation'
import InspirationForm from '@/components/project/InspirationForm'
import InspirationEditor from '@/components/project/InspirationEditor'
import ResumeDialog from '@/components/project/ResumeDialog'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import ChapterList from '@/components/project/ChapterList'
import ChapterOutlineDetail from '@/components/project/ChapterOutlineDetail'
import HistoryContent from '@/components/project/HistoryContent'
import { generateInspirationTemplate, type InspirationData } from '@/lib/inspiration'
import type { CollectedInfo } from '@/types'

const STAGE_LABELS: Record<string, string> = {
  inspiration: '灵感采集',
  outline: '大纲生成',
  chapter_outlines: '章节大纲',
  writing: '写作中',
  review: '审核中',
  complete: '已完成',
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectId = id ? parseInt(id) : null

  // 使用统一的 Hook 获取数据
  const {
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
  } = useProjectData(projectId)

  // 视图状态
  const [viewingStep, setViewingStep] = useState<number | null>(() => {
    const viewStepParam = searchParams.get('viewStep')
    return viewStepParam ? parseInt(viewStepParam) : null
  })

  // 灵感采集状态
  const [inspirationData, setInspirationData] = useState<InspirationData | null>(null)
  const [inspirationTemplate, setInspirationTemplate] = useState('')
  const [showInspirationEditor, setShowInspirationEditor] = useState(false)
  const [selectedModelId, setSelectedModelId] = useState<number | undefined>()

  // 返回确认弹窗状态
  const [isGenerating, setIsGenerating] = useState(false)
  const [showReturnConfirm, setShowReturnConfirm] = useState(false)
  const [showResumeDialog, setShowResumeDialog] = useState(false)

  // 工作流 store
  const setWorkflowStage = useWorkflowStore((state) => state.setStage)
  const setWorkflowProjectId = useWorkflowStore((state) => state.setProjectId)

  // 恢复弹窗逻辑
  useEffect(() => {
    if (workflowState?.has_checkpoint && workflowState.stage !== 'complete') {
      setShowResumeDialog(true)
    }
  }, [workflowState])

  // 灵感数据回显
  useEffect(() => {
    if (outline?.collected_info && !inspirationData) {
      const info = outline.collected_info as unknown as InspirationData
      if (info.novelType) {
        setInspirationData(info)
      }
    }
    if (outline?.inspiration_template && !inspirationTemplate) {
      setInspirationTemplate(outline.inspiration_template)
    }
  }, [outline, inspirationData, inspirationTemplate])

  // 阶段变更处理
  const handleStageChange = async (stage: string, skipRefresh = false) => {
    if (!project) return
    try {
      if (!skipRefresh) {
        await workflowApi.updateStage(project.id, stage)
      }
      await refreshProject()

      if (!skipRefresh) {
        await refreshOutline()
      }

      if (stage === 'chapter_outlines' || stage === 'writing') {
        await refreshChapterOutlines()
      }
    } catch (err) {
      console.error('Failed to update stage:', err)
    }
  }

  const handleOutlineUpdate = (updatedOutline: typeof outline) => {
    if (updatedOutline) {
      refreshOutline()
    }
  }

  const handleConfirmChapterOutline = async (chapterNum: number) => {
    if (!projectId) return
    try {
      await chapterOutlinesApi.confirm(projectId, chapterNum)
      await refreshChapterOutlines()

      // 检查是否全部确认
      const updatedChapters = await chapterOutlinesApi.list(projectId)
      const allConfirmed = updatedChapters.every(c => c.confirmed)
      if (allConfirmed && project && project.workflow_state?.stage !== 'writing') {
        await workflowApi.updateStage(project.id, 'writing')
        await refreshProject()
      }
    } catch (err) {
      console.error('Failed to confirm chapter outline:', err)
      toast.error('确认章节大纲失败')
    }
  }

  // 步骤导航
  const handleViewStep = (stepIndex: number | null) => {
    setViewingStep(stepIndex)
    if (stepIndex !== null) {
      setSearchParams({ viewStep: stepIndex.toString() })
    } else {
      setSearchParams({})
    }
  }

  const handleReturnToCurrent = () => {
    setViewingStep(null)
  }

  // 灵感采集处理
  const handleInspirationSubmit = (data: InspirationData, modelId?: number) => {
    setInspirationData(data)
    setInspirationTemplate(generateInspirationTemplate(data))
    setSelectedModelId(modelId)
    setShowInspirationEditor(true)
  }

  const handleInspirationConfirm = async () => {
    if (!inspirationData || !project) return

    try {
      await outlineApi.update(project.id, {
        collected_info: inspirationData as unknown as CollectedInfo,
        inspiration_template: inspirationTemplate,
      })
      await workflowApi.updateStage(project.id, 'outline')
      await refreshProject()
      await refreshOutline()
      setShowInspirationEditor(false)
    } catch (err) {
      console.error('Failed to confirm inspiration:', err)
    }
  }

  const handleInspirationUpdate = async (data: InspirationData) => {
    if (!project) return

    try {
      await outlineApi.update(project.id, {
        collected_info: data as unknown as CollectedInfo,
        inspiration_template: generateInspirationTemplate(data),
        title: '',
        summary: '',
        plot_points: [],
      })
      await workflowApi.updateStage(project.id, 'outline')
      await refreshProject()
      await refreshOutline()
      setViewingStep(null)
      setSearchParams({})
    } catch (err) {
      console.error('Failed to update inspiration:', err)
    }
  }

  if (loading) {
    return <ProjectDetailSkeleton />
  }

  if (!project) {
    return <div className="text-center py-10">项目不存在</div>
  }

  // 决定显示哪个工作流
  const currentStage = project.workflow_state?.stage || ''
  const showInspirationCollection = currentStage === 'inspiration'
  const showOutlineWorkflow = currentStage === 'outline' ||
    (currentStage === 'chapter_outlines' && chapterOutlines.length === 0)
  const showChapterList = ['writing', 'review', 'complete'].includes(currentStage) ||
    (currentStage === 'chapter_outlines' && chapterOutlines.length > 0)

  return (
    <div>
      {/* 项目头部 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <Button
            onClick={() => {
              if (isGenerating) {
                setShowReturnConfirm(true)
              } else {
                navigate('/')
              }
            }}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回列表
          </Button>
        </div>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <span>创建时间: {new Date(project.created_at).toLocaleDateString()}</span>
          <span>阶段: {STAGE_LABELS[currentStage] || currentStage}</span>
          <span>字数: {project.total_words.toLocaleString()}</span>
        </div>
      </div>

      {/* 步骤导航 */}
      <StepNavigation
        currentStage={currentStage}
        viewingStep={viewingStep}
        onViewStep={handleViewStep}
        outlineConfirmed={outline?.confirmed}
      />

      {/* 历史横幅 */}
      {viewingStep !== null && (
        <HistoryBanner
          stepName={STEPS[viewingStep].name}
          onReturn={handleReturnToCurrent}
        />
      )}

      {/* 主内容区 */}
      <div className="flex gap-6 mt-4">
        {viewingStep !== null ? (
          <HistoryContent
            stepIndex={viewingStep}
            outline={outline}
            chapterOutlines={chapterOutlines}
            selectedChapter={selectedChapter}
            projectId={project.id}
            onSelectChapter={setSelectedChapter}
            onConfirmChapter={handleConfirmChapterOutline}
            onInspirationUpdate={handleInspirationUpdate}
          />
        ) : (
          <>
            {/* 灵感采集阶段 */}
            {showInspirationCollection && !showInspirationEditor && (
              <Card className="flex-1">
                <CardHeader>
                  <CardTitle>灵感采集</CardTitle>
                </CardHeader>
                <CardContent>
                  <InspirationForm
                    initialData={outline?.collected_info as Partial<InspirationData>}
                    onSubmit={handleInspirationSubmit}
                  />
                </CardContent>
              </Card>
            )}

            {showInspirationCollection && showInspirationEditor && inspirationData && (
              <Card className="flex-1">
                <CardHeader>
                  <CardTitle>灵感模板</CardTitle>
                </CardHeader>
                <CardContent>
                  <InspirationEditor
                    data={inspirationData}
                    template={inspirationTemplate}
                    onDataChange={setInspirationData}
                    onTemplateChange={setInspirationTemplate}
                    onConfirm={handleInspirationConfirm}
                    onBack={() => setShowInspirationEditor(false)}
                  />
                </CardContent>
              </Card>
            )}

            {/* 大纲工作流阶段 */}
            {showOutlineWorkflow && outline && (
              <OutlineWorkflow
                projectId={project.id}
                outline={outline}
                modelId={selectedModelId}
                onOutlineUpdate={handleOutlineUpdate}
                onStageChange={handleStageChange}
                onGeneratingChange={setIsGenerating}
              />
            )}

            {/* 章节列表阶段 */}
            {showChapterList && (
              <div className="flex gap-6 flex-1">
                <ChapterList
                  chapters={chapterOutlines}
                  selectedChapter={selectedChapter}
                  onSelectChapter={setSelectedChapter}
                />
                <ChapterOutlineDetail
                  chapter={selectedChapter}
                  projectId={project.id}
                  onConfirm={handleConfirmChapterOutline}
                />
              </div>
            )}
          </>
        )}
      </div>

      {/* 返回确认弹窗 */}
      <ConfirmDialog
        open={showReturnConfirm}
        title="返回列表"
        message="当前正在生成大纲，返回列表会中断生成进度，已生成的内容将会保留。"
        confirmText="确认返回"
        cancelText="继续生成"
        onConfirm={() => {
          setShowReturnConfirm(false)
          setIsGenerating(false)
          navigate('/')
        }}
        onCancel={() => setShowReturnConfirm(false)}
      />

      {/* 恢复创作弹窗 */}
      {workflowState && (
        <ResumeDialog
          open={showResumeDialog}
          onOpenChange={setShowResumeDialog}
          projectName={project.name}
          currentStage={workflowState.stage}
          currentChapter={workflowState.current_chapter}
          writtenChaptersCount={workflowState.written_chapters_count}
          waitingForConfirmation={workflowState.waiting_for_confirmation}
          confirmationType={workflowState.confirmation_type}
          hasChapters={workflowState.total_chapters > 0}
          onResume={() => {
            console.log('Resume workflow')
          }}
          onViewChapters={() => {
            setViewingStep(3)
          }}
        />
      )}
    </div>
  )
}
