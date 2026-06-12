// frontend/src/components/workbench/creation/WritingPanel.tsx

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { ChevronLeft, ChevronRight, PanelLeftClose, PanelLeft, ChevronDown, ChevronUp, Check, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Skeleton from '@/components/ui/skeleton'
import { chapterOutlinesApi, chaptersApi, knowledgeStatusApi } from '@/lib/api'
import { ChapterNodePanel } from './ChapterNodePanel'
import type { ChapterNode } from './ChapterNodePanel'
import TipTapEditor from '@/components/common/TipTapEditor'
import type { ChapterOutline, ChapterOutlineUpdate } from '@/types'
import { toast } from 'sonner'
import { useWorkbenchStore } from '@/stores/workbenchStore'

interface WritingPanelProps
{
  projectId: number
}

function stripHtml(html: string): string
{
  if (!html) return ''
  const div = document.createElement('div')
  div.innerHTML = html
  return div.textContent || div.innerText || ''
}

function getWordCount(text: string): number
{
  if (!text) return 0
  const plainText = /<[a-zA-Z][^>]*>/.test(text) ? stripHtml(text) : text
  const chineseChars = (plainText.match(/[\u4e00-\u9fa5]/g) || []).length
  const englishWords = plainText
    .replace(/[\u4e00-\u9fa5]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 0).length
  return chineseChars + englishWords
}

function ChapterListSkeleton()
{
  return (
    <div className="space-y-2 p-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}

function EditorSkeleton()
{
  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-8 w-24" />
      </div>
      <Skeleton className="h-[calc(100vh-250px)] w-full" />
    </div>
  )
}

/** 大纲面板中可编辑的文本字段 */
function EditableField(
  { label, value, onSave, placeholder }:
  { label: string; value: string | null | undefined; onSave: (v: string) => void; placeholder?: string }
)
{
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value || '')

  useEffect(() =>
  {
    setDraft(value || '')
  }, [value])

  if (editing)
  {
    return (
      <div className="mb-1">
        <span className="text-[10px] text-muted-foreground">{label}：</span>
        <input
          className="w-full text-xs border rounded px-1.5 py-0.5 mt-0.5 focus:outline-none focus:ring-1 focus:ring-primary"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() =>
          {
            setEditing(false)
            if (draft !== (value || ''))
            {
              onSave(draft)
            }
          }}
          onKeyDown={(e) =>
          {
            if (e.key === 'Enter')
            {
              setEditing(false)
              if (draft !== (value || ''))
              {
                onSave(draft)
              }
            }
          }}
          autoFocus
        />
      </div>
    )
  }

  return (
    <div className="mb-1 cursor-pointer hover:bg-muted/30 rounded px-0.5" onClick={() => setEditing(true)}>
      <span className="text-[10px] text-muted-foreground">{label}：</span>
      <span className="text-xs">{value || <span className="text-muted-foreground/50 italic">{placeholder || '点击编辑'}</span>}</span>
    </div>
  )
}

type SaveStatus = 'saved' | 'saving' | 'error'

