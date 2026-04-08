// frontend/src/pages/ProjectDetail.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { projectsApi, outlineApi, chapterOutlinesApi } from '@/lib/api'
import { useProjectStore } from '@/stores/projectStore'
import type { ProjectDetail, Outline, ChapterOutline } from '@/types'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [outline, setOutline] = useState<Outline | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
  const [loading, setLoading] = useState(true)

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

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  if (!project) {
    return <div className="text-center py-10">项目不存在</div>
  }

  return (
    <div>
      {/* Project Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">{project.name}</h1>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <span>创建时间: {new Date(project.created_at).toLocaleDateString()}</span>
          <span>阶段: {project.stage}</span>
          <span>字数: {project.total_words.toLocaleString()}</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex gap-6">
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
                  <Link to={`/project/${project.id}/write`}>
                    <Button>
                      {selectedChapter.has_content ? '编辑正文' : '开始写作'}
                    </Button>
                  </Link>
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
      </div>
    </div>
  )
}