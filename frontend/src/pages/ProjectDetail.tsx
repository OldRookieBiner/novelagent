// frontend/src/pages/ProjectDetail.tsx
import { useState, useEffect } from 'react'
import { useParams, Link, useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { projectsApi, outlineApi, chapterOutlinesApi } from '@/lib/api'
import { useProjectStore } from '@/stores/projectStore'
import OutlineWorkflow from '@/components/project/OutlineWorkflow'
import StepNavigation, { HistoryBanner, STEPS } from '@/components/project/StepNavigation'
import InspirationForm from '@/components/project/InspirationForm'
import InspirationEditor from '@/components/project/InspirationEditor'
import InspirationDisplay from '@/components/project/InspirationDisplay'
import ConfirmDialog from '@/components/common/ConfirmDialog'
import { generateInspirationTemplate, type InspirationData } from '@/lib/inspiration'
import type { ProjectDetail, ChapterOutline, Outline, CollectedInfo } from '@/types'

const STAGE_LABELS: Record<string, string> = {
  inspiration_collecting: '灵感采集',
  outline_generating: '生成大纲',
  outline_confirming: '确认大纲',
  chapter_outlines_generating: '生成章节纲',
  chapter_outlines_confirming: '确认章节纲',
  chapter_writing: '写作中',
  chapter_reviewing: '审核中',
  completed: '已完成',
  paused: '暂停',
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [outline, setOutline] = useState<Outline | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingStep, setViewingStep] = useState<number | null>(() => {
    const viewStepParam = searchParams.get('viewStep')
    return viewStepParam ? parseInt(viewStepParam) : null
  })

  // 灵感采集状态
  const [inspirationData, setInspirationData] = useState<InspirationData | null>(null)
  const [inspirationTemplate, setInspirationTemplate] = useState('')
  const [showInspirationEditor, setShowInspirationEditor] = useState(false)

  // 返回确认弹窗状态
  const [isGenerating, setIsGenerating] = useState(false)
  const [showReturnConfirm, setShowReturnConfirm] = useState(false)

  const setCurrentProject = useProjectStore((state) => state.setCurrentProject)
  const setProjectOutline = useProjectStore((state) => state.setOutline)
  const setProjectChapterOutlines = useProjectStore((state) => state.setChapterOutlines)

  const fetchData = async () => {
    if (!id) return

    try {
      const projectData = await projectsApi.get(parseInt(id))
      setProject(projectData)
      setCurrentProject(projectData)

      const outlineData = await outlineApi.get(parseInt(id))
      setOutline(outlineData)
      setProjectOutline(outlineData)

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
      setProjectChapterOutlines(chaptersData)

      if (chaptersData.length > 0) {
        setSelectedChapter(chaptersData[0])
      }
    } catch (err) {
      console.error('Failed to fetch project:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [id])

  // 灵感数据回显：从 outline 恢复已保存的灵感数据
  useEffect(() => {
    if (outline?.collected_info && !inspirationData) {
      // 将 CollectedInfo 转换为 InspirationData
      const info = outline.collected_info as unknown as InspirationData
      if (info.novelType) {
        setInspirationData(info)
      }
    }
    if (outline?.inspiration_template && !inspirationTemplate) {
      setInspirationTemplate(outline.inspiration_template)
    }
  }, [outline])

  // Handlers for workflow components
  const handleStageChange = async (stage: string, skipRefresh = false) => {
    if (!project) return
    try {
      if (!skipRefresh) {
        await projectsApi.update(project.id, { stage })
      }
      // Fetch updated project detail
      const updatedProject = await projectsApi.get(project.id)
      setProject(updatedProject)

      // Only refresh outline if not skipped (i.e., not from streaming completion)
      if (!skipRefresh) {
        const outlineData = await outlineApi.get(parseInt(id!))
        setOutline(outlineData)
        setProjectOutline(outlineData)
      }

      // Refresh chapter outlines if we're in writing stage
      if (stage === 'chapter_outlines_confirming' || stage === 'chapter_writing') {
        const chaptersData = await chapterOutlinesApi.list(parseInt(id!))
        setChapterOutlines(chaptersData)
        setProjectChapterOutlines(chaptersData)
        if (chaptersData.length > 0) {
          setSelectedChapter(chaptersData[0])
        }
      }
    } catch (err) {
      console.error('Failed to update stage:', err)
    }
  }

  const handleOutlineUpdate = (updatedOutline: Outline) => {
    setOutline(updatedOutline)
    setProjectOutline(updatedOutline)
  }

  const handleConfirmChapterOutline = async (chapterNum: number) => {
    if (!id) return
    try {
      await chapterOutlinesApi.confirm(parseInt(id), chapterNum)
      // Refresh chapter outlines
      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
      setProjectChapterOutlines(chaptersData)
      // Update selected chapter
      const updatedChapter = chaptersData.find(c => c.chapter_number === chapterNum)
      if (updatedChapter) {
        setSelectedChapter(updatedChapter)
      }
      // Check if all confirmed, update stage
      const allConfirmed = chaptersData.every(c => c.confirmed)
      if (allConfirmed && project && project.stage !== 'chapter_writing') {
        await projectsApi.update(project.id, { stage: 'chapter_writing' })
        const updatedProject = await projectsApi.get(project.id)
        setProject(updatedProject)
      }
    } catch (err) {
      console.error('Failed to confirm chapter outline:', err)
      alert('确认章节大纲失败')
    }
  }

  // Step navigation handlers
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

  // 灵感采集 handlers
  const handleInspirationSubmit = (data: InspirationData) => {
    setInspirationData(data)
    setInspirationTemplate(generateInspirationTemplate(data))
    setShowInspirationEditor(true)
  }

  const handleInspirationConfirm = async () => {
    if (!inspirationData || !project) return

    try {
      // 保存灵感数据和模板
      await outlineApi.update(project.id, {
        collected_info: inspirationData as unknown as CollectedInfo,
        inspiration_template: inspirationTemplate,
      })
      // 更新 stage 到大纲生成
      await projectsApi.update(project.id, { stage: 'outline_generating' })
      // 刷新数据
      const updatedProject = await projectsApi.get(project.id)
      setProject(updatedProject)
      const outlineData = await outlineApi.get(project.id)
      setOutline(outlineData)
      setShowInspirationEditor(false)
    } catch (err) {
      console.error('Failed to confirm inspiration:', err)
    }
  }

  // 修改灵感采集记录（大纲未确认时）
  const handleInspirationUpdate = async (data: InspirationData) => {
    if (!project) return

    try {
      // 保存灵感数据
      await outlineApi.update(project.id, {
        collected_info: data as unknown as CollectedInfo,
        inspiration_template: generateInspirationTemplate(data),
        // 清空大纲内容，需要重新生成
        title: '',
        summary: '',
        plot_points: [],
      })
      // 更新 stage 到大纲生成
      await projectsApi.update(project.id, { stage: 'outline_generating' })
      // 刷新数据
      const updatedProject = await projectsApi.get(project.id)
      setProject(updatedProject)
      const outlineData = await outlineApi.get(project.id)
      setOutline(outlineData)
      // 返回当前步骤
      setViewingStep(null)
      setSearchParams({})
    } catch (err) {
      console.error('Failed to update inspiration:', err)
    }
  }

  // Render history content for a specific step
  const renderHistoryContent = (stepIndex: number) => {
    switch (stepIndex) {
      case 0: // 灵感采集
        const info = outline?.collected_info
        // 如果大纲未确认，允许修改灵感采集
        if (outline && !outline.confirmed) {
          return (
            <Card className="flex-1">
              <CardHeader>
                <CardTitle>修改灵感采集</CardTitle>
              </CardHeader>
              <CardContent>
                <InspirationForm
                  initialData={info as Partial<InspirationData>}
                  onSubmit={(data) => {
                    // 保存灵感数据并返回大纲生成阶段
                    handleInspirationUpdate(data)
                  }}
                />
              </CardContent>
            </Card>
          )
        }
        return (
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>灵感采集记录</CardTitle>
            </CardHeader>
            <CardContent>
              {info && Object.keys(info).length > 0 ? (
                <InspirationDisplay data={info} />
              ) : (
                <div className="text-muted-foreground">暂无灵感采集记录</div>
              )}
            </CardContent>
          </Card>
        )

      case 1: // 大纲生成
        return (
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>大纲信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {outline ? (
                <>
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">标题</div>
                    <div className="text-lg font-bold">{outline.title || '未设置'}</div>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">简介</div>
                    <div>{outline.summary || '未设置'}</div>
                  </div>
                  {outline.plot_points && outline.plot_points.length > 0 && (
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">主要情节节点</div>
                      <ul className="list-disc list-inside text-sm mt-1">
                        {outline.plot_points.map((point, idx) => {
                          // v0.6.1: 支持新的字典格式
                          const eventText = typeof point === 'string' ? point : point.event
                          return <li key={idx} className="mb-1">{eventText}</li>
                        })}
                      </ul>
                    </div>
                  )}
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">章节数</div>
                    <div>{outline.chapter_count_suggested || 0} 章</div>
                  </div>
                </>
              ) : (
                <div className="text-muted-foreground">暂无大纲信息</div>
              )}
            </CardContent>
          </Card>
        )

      case 2: // 章节纲
      case 3: // 写作
      case 4: // 审核
        return (
          <>
            {/* Chapter List */}
            <Card className="w-64 shrink-0">
              <CardHeader>
                <CardTitle className="text-lg">章节列表</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-96 overflow-y-auto">
                  {chapterOutlines.length === 0 ? (
                    <div className="p-4 text-center text-muted-foreground text-sm">
                      暂无章节
                    </div>
                  ) : (
                    chapterOutlines.map((chapter) => (
                      <div
                        key={chapter.id}
                        className={`px-4 py-2 border-b cursor-pointer hover:bg-muted ${
                          selectedChapter?.id === chapter.id ? 'bg-muted' : ''
                        }`}
                        onClick={() => setSelectedChapter(chapter)}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-sm">
                            {chapter.chapter_number}. {chapter.title || '未命名'}
                          </span>
                          {chapter.has_content && (
                            <span className="text-xs text-green-600">✓</span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Chapter Outline Detail */}
            <Card className="flex-1">
              <CardHeader>
                <CardTitle className="text-lg">
                  {selectedChapter
                    ? `第 ${selectedChapter.chapter_number} 章：${selectedChapter.title || '未命名'}`
                    : '章节详情'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedChapter ? (
                  <div className="space-y-4">
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">场景</div>
                      <div>{selectedChapter.scene || '-'}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">人物</div>
                      <div>{selectedChapter.characters || '-'}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">情节</div>
                      <div>{selectedChapter.plot || '-'}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">冲突</div>
                      <div>{selectedChapter.conflict || '-'}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">结局</div>
                      <div>{selectedChapter.ending || '-'}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">预计字数</div>
                      <div>{selectedChapter.target_words} 字</div>
                    </div>

                    <div className="flex gap-2 pt-4">
                      {!selectedChapter.confirmed && (
                        <Button
                          onClick={() => handleConfirmChapterOutline(selectedChapter.chapter_number)}
                        >
                          确认章节大纲
                        </Button>
                      )}
                      {selectedChapter.confirmed && project && (
                        <Link to={`/project/${project.id}/write`}>
                          <Button>
                            {selectedChapter.has_content ? '编辑正文' : '开始写作'}
                          </Button>
                        </Link>
                      )}
                      {selectedChapter.has_content && project && (
                        <Link to={`/project/${project.id}/read/${selectedChapter.chapter_number}`}>
                          <Button variant="outline">阅读正文</Button>
                        </Link>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-10">
                    选择左侧章节查看详情
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )

      default:
        return null
    }
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  if (!project) {
    return <div className="text-center py-10">项目不存在</div>
  }

  // Determine which workflow to show based on stage
  const showInspirationCollection = project.stage === 'inspiration_collecting'
  const showOutlineWorkflow = [
    'outline_generating',
    'outline_confirming',
    'chapter_outlines_generating',
  ].includes(project.stage)
  const showChapterList = [
    'chapter_outlines_confirming',
    'chapter_writing',
    'chapter_reviewing',
    'completed',
  ].includes(project.stage)

  return (
    <div>
      {/* Project Header */}
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
          <span>阶段: {STAGE_LABELS[project.stage] || project.stage}</span>
          <span>字数: {project.total_words.toLocaleString()}</span>
        </div>
      </div>

      {/* Step Navigation */}
      <StepNavigation
        currentStage={project.stage}
        viewingStep={viewingStep}
        onViewStep={handleViewStep}
        outlineConfirmed={outline?.confirmed}
      />

      {/* History Banner */}
      {viewingStep !== null && (
        <HistoryBanner
          stepName={STEPS[viewingStep].name}
          onReturn={handleReturnToCurrent}
        />
      )}

      {/* Main Content - Render based on stage or history view */}
      <div className="flex gap-6 mt-4">
        {/* History Content */}
        {viewingStep !== null ? (
          renderHistoryContent(viewingStep)
        ) : (
          <>
            {/* Inspiration Collection Stage */}
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

            {/* Outline Workflow Stage */}
            {showOutlineWorkflow && outline && (
              <OutlineWorkflow
                projectId={project.id}
                outline={outline}
                onOutlineUpdate={handleOutlineUpdate}
                onStageChange={handleStageChange}
                onGeneratingChange={setIsGenerating}
              />
            )}

            {/* Chapter List Stage */}
            {showChapterList && (
              <>
                {/* Chapter List */}
                <Card className="w-64 shrink-0">
                  <CardHeader>
                    <CardTitle className="text-lg">章节列表</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="max-h-96 overflow-y-auto">
                      {chapterOutlines.length === 0 ? (
                        <div className="p-4 text-center text-muted-foreground text-sm">
                          暂无章节
                        </div>
                      ) : (
                        chapterOutlines.map((chapter) => (
                          <div
                            key={chapter.id}
                            className={`px-4 py-2 border-b cursor-pointer hover:bg-muted ${
                              selectedChapter?.id === chapter.id ? 'bg-muted' : ''
                            }`}
                            onClick={() => setSelectedChapter(chapter)}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-sm">
                                {chapter.chapter_number}. {chapter.title || '未命名'}
                              </span>
                              {chapter.has_content && (
                                <span className="text-xs text-green-600">✓</span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Chapter Outline Detail */}
                <Card className="flex-1">
                  <CardHeader>
                    <CardTitle className="text-lg">
                      {selectedChapter
                        ? `第 ${selectedChapter.chapter_number} 章：${selectedChapter.title || '未命名'}`
                        : '章节详情'}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {selectedChapter ? (
                      <div className="space-y-4">
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">场景</div>
                          <div>{selectedChapter.scene || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">人物</div>
                          <div>{selectedChapter.characters || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">情节</div>
                          <div>{selectedChapter.plot || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">冲突</div>
                          <div>{selectedChapter.conflict || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">结局</div>
                          <div>{selectedChapter.ending || '-'}</div>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-muted-foreground">预计字数</div>
                          <div>{selectedChapter.target_words} 字</div>
                        </div>

                        <div className="flex gap-2 pt-4">
                          {!selectedChapter.confirmed && (
                            <Button
                              onClick={() => handleConfirmChapterOutline(selectedChapter.chapter_number)}
                            >
                              确认章节大纲
                            </Button>
                          )}
                          {selectedChapter.confirmed && (
                            <Link to={`/project/${project.id}/write`}>
                              <Button>
                                {selectedChapter.has_content ? '编辑正文' : '开始写作'}
                              </Button>
                            </Link>
                          )}
                          {selectedChapter.has_content && (
                            <Link to={`/project/${project.id}/read/${selectedChapter.chapter_number}`}>
                              <Button variant="outline">阅读正文</Button>
                            </Link>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center text-muted-foreground py-10">
                        选择左侧章节查看详情
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
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
    </div>
  )
}