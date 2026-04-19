// frontend/src/pages/Reading.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChevronLeft, ChevronRight, Check, X } from 'lucide-react'
import StepNavigation from '@/components/project/StepNavigation'
import { projectsApi, chapterOutlinesApi, chaptersApi } from '@/lib/api'
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
      setProject(projectData)

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)

      const outline = chaptersData.find(c => c.chapter_number === chapterNumber)
      setCurrentOutline(outline || null)

      const chapterData = await chaptersApi.get(parseInt(id), chapterNumber)
      setChapter(chapterData)
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
        currentStage={project.stage}
        viewingStep={null}
        onViewStep={() => {}}  // 阅读页面不允许查看历史
      />

      <div className="max-w-4xl mx-auto">
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
          {chapter.content?.split('\n').map((paragraph, i) => (
            <p key={i}>{paragraph}</p>
          ))}
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
            disabled={isReviewing}
          >
            {isReviewing ? '审核中...' : '审核'}
          </Button>
          <Link to={`/project/${id}/write`}>
            <Button variant="outline">编辑</Button>
          </Link>
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
  )
}