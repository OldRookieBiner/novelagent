// frontend/src/pages/Reading.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChevronLeft, ChevronRight, Check, X } from 'lucide-react'
import StepNavigation from '@/components/project/StepNavigation'
import { projectsApi, chapterOutlinesApi, chaptersApi, workflowApi } from '@/lib/api'
import type { ProjectDetail, ChapterOutline, Chapter } from '@/types'

export default function Reading() {
  const { id, chapterNum } = useParams<{ id: string; chapterNum: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [currentOutline, setCurrentOutline] = useState<ChapterOutline | null>(null)
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [isReviewing, setIsReviewing] = useState(false)
  const [reviewResult, setReviewResult] = useState<{ passed: boolean; feedback: string } | null>(null)

  const chapterNumber = parseInt(chapterNum || '1')

  useEffect(() => {
    fetchData()
  }, [id, chapterNum])

  const fetchData = async () => {
    if (!id) return

    try {
      const projectData = await projectsApi.get(parseInt(id))

      // Ensure stage is set to review when entering reading/review page
      if (projectData.workflow_state?.stage === 'writing') {
        await workflowApi.updateStage(projectData.id, 'review')
        const updatedProject = await projectsApi.get(parseInt(id))
        setProject(updatedProject)
      } else {
        setProject(projectData)
      }

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)

      const outline = chaptersData.find(c => c.chapter_number === chapterNumber)
      setCurrentOutline(outline || null)

      // Try to fetch chapter content, handle 404 for chapters without content
      try {
        const chapterData = await chaptersApi.get(parseInt(id), chapterNumber)
        setChapter(chapterData)
      } catch {
        // Chapter has no content yet, set empty state
        setChapter({
          id: 0,
          chapter_outline_id: outline?.id || 0,
          content: undefined,
          word_count: 0,
          review_passed: false,
          review_feedback: undefined,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        })
      }

      // Clear review result when switching chapters
      setReviewResult(null)
    } catch (err) {
      console.error('Failed to fetch data:', err)
    }
  }

  const handleReview = async () => {
    if (!id) return

    setIsReviewing(true)
    setReviewResult(null)

    try {
      const result = await chaptersApi.review(parseInt(id), chapterNumber)
      setReviewResult(result)
    } catch (err) {
      console.error('Failed to review:', err)
    } finally {
      setIsReviewing(false)
    }
  }

  // 确认章节大纲
  const handleConfirmOutline = async () => {
    if (!id || !currentOutline) return

    try {
      await chapterOutlinesApi.confirm(parseInt(id), chapterNumber)
      // 刷新数据
      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)
      const outline = chaptersData.find(c => c.chapter_number === chapterNumber)
      setCurrentOutline(outline || null)
    } catch (err) {
      console.error('Failed to confirm chapter outline:', err)
    }
  }

  const goToChapter = (num: number) => {
    navigate(`/project/${id}/read/${num}`)
  }

  const currentIndex = chapterOutlines.findIndex(c => c.chapter_number === chapterNumber)
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < chapterOutlines.length - 1

  if (!project || !chapter) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div>
      {/* Step Navigation */}
      <StepNavigation
        currentStage={project.workflow_state?.stage || 'inspiration'}
        viewingStep={null}
        onViewStep={(stepIndex) => navigate(`/project/${id}?viewStep=${stepIndex}`)}
      />

      <div className="flex min-h-[calc(100vh-80px)]">
        {/* 左侧章节列表 */}
        <div className="w-[200px] border-r bg-background shrink-0">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-sm">章节列表</h2>
          </div>
          <div className="overflow-y-auto max-h-[calc(100vh-140px)]">
            {chapterOutlines.map((outline) => (
              <div
                key={outline.id}
                onClick={() => goToChapter(outline.chapter_number)}
                className={`px-4 py-3 text-sm cursor-pointer border-b ${
                  outline.chapter_number === chapterNumber
                    ? 'bg-secondary font-medium'
                    : 'hover:bg-muted'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="truncate">
                    第{outline.chapter_number}章：{outline.title || '未命名'}
                  </span>
                  {outline.has_content && (
                    <span className="text-green-600 text-xs ml-1">✓</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 右侧内容区 */}
        <div className="flex-1 flex flex-col">
          <div className="max-w-4xl mx-auto w-full p-6">
            {/* Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold mb-2">
                第 {chapterNumber} 章：{currentOutline?.title || '未命名'}
              </h1>
              <div className="text-sm text-muted-foreground">
                字数：{chapter.word_count}
              </div>
            </div>

            {/* Content */}
            <Card className="mb-6">
              <CardContent className="p-6 prose max-w-none">
                {chapter.content ? (
                  chapter.content.split('\n').map((paragraph, i) => (
                    <p key={i}>{paragraph}</p>
                  ))
                ) : (
                  <p className="text-muted-foreground">该章节尚未生成正文</p>
                )}
              </CardContent>
            </Card>

            {/* Review Result */}
            {reviewResult && (
              <Card className={`mb-6 ${reviewResult.passed ? 'border-green-500' : 'border-yellow-500'}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {reviewResult.passed ? (
                      <>
                        <Check className="h-5 w-5 text-green-500" />
                        审核通过
                      </>
                    ) : (
                      <>
                        <X className="h-5 w-5 text-yellow-500" />
                        需要修改
                      </>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-sm">{reviewResult.feedback}</pre>
                </CardContent>
              </Card>
            )}

            {/* Actions */}
            <div className="flex justify-between items-center">
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleReview}
                  disabled={isReviewing || !chapter.content}
                >
                  {isReviewing ? '审核中...' : '审核'}
                </Button>
                {/* 根据章节大纲确认状态显示不同按钮 */}
                {currentOutline?.confirmed ? (
                  <Link to={`/project/${id}/write`}>
                    <Button variant="outline">
                      {chapter.content ? '编辑' : '去写作'}
                    </Button>
                  </Link>
                ) : (
                  <Button variant="outline" onClick={handleConfirmOutline}>
                    确认章节大纲
                  </Button>
                )}
              </div>

              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={!hasPrev}
                  onClick={() => goToChapter(chapterOutlines[currentIndex - 1].chapter_number)}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  上一章
                </Button>
                <Button
                  variant="outline"
                  disabled={!hasNext}
                  onClick={() => goToChapter(chapterOutlines[currentIndex + 1].chapter_number)}
                >
                  下一章
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}