function SaveStatusIndicator({ status, onRetry }: { status: SaveStatus; onRetry: () => void })
{
  const config: Record<SaveStatus, { icon: string; text: string; className: string }> = {
    saved: { icon: '✓', text: '已自动保存', className: 'text-muted-foreground bg-muted' },
    saving: { icon: '↻', text: '保存中...', className: 'text-blue-600 bg-blue-50' },
    error: { icon: '⚠', text: '保存失败，点击重试', className: 'text-red-600 bg-red-50 cursor-pointer' },
  }
  const c = config[status]
  return (
    <span
      className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${c.className}`}
      onClick={status === 'error' ? onRetry : undefined}
    >
      <span>{c.icon}</span>
      <span>{c.text}</span>
    </span>
  )
}

function KnowledgeStatusItem({ label, ok }: { label: string; ok: boolean })
{
  return (
    <span className={ok ? 'text-green-600' : 'text-red-500'}>
      {ok ? '✓' : '✗'} {label}
    </span>
  )
}

export function WritingPanel({ projectId }: WritingPanelProps)
{
  const [chapters, setChapters] = useState<ChapterOutline[]>([])
  const [selectedChapter, setSelectedChapter] = useState<ChapterOutline | null>(null)
    const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingContent, setLoadingContent] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [chapterNode, setChapterNode] = useState<ChapterNode | null>(null)
  const [showChapterNode, setShowChapterNode] = useState(false)
  const [outlineCollapsed, setOutlineCollapsed] = useState(false)

  // 自动保存状态
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved')
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const contentRef = useRef<string>('')
  const prevChapterRef = useRef<ChapterOutline | null>(null)
  const selectedChapterRef = useRef<ChapterOutline | null>(null)

  // 知识库状态
  const [kbStatus, setKbStatus] = useState<{
    blocked: { type: string; message: string }[]
    warnings: { type: string; message: string }[]
  }>({ blocked: [], warnings: [] })

  const knowledgeVersion = useWorkbenchStore((s) => s.knowledgeVersion)
  const { toggleAiSidebar } = useWorkbenchStore()

  // 保持 contentRef 与 content 同步
  useEffect(() =>
  {
    contentRef.current = content
  }, [content])

  // 同步 prevChapterRef 和 selectedChapterRef
  useEffect(() =>
  {
    if (selectedChapter)
    {
      prevChapterRef.current = selectedChapter
      selectedChapterRef.current = selectedChapter
    }
  }, [selectedChapter])

  useEffect(() =>
  {
    const fetchChapters = async () =>
    {
      try
      {
        const data = await chapterOutlinesApi.list(projectId)
        setChapters(data)
        if (data.length > 0)
        {
          setSelectedChapter(data[0])
        }
      }
      catch (err)
      {
        console.error('Failed to fetch chapters:', err)
      }
      finally
      {
        setLoading(false)
      }
    }
    fetchChapters()
  }, [projectId, knowledgeVersion])

  const formatContentAsHtml = (rawContent: string): string =>
  {
    if (!rawContent) return ''
    if (rawContent.includes('<p>')) return rawContent
    return rawContent
      .split('\n')
      .filter(p => p.trim())
      .map(p => `<p>${p}</p>`)
      .join('')
  }

  // 加载 KB 状态
  useEffect(() =>
  {
    const fetchKbStatus = async () =>
    {
      try
      {
        const data = await knowledgeStatusApi.get(projectId, selectedChapter?.chapter_number)
        setKbStatus({ blocked: data.blocked || [], warnings: data.warnings || [] })
      }
      catch (e)
      {
        console.error('Failed to fetch KB status:', e)
      }
    }
    fetchKbStatus()
  }, [projectId, selectedChapter?.chapter_number])

  // 自动保存核心逻辑（章节不存在时自动创建）
  const doSave = useCallback(async (chapterNumber: number, text: string) =>
  {
    setSaveStatus('saving')
    try
    {
      await chaptersApi.update(projectId, chapterNumber, { content: text })
      setSaveStatus('saved')
    }
    catch (e: any)
    {
      // 章节记录不存在，先创建再保存
      if (e?.status === 404 || e?.response?.status === 404)
      {
        try
        {
          await chaptersApi.create(projectId, chapterNumber)
          await chaptersApi.update(projectId, chapterNumber, { content: text })
          setSaveStatus('saved')
          return
        }
        catch
        {
          // 创建也失败，走正常错误流程
        }
      }
      console.error('Auto-save failed:', e)
      setSaveStatus('error')
    }
  }, [projectId])

  // 手动保存（重试用）
  const handleManualSave = useCallback(async () =>
  {
    if (!selectedChapter) return
    await doSave(selectedChapter.chapter_number, contentRef.current)
  }, [selectedChapter, doSave])

  // 防抖自动保存
  const handleContentChange = useCallback((newContent: string) =>
  {
    setContent(newContent)
    contentRef.current = newContent

    if (saveTimeoutRef.current)
    {
      clearTimeout(saveTimeoutRef.current)
    }

    saveTimeoutRef.current = setTimeout(async () =>
    {
      const ch = selectedChapterRef.current
      if (!ch) return
      await doSave(ch.chapter_number, newContent)
    }, 2000)
  }, [doSave])

  // 切换章节时自动保存旧章节 + 加载新章节
  useEffect(() =>
  {
    if (!selectedChapter) return

    // 保存旧章节内容
    const prevChapter = prevChapterRef.current
    const currentContent = contentRef.current
    if (prevChapter && currentContent && prevChapter.id !== selectedChapter.id)
    {
      chaptersApi.update(projectId, prevChapter.chapter_number, { content: currentContent }).catch(e =>
      {
        console.error('Save on chapter switch failed:', e)
      })
    }

    // 清理待执行的防抖保存
    if (saveTimeoutRef.current)
    {
      clearTimeout(saveTimeoutRef.current)
    }

    const loadContent = async () =>
    {
      setLoadingContent(true)
      try
      {
        const chapter = await chaptersApi.get(projectId, selectedChapter.chapter_number)
        const html = formatContentAsHtml(chapter.content || '')
        setContent(html)
        contentRef.current = html
        setSaveStatus('saved')
      }
      catch
      {
        setContent('')
        contentRef.current = ''
        setSaveStatus('saved')
      }
      finally
      {
        setLoadingContent(false)
      }
    }
    loadContent()
  }, [projectId, selectedChapter?.id])

  // 离开页面时自动保存
  useEffect(() =>
  {
    const handleBeforeUnload = () =>
    {
      const currentContent = contentRef.current
      if (!currentContent || !selectedChapter) return

      if (saveTimeoutRef.current)
      {
        clearTimeout(saveTimeoutRef.current)
      }

      const url = `/api/projects/${projectId}/chapters/${selectedChapter.chapter_number}`
      const payload = JSON.stringify({ content: currentContent })

      // 使用 fetch+keepalive 替代 sendBeacon（sendBeacon 无法设置 Authorization header）
      const token = localStorage.getItem('token')
      fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': 'Basic ' + btoa(token + ':') } : {}),
        },
        body: payload,
        keepalive: true,
      }).catch(() =>
      {
        // 页面关闭时忽略网络错误
      })
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [projectId, selectedChapter])

  /** 更新大纲单个字段 */
  const handleOutlineUpdate = useCallback(async (field: string, value: string | object[]) =>
  {
    if (!selectedChapter) return
    try
    {
      const update: ChapterOutlineUpdate = { [field]: value }
      await chapterOutlinesApi.update(projectId, selectedChapter.chapter_number, update)
      setChapters(prev => prev.map(c =>
        c.id === selectedChapter.id ? { ...c, [field]: value } : c
      ))
      setSelectedChapter(prev => prev ? { ...prev, [field]: value } : prev)
    }
    catch
    {
      toast.error('大纲更新失败')
    }
  }, [selectedChapter, projectId])

  /** 确认大纲 */
  const handleConfirmOutline = useCallback(async () =>
  {
    if (!selectedChapter) return
    try
    {
      await chapterOutlinesApi.confirm(projectId, selectedChapter.chapter_number)
      setChapters(prev => prev.map(c =>
        c.id === selectedChapter.id ? { ...c, confirmed: true } : c
      ))
      setSelectedChapter(prev => prev ? { ...prev, confirmed: true } : prev)
      setOutlineCollapsed(true)
      toast.success('大纲已确认')
    }
    catch
    {
      toast.error('确认失败')
    }
  }, [selectedChapter, projectId])

  /** 重新规划 */
  const handleReplan = useCallback(() =>
  {
    if (!selectedChapter) return
    const msg = `重新规划第${selectedChapter.chapter_number}章大纲`
    toggleAiSidebar()
    toast.info('请在右侧 Agent 对话中输入重新规划请求', { description: msg })
  }, [selectedChapter, toggleAiSidebar])

  const navigateChapter = (direction: 'prev' | 'next') =>
  {
    if (!selectedChapter) return
    const currentIndex = chapters.findIndex(c => c.id === selectedChapter.id)
    if (direction === 'prev' && currentIndex > 0)
    {
      setSelectedChapter(chapters[currentIndex - 1])
    }
    else if (direction === 'next' && currentIndex < chapters.length - 1)
    {
      setSelectedChapter(chapters[currentIndex + 1])
    }
  }

  const wordCount = useMemo(() => getWordCount(content), [content])
  const writtenCount = chapters.filter(c => c.has_content).length

  /** 章节列表状态标识 */
  const getChapterStatusIcon = (chapter: ChapterOutline) =>
  {
    if (chapter.has_content)
    {
      return <span className="text-[10px] text-green-500 flex-shrink-0">✓</span>
    }
    if (chapter.confirmed)
    {
      return <span className="text-[10px] text-blue-500 flex-shrink-0">●</span>
    }
    if (chapter.plot)
    {
      return <span className="text-[10px] text-amber-500 flex-shrink-0">●</span>
    }
    return <span className="text-[10px] text-gray-300 flex-shrink-0">○</span>
  }

  /** 折叠侧边栏章节按钮状态 */
  const getChapterButtonStyle = (chapter: ChapterOutline) =>
  {
    if (chapter.has_content) return 'text-green-600'
    if (chapter.confirmed) return 'text-blue-500'
    if (chapter.plot) return 'text-amber-500'
    return 'text-muted-foreground'
  }

  if (loading)
  {
    return (
      <div className="flex h-full">
        <div className="w-40 border-r bg-white">
          <ChapterListSkeleton />
        </div>
        <div className="flex-1">
          <EditorSkeleton />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* 左侧章节列表 */}
      <div className={`border-r bg-white transition-all duration-300 ${sidebarCollapsed ? 'w-10' : 'w-40'}`}>
        {!sidebarCollapsed ? (
          <>
            <div className="p-2.5 border-b flex items-center justify-between">
              <span className="text-xs font-medium">章节 ({chapters.length})</span>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="text-muted-foreground hover:text-foreground"
                title="折叠侧边栏"
              >
                <PanelLeftClose className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="overflow-auto" style={{ height: 'calc(100% - 80px)' }}>
              {chapters.map((chapter) =>
              {
                const isActive = selectedChapter?.id === chapter.id

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                      isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground text-[10px] min-w-[14px]">{chapter.chapter_number}.</span>
                      <span className="truncate flex-1">{chapter.title || '未命名'}</span>
                      {getChapterStatusIcon(chapter)}
                    </div>
                  </button>
                )
              })}
            </div>
            <div className="border-t p-2">
              <div className="text-[10px] text-muted-foreground text-center">
                已写 {writtenCount}/{chapters.length} 章
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center py-3 gap-2">
            <button
              onClick={() => setSidebarCollapsed(false)}
              className="text-muted-foreground hover:text-foreground"
              title="展开侧边栏"
            >
              <PanelLeft className="h-3.5 w-3.5" />
            </button>
            <div className="flex flex-col items-center gap-1">
              {chapters.map((chapter) =>
              {
                const isActive = selectedChapter?.id === chapter.id

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-6 h-6 rounded flex items-center justify-center text-[10px] transition-colors ${
                      isActive ? 'bg-primary/20 text-primary font-medium' : `${getChapterButtonStyle(chapter)} hover:bg-muted`
                    }`}
                    title={chapter.title || `第${chapter.chapter_number}章`}
                  >
                    {chapter.has_content ? '✓' : chapter.chapter_number}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* 中间写作区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-6 overflow-auto">
          {selectedChapter ? (
            <div className="max-w-3xl mx-auto">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold">{selectedChapter.title || `第 ${selectedChapter.chapter_number} 章`}</h2>
                <div className="flex gap-2 items-center">
                  <SaveStatusIndicator status={saveStatus} onRetry={handleManualSave} />
                </div>
              </div>

              {/* 章节大纲面板 */}
              {selectedChapter.plot && (
                <div className={`mb-4 rounded-lg border p-3 ${selectedChapter.confirmed ? 'border-solid border-green-200 bg-green-50/30' : 'border-dashed border-amber-300 bg-amber-50/30'}`}>
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setOutlineCollapsed(!outlineCollapsed)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">本章大纲</span>
                      {selectedChapter.confirmed ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">已确认</span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">待确认</span>
                      )}
                    </div>
                    {outlineCollapsed ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />}
                  </div>

                  {!outlineCollapsed && (
                    <div className="mt-2 space-y-0.5">
                      {/* 基础规划 */}
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 mt-1">基础规划</div>
                      <EditableField label="场景" value={selectedChapter.scene} onSave={(v) => handleOutlineUpdate('scene', v)} placeholder="场景设定" />
                      <EditableField label="人物" value={selectedChapter.characters} onSave={(v) => handleOutlineUpdate('characters', v)} placeholder="出场人物" />
                      <EditableField label="情节" value={selectedChapter.plot} onSave={(v) => handleOutlineUpdate('plot', v)} placeholder="情节要点" />
                      <EditableField label="冲突" value={selectedChapter.conflict} onSave={(v) => handleOutlineUpdate('conflict', v)} placeholder="主要冲突" />
                      <EditableField label="转折" value={selectedChapter.turning_point} onSave={(v) => handleOutlineUpdate('turning_point', v)} placeholder="转折点" />
                      <EditableField label="悬念" value={selectedChapter.hook} onSave={(v) => handleOutlineUpdate('hook', v)} placeholder="悬念钩子" />
                      <EditableField label="过渡" value={selectedChapter.transition} onSave={(v) => handleOutlineUpdate('transition', v)} placeholder="过渡衔接" />
                      <EditableField label="结尾" value={selectedChapter.ending} onSave={(v) => handleOutlineUpdate('ending', v)} placeholder="结尾描述" />

                      {/* 写作指导 */}
                      <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 mt-2 pt-1 border-t">写作指导</div>
                      <EditableField label="开场状态" value={selectedChapter.opening_state} onSave={(v) => handleOutlineUpdate('opening_state', v)} placeholder="角色/局面状态" />
                      <EditableField label="情绪弧线" value={selectedChapter.emotional_arc} onSave={(v) => handleOutlineUpdate('emotional_arc', v)} placeholder="如：压抑→紧张→爆发" />
                      <EditableField label="节奏" value={selectedChapter.pacing_note} onSave={(v) => handleOutlineUpdate('pacing_note', v)} placeholder="如：前慢后快" />

                      {/* 核心场景 */}
                      {selectedChapter.key_scenes && selectedChapter.key_scenes.length > 0 && (
                        <div className="mt-1">
                          <span className="text-[10px] text-muted-foreground">核心场景：</span>
                          <div className="mt-0.5 space-y-0.5">
                            {selectedChapter.key_scenes.map((scene, idx) => (
                              <div key={idx} className="text-xs pl-2">
                                <span className="text-muted-foreground">{scene.seq}.</span> {scene.desc}
                                {scene.mood && <span className="text-muted-foreground ml-1">（{scene.mood}）</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 操作按钮 */}
                      <div className="flex gap-2 mt-3 pt-2 border-t">
                        {!selectedChapter.confirmed && (
                          <Button size="sm" variant="default" onClick={handleConfirmOutline} className="h-6 text-[10px]">
                            <Check className="h-3 w-3 mr-1" />
                            确认大纲
                          </Button>
                        )}
                        <Button size="sm" variant="outline" onClick={handleReplan} className="h-6 text-[10px]">
                          <RefreshCw className="h-3 w-3 mr-1" />
                          重新规划
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 无大纲提示 */}
              {!selectedChapter.plot && (
                <div className="mb-4 rounded-lg border border-dashed border-gray-200 bg-gray-50/30 p-3">
                  <div className="text-xs text-muted-foreground text-center">
                    尚未规划本章，点击
                    <button className="text-primary underline mx-0.5" onClick={handleReplan}>重新规划</button>
                    或通过 Agent 对话生成
                  </div>
                </div>
              )}

              {/* 章节点确认卡片 */}
              {showChapterNode && chapterNode && (
                <div className="mb-4">
                  <ChapterNodePanel
                    node={chapterNode}
                    onConfirm={() => { setShowChapterNode(false) }}
                    onReject={() => setShowChapterNode(false)}
                    onEdit={(updated) => setChapterNode(updated)}
                  />
                </div>
              )}
              {loadingContent ? (
                <EditorSkeleton />
              ) : (
                <TipTapEditor
                  key={selectedChapter?.id}
                  content={content}
                  onChange={handleContentChange}
                  placeholder="开始写作..."
                />
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
              <p>选择章节开始写作</p>
            </div>
          )}
        </div>

        {/* 底部状态栏 */}
        <div className="border-t p-3 flex items-center justify-between bg-white">
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>第 {selectedChapter?.chapter_number || 1} 章 / {chapters.length} 章</span>
            <span className="border-l pl-4">字数 {wordCount.toLocaleString()}</span>
            {kbStatus.blocked.length > 0 && (
              <span className="border-l pl-4 text-red-500 font-medium">
                ⚠ 缺失: {kbStatus.blocked.map(b =>
                {
                  const typeMap: Record<string, string> = {
                    'character_missing': '角色',
                    'world_setting_missing': '世界观',
                    'outline_unconfirmed': '大纲确认',
                    'chapter_outline_missing': '章节大纲',
                  }
                  return typeMap[b.type] || b.type
                }).join(' · ')}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-[10px]">
              <KnowledgeStatusItem label="角色" ok={!kbStatus.blocked.find(b => b.type === 'character_missing')} />
              <KnowledgeStatusItem label="世界观" ok={!kbStatus.blocked.find(b => b.type === 'world_setting_missing')} />
              <KnowledgeStatusItem label="伏笔" ok={!kbStatus.warnings.find(w => w.type === 'foreshadowing_empty')} />
              <KnowledgeStatusItem label="风格" ok={!kbStatus.warnings.find(w => w.type === 'style_constraints_missing')} />
              <KnowledgeStatusItem label="情节块" ok={!kbStatus.warnings.find(w => w.type === 'plot_block_empty')} />
              <KnowledgeStatusItem label="时间线" ok={!kbStatus.warnings.find(w => w.type === 'timeline_empty')} />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => navigateChapter('prev')}>
                <ChevronLeft className="h-4 w-4 mr-1" />
                上一章
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigateChapter('next')}>
                下一章
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}
