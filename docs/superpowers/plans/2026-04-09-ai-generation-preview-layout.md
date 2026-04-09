# AI 生成预览页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 Writing.tsx 为分屏布局：左侧章节列表，右上周节大纲，右下内容预览，生成完毕后点击"编辑"进入富文本编辑器。

**Architecture:** 单页面双模式（预览/编辑），通过 state 切换。左侧章节列表点击切换章节，右上显示章节大纲，右下显示纯文本预览或富文本编辑器。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui, TipTap

---

## File Structure

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/pages/Writing.tsx` | 修改 | 重构为分屏布局 + 预览/编辑双模式 |
| `frontend/src/components/common/TipTapEditor.tsx` | 不改 | 仅用于编辑模式 |

---

### Task 1: 重构 Writing.tsx 为分屏布局

**Files:**
- Modify: `frontend/src/pages/Writing.tsx`

- [ ] **Step 1: 添加预览/编辑模式状态和章节切换逻辑**

在组件顶部添加新的 state：

```tsx
// 在现有 state 后添加
const [mode, setMode] = useState<'preview' | 'edit'>('preview')
const [chapterOutlines, setChapterOutlines] = useState<ChapterOutline[]>([])
```

修改 fetchData 函数加载所有章节大纲：

```tsx
const fetchData = async () => {
  if (!id) return
  setLoading(true)
  setError(null)

  try {
    const projectData = await projectsApi.get(parseInt(id))
    setProject(projectData)

    const chaptersData = await chapterOutlinesApi.list(parseInt(id))
    setChapterOutlines(chaptersData)

    // Find first chapter without content, or use first chapter
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
    setError(err instanceof Error ? err.message : '加载数据失败')
  } finally {
    setLoading(false)
  }
}
```

- [ ] **Step 2: 添加章节切换处理函数**

```tsx
const handleChapterSelect = async (chapter: ChapterOutline) => {
  if (isGenerating) return // 生成中不允许切换
  
  setCurrentChapter(chapter)
  setMode('preview')
  
  try {
    const chapterData = await chaptersApi.get(parseInt(id!), chapter.chapter_number)
    setContent(chapterData.content || '')
    setWordCount(chapterData.word_count || 0)
  } catch {
    setContent('')
    setWordCount(0)
  }
}
```

- [ ] **Step 3: 重构 JSX 为分屏布局**

替换整个 return 部分：

```tsx
if (loading) {
  return <div className="text-center py-10">加载中...</div>
}

if (!project || !currentChapter) {
  return (
    <div className="max-w-4xl mx-auto">
      <ErrorMessage message="项目或章节不存在" />
    </div>
  )
}

return (
  <div className="flex min-h-[calc(100vh-80px)]">
    {/* 左侧章节列表 */}
    <div className="w-[200px] border-r bg-background shrink-0">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-sm">章节列表</h2>
      </div>
      <div className="overflow-y-auto max-h-[calc(100vh-140px)]">
        {chapterOutlines.map((chapter) => (
          <div
            key={chapter.id}
            onClick={() => handleChapterSelect(chapter)}
            className={`px-4 py-3 text-sm cursor-pointer border-b ${
              currentChapter.id === chapter.id
                ? 'bg-secondary font-medium'
                : 'hover:bg-muted'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate">
                第{chapter.chapter_number}章：{chapter.title || '未命名'}
              </span>
              {chapter.has_content && (
                <span className="text-green-600 text-xs ml-1">✓</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* 右侧区域 */}
    <div className="flex-1 flex flex-col">
      {/* 右上：章节大纲 */}
      <div className="border-b p-4 bg-background">
        <h3 className="font-semibold mb-3">
          第{currentChapter.chapter_number}章：{currentChapter.title || '未命名'}
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div><span className="text-muted-foreground">场景：</span>{currentChapter.scene || '-'}</div>
          <div><span className="text-muted-foreground">人物：</span>{currentChapter.characters || '-'}</div>
          <div className="col-span-2"><span className="text-muted-foreground">情节：</span>{currentChapter.plot || '-'}</div>
          <div><span className="text-muted-foreground">冲突：</span>{currentChapter.conflict || '-'}</div>
          <div><span className="text-muted-foreground">结局：</span>{currentChapter.ending || '-'}</div>
        </div>
      </div>

      {/* 右下：内容区域 */}
      <div className="flex-1 flex flex-col">
        {/* 状态栏 */}
        <div className="px-4 py-2 border-b bg-muted/30 flex justify-between items-center">
          <div className="flex items-center gap-2">
            {isGenerating ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm text-green-600">正在生成...</span>
              </>
            ) : wordCount > 0 ? (
              <>
                <div className="w-2 h-2 bg-green-500 rounded-full" />
                <span className="text-sm text-green-600">生成完成</span>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">未生成</span>
            )}
          </div>
          <span className="text-sm text-muted-foreground">
            {wordCount > 0 ? `共 ${wordCount} 字` : ''}
          </span>
        </div>

        {/* 内容区：预览或编辑 */}
        <div className="flex-1 overflow-y-auto p-6 bg-background">
          {mode === 'edit' ? (
            <TipTapEditor
              content={content}
              onChange={handleContentChange}
              placeholder="开始写作..."
            />
          ) : (
            <div className="prose max-w-none">
              {content ? (
                content.split('\n').filter(p => p.trim()).map((paragraph, i) => (
                  <p key={i} className="mb-4 leading-relaxed" style={{ textIndent: '2em' }}>
                    {paragraph}
                  </p>
                ))
              ) : (
                <p className="text-muted-foreground">点击下方按钮生成内容</p>
              )}
            </div>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="px-4 py-3 border-t bg-muted/30 flex gap-2">
          {mode === 'edit' ? (
            <>
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? '保存中...' : '保存'}
              </Button>
              <Button variant="outline" onClick={() => setMode('preview')}>
                返回预览
              </Button>
            </>
          ) : isGenerating ? (
            <Button variant="destructive" onClick={handleStop}>
              停止生成
            </Button>
          ) : (
            <>
              <Button onClick={handleGenerate}>AI 生成</Button>
              {wordCount > 0 && (
                <>
                  <Button variant="outline" onClick={() => setMode('edit')}>
                    编辑
                  </Button>
                  <Button variant="outline" onClick={handleGenerate}>
                    重新生成
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate(`/project/${id}/read/${currentChapter.chapter_number}`)}
                  >
                    审核
                  </Button>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  </div>
)
```

- [ ] **Step 4: 移除不再需要的导入**

移除未使用的导入：

```tsx
// 移除这行（如果存在）
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
```

- [ ] **Step 5: 重新构建前端镜像**

```bash
cd /opt/project/novelagent/novelagent && docker compose build --no-cache frontend && docker compose up -d frontend
```

- [ ] **Step 6: 提交更改**

```bash
cd /opt/project/novelagent/novelagent
git add frontend/src/pages/Writing.tsx
git commit -m "$(cat <<'EOF'
feat: refactor Writing page to split layout with preview/edit modes

- Left panel (200px): Chapter list with click-to-switch
- Top-right: Chapter outline (scene, characters, plot, etc.)
- Bottom-right: Content preview with paragraph display
- Preview mode: Plain text display, click Edit to enter editor
- Edit mode: TipTap rich text editor

User workflow: Generate → Preview → Click Edit → Edit in TipTap

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

- [x] Spec coverage: 左侧章节列表 ✓，右上周节大纲 ✓，右下内容预览 ✓，编辑按钮 ✓
- [x] Placeholder scan: 无 TBD/TODO
- [x] Type consistency: ChapterOutline 类型已存在于 types/index.ts