# NovelAgent v0.2.0 Implementation Plan - Phase 4-5 (Continued)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**前置条件:** Phase 1-3 已完成

---

## Phase 4: 页面实现（续）

### Task 25: 项目详情页

**Files:**
- Create: `frontend/src/pages/ProjectDetail.tsx`

- [ ] **Step 1: 创建项目详情页**

```tsx
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/ProjectDetail.tsx
git commit -m "feat: add project detail page"
```

---

### Task 26: 写作页面（带 TipTap 编辑器）

**Files:**
- Create: `frontend/src/pages/Writing.tsx`
- Create: `frontend/src/components/common/TipTapEditor.tsx`

- [ ] **Step 1: 创建 TipTap 编辑器组件**

```tsx
// frontend/src/components/common/TipTapEditor.tsx
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { Button } from '@/components/ui/button'
import { Bold, Italic, Undo, Redo } from 'lucide-react'

interface TipTapEditorProps {
  content: string
  onChange: (content: string) => void
  placeholder?: string
  readOnly?: boolean
}

export default function TipTapEditor({
  content,
  onChange,
  placeholder = '开始写作...',
  readOnly = false,
}: TipTapEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder,
      }),
    ],
    content,
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      onChange(editor.getText())
    },
  })

  if (!editor) {
    return null
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      {!readOnly && (
        <div className="border-b bg-muted/50 p-2 flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={editor.isActive('bold') ? 'bg-muted' : ''}
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={editor.isActive('italic') ? 'bg-muted' : ''}
          >
            <Italic className="h-4 w-4" />
          </Button>
          <div className="w-px bg-border mx-1" />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
          >
            <Undo className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
          >
            <Redo className="h-4 w-4" />
          </Button>
        </div>
      )}
      <EditorContent
        editor={editor}
        className="prose max-w-none p-4 min-h-[400px] focus:outline-none"
      />
    </div>
  )
}
```

- [ ] **Step 2: 创建写作页面**

```tsx
// frontend/src/pages/Writing.tsx
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import TipTapEditor from '@/components/common/TipTapEditor'
import { projectsApi, chapterOutlinesApi, chaptersApi } from '@/lib/api'
import type { ProjectDetail, ChapterOutline } from '@/types'

export default function Writing() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
  const [currentChapter, setCurrentChapter] = useState<ChapterOutline | null>(null)
  const [content, setContent] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [wordCount, setWordCount] = useState(0)

  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    fetchData()
    return () => {
      // Cancel any ongoing stream
      abortControllerRef.current?.abort()
    }
  }, [id])

  const fetchData = async () => {
    if (!id) return

    try {
      const projectData = await projectsApi.get(parseInt(id))
      setProject(projectData)

      const chaptersData = await chapterOutlinesApi.list(parseInt(id))
      setChapterOutlines(chaptersData)

      // Find first chapter without content
      const nextChapter = chaptersData.find(c => !c.has_content) || chaptersData[0]
      if (nextChapter) {
        setCurrentChapter(nextChapter)
        // Load existing content if any
        try {
          const chapter = await chaptersApi.get(parseInt(id), nextChapter.chapter_number)
          setContent(chapter.content || '')
          setWordCount(chapter.word_count || 0)
        } catch {
          setContent('')
          setWordCount(0)
        }
      }
    } catch (err) {
      console.error('Failed to fetch data:', err)
    }
  }

  const handleGenerate = async () => {
    if (!id || !currentChapter || isGenerating) return

    setIsGenerating(true)
    setContent('')
    setWordCount(0)

    // Create abort controller for streaming
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`/api/projects/${id}/chapters/${currentChapter.chapter_number}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) throw new Error('Failed to generate')

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No reader')

      const decoder = new TextDecoder()
      let accumulated = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        accumulated += chunk
        setContent(accumulated)
        setWordCount(accumulated.length)
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Failed to generate:', err)
      }
    } finally {
      setIsGenerating(false)
    }
  }

  const handleStop = () => {
    abortControllerRef.current?.abort()
    setIsGenerating(false)
  }

  const handleSave = async () => {
    if (!id || !currentChapter) return

    setIsSaving(true)
    try {
      await chaptersApi.update(parseInt(id), currentChapter.chapter_number, content)
    } catch (err) {
      console.error('Failed to save:', err)
    } finally {
      setIsSaving(false)
    }
  }

  const handleContentChange = (newContent: string) => {
    setContent(newContent)
    setWordCount(newContent.length)
  }

  if (!project || !currentChapter) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">
          第 {currentChapter.chapter_number} 章：{currentChapter.title || '未命名'}
        </h1>
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>预计 {currentChapter.target_words} 字</span>
          <span>已写 {wordCount} 字</span>
        </div>
      </div>

      {/* Chapter Outline Summary */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">章节大纲</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>{currentChapter.plot}</p>
        </CardContent>
      </Card>

      {/* Editor */}
      <div className="mb-4">
        <TipTapEditor
          content={content}
          onChange={handleContentChange}
          placeholder={isGenerating ? '正在生成...' : '点击下方按钮生成内容，或直接开始写作...'}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {isGenerating ? (
          <Button variant="destructive" onClick={handleStop}>
            停止生成
          </Button>
        ) : (
          <Button onClick={handleGenerate}>AI 生成</Button>
        )}
        <Button variant="outline" onClick={handleSave} disabled={isSaving}>
          {isSaving ? '保存中...' : '保存'}
        </Button>
        {wordCount > 0 && (
          <Button
            variant="outline"
            onClick={() => navigate(`/project/${id}/read/${currentChapter.chapter_number}`)}
          >
            阅读/审核
          </Button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Writing.tsx frontend/src/components/common/TipTapEditor.tsx
git commit -m "feat: add writing page with TipTap editor and streaming"
```

---

### Task 27: 阅读/审核页面

**Files:**
- Create: `frontend/src/pages/Reading.tsx`

- [ ] **Step 1: 创建阅读页面**

```tsx
// frontend/src/pages/Reading.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChevronLeft, ChevronRight, Check, X } from 'lucide-react'
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
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Reading.tsx
git commit -m "feat: add reading page with review functionality"
```

---

### Task 28: 设置页面

**Files:**
- Create: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 创建设置页面**

```tsx
// frontend/src/pages/Settings.tsx
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { settingsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import type { UserSettings, SettingsUpdate } from '@/types'

const MODEL_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek (火山方舟)' },
  { value: 'deepseek-official', label: 'DeepSeek (官方)' },
  { value: 'openai', label: 'OpenAI' },
]

const REVIEW_STRICTNESS = [
  { value: 'loose', label: '宽松' },
  { value: 'standard', label: '标准' },
  { value: 'strict', label: '严格' },
]

export default function Settings() {
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Form state
  const [modelProvider, setModelProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [reviewEnabled, setReviewEnabled] = useState(true)
  const [reviewStrictness, setReviewStrictness] = useState('standard')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const data = await settingsApi.get()
      setSettings(data)
      setModelProvider(data.model_provider)
      setReviewEnabled(data.review_enabled)
      setReviewStrictness(data.review_strictness)
      useSettingsStore.getState().setSettings(data)
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)

    try {
      const update: SettingsUpdate = {
        model_provider: modelProvider,
        review_enabled: reviewEnabled,
        review_strictness: reviewStrictness,
      }

      if (apiKey) {
        update.api_key = apiKey
      }

      const updated = await settingsApi.update(update)
      setSettings(updated)
      useSettingsStore.getState().setSettings(updated)
      setApiKey('')
      setSaved(true)
    } catch (err) {
      console.error('Failed to save settings:', err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">设置</h1>

      {/* Model Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>模型配置</CardTitle>
          <CardDescription>配置 AI 模型和 API Key</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">模型提供商</label>
            <select
              className="w-full h-10 px-3 rounded-md border border-input bg-background"
              value={modelProvider}
              onChange={(e) => setModelProvider(e.target.value)}
            >
              {MODEL_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              API Key {settings?.has_api_key && '(已设置)'}
            </label>
            <Input
              type="password"
              placeholder={settings?.has_api_key ? '输入新的 API Key 以更新' : '输入 API Key'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              API Key 会被加密存储
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Review Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>审核设置</CardTitle>
          <CardDescription>配置章节审核行为</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">启用审核</label>
            <input
              type="checkbox"
              checked={reviewEnabled}
              onChange={(e) => setReviewEnabled(e.target.checked)}
              className="h-4 w-4"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">审核严格度</label>
            <select
              className="w-full h-10 px-3 rounded-md border border-input bg-background"
              value={reviewStrictness}
              onChange={(e) => setReviewStrictness(e.target.value)}
              disabled={!reviewEnabled}
            >
              {REVIEW_STRICTNESS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex items-center gap-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存设置'}
        </Button>
        {saved && (
          <span className="text-sm text-green-600">已保存</span>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: add settings page for model and review configuration"
```

---

## Phase 5: 部署和验证

### Task 29: 前端 Dockerfile

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 2: 创建 nginx.conf**

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

- [ ] **Step 3: 提交**

```bash
git add frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: add frontend Dockerfile and nginx config"
```

---

### Task 30: 最终集成测试

**Files:**
- 无新文件

- [ ] **Step 1: 构建并启动 Docker 容器**

```bash
docker-compose build
docker-compose up -d
```

- [ ] **Step 2: 检查服务状态**

```bash
docker-compose ps
docker-compose logs backend
docker-compose logs frontend
```

- [ ] **Step 3: 访问应用测试**

```bash
# 访问 http://localhost:3000
# 测试登录（使用默认账号密码）
# 测试创建项目
# 测试生成大纲
# 测试写作和审核流程
```

- [ ] **Step 4: 运行数据库迁移**

```bash
docker-compose exec backend alembic upgrade head
```

- [ ] **Step 5: 最终提交**

```bash
git add .
git commit -m "feat: complete v0.2.0 implementation"
git tag v0.2.0
```

---

## 全部验收清单

### 功能验收

- [ ] 用户可登录系统
- [ ] 用户可创建/删除项目
- [ ] 用户可与 Agent 对话收集信息
- [ ] Agent 可生成大纲
- [ ] Agent 可建议章节数，用户可调整
- [ ] Agent 可一次性生成所有章节纲
- [ ] 用户可编辑大纲和章节纲
- [ ] Agent 可流式生成章节正文
- [ ] 用户可编辑章节正文
- [ ] 用户可开启/关闭审核
- [ ] 审核不通过时可重写
- [ ] 用户可配置模型和 API Key
- [ ] 支持多模型切换

### 技术验收

- [ ] Docker Compose 一键启动
- [ ] 数据库迁移正常
- [ ] 前后端分离部署
- [ ] 流式响应正常
- [ ] Session 认证正常

---

**计划完成！**