# Workbench Inspiration & Writing Editor Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor InspirationPanel with real-time Prompt template preview (left-right split layout) and upgrade WritingPanel from textarea to TipTap rich text editor.

**Architecture:** Two independent feature modules. InspirationPanel gets a companion Markdown template pane that syncs in real-time with form selections via generateInspirationTemplate(). WritingPanel replaces native textarea with the existing TipTapEditor component, reusing its content sync mechanism.

**Tech Stack:** React 18, Zustand, TipTap 2.2.x, Tailwind CSS, SSE streaming

---

### File Structure

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | Modify | Rewrite as left-right split layout with real-time Prompt template |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | Modify | Replace textarea with TipTapEditor component |
| `frontend/src/stores/workbenchStore.ts` | No change needed | Already has setActiveTab/setActiveMenuItem |
| `frontend/src/lib/inspiration.ts` | No change needed | generateInspirationTemplate() already exists |
| `frontend/src/components/common/TipTapEditor.tsx` | No change needed | Already exists, reuse as-is |

---

### Task 1: Refactor InspirationPanel — Left-Right Split with Real-time Prompt Template

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: Remove right completeness panel and add template tracking state**

Replace the right panel area with new state variables for the template preview. Start from the top of the file, replace the `saving` state and completeness/suggestions logic with template-related state:

```tsx
// frontend/src/components/workbench/planning/InspirationPanel.tsx

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Lightbulb, RotateCcw, ArrowRight, Check } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  INSPIRATION_OPTIONS,
  COMMON_OPTIONS,
  MALE_OPTIONS,
  FEMALE_OPTIONS,
  generateInspirationTemplate,
  saveInspirationDraft,
  loadInspirationDraft,
  type InspirationData,
} from '@/lib/inspiration'
import { collectedInfoApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { toast } from 'sonner'
```

Note: Removed `Save` icon import, added `RotateCcw`, `ArrowRight`, `Check`. Added `useMemo`, `useCallback` imports. Added `Textarea`, `generateInspirationTemplate`, `useWorkbenchStore` imports.

- [ ] **Step 2: Add template state variables and remove obsolete state**

Replace the `saving` and `errors` state declarations (around line 87-89 of the current file) and the `calculateCompleteness`/`getSuggestions` functions with:

```tsx
  // 模板相关状态
  const [template, setTemplate] = useState('')
  const [templateManuallyEdited, setTemplateManuallyEdited] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const [errors, setErrors] = useState<Record<string, string>>({})

  const { setActiveTab, setActiveMenuItem } = useWorkbenchStore()
```

Remove the entire `calculateCompleteness` function (lines 92-123) and `getSuggestions` function (lines 126-137).

- [ ] **Step 3: Build the full form data object as a memoized value**

Insert after the state declarations and before the `useEffect` blocks:

```tsx
  // 构建完整的表单数据对象（用于生成模板）
  const formData = useMemo((): InspirationData => ({
    novelType,
    targetWords,
    coreTheme,
    worldSetting,
    customWorldSetting,
    era,
    genre,
    customGenre,
    maleLead,
    customMaleLead,
    femaleLead,
    customFemaleLead,
    stylePreference,
    targetReader,
    wordsPerChapter,
    customWordsPerChapter,
    narrative,
    goldFinger,
    customGoldFinger,
  }), [novelType, targetWords, coreTheme, worldSetting, customWorldSetting, era, genre, customGenre, maleLead, customMaleLead, femaleLead, customFemaleLead, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])
```

- [ ] **Step 4: Add real-time template generation effect**

Insert after the auto-save draft `useEffect` (replace the existing auto-save effect at lines 187-214):

```tsx
  // 实时更新模板（用户未手动编辑时）
  useEffect(() =>
  {
    if (!templateManuallyEdited)
    {
      const generated = generateInspirationTemplate(formData)
      setTemplate(generated)
    }
  }, [formData, templateManuallyEdited])

  // 自动保存草稿
  useEffect(() =>
  {
    const data: InspirationData = {
      novelType,
      targetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      era,
      genre,
      customGenre,
      maleLead,
      customMaleLead,
      femaleLead,
      customFemaleLead,
      stylePreference,
      targetReader,
      wordsPerChapter,
      customWordsPerChapter,
      narrative,
      goldFinger,
      customGoldFinger,
    }
    if (novelType || targetWords || coreTheme || targetReader)
    {
      saveInspirationDraft(data)
    }
  }, [novelType, targetWords, coreTheme, worldSetting, customWorldSetting, era, genre, customGenre, maleLead, customMaleLead, femaleLead, customFemaleLead, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])
```

- [ ] **Step 5: Add template handling functions (handleTemplateChange, handleResetTemplate)**

Insert before the `handleSaveToServer` function:

```tsx
  // 用户手动编辑模板
  const handleTemplateChange = useCallback((value: string) =>
  {
    setTemplate(value)
    setTemplateManuallyEdited(true)
  }, [])

  // 重置模板（恢复自动同步）
  const handleResetTemplate = useCallback(() =>
  {
    setTemplate(generateInspirationTemplate(formData))
    setTemplateManuallyEdited(false)
  }, [formData])
```

- [ ] **Step 6: Replace handleSaveToServer with handleConfirm function**

Replace the entire `handleSaveToServer` function (lines 220-274) with:

```tsx
  // 确认灵感，生成大纲
  const handleConfirm = async () =>
  {
    // 验证必填项
    const newErrors: Record<string, string> = {}
    if (!targetReader) newErrors.targetReader = '请选择目标读者'
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!targetWords) newErrors.targetWords = '请输入目标字数'
    else if (targetWords < 10000) newErrors.targetWords = '目标字数不能少于1万字'
    if (!wordsPerChapter) newErrors.wordsPerChapter = '请选择每章字数'
    if (!era) newErrors.era = '请选择年代'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'
    if (targetReader === 'male' && !maleLead) newErrors.maleLead = '请选择男主人设'
    if (targetReader === 'female' && !femaleLead) newErrors.femaleLead = '请选择女主人设'

    if (Object.keys(newErrors).length > 0)
    {
      setErrors(newErrors)
      toast.error('请完善必填信息')
      return
    }

    setConfirming(true)
    try
    {
      // 构建 collected_info 数据
      const collectedInfoData: Record<string, unknown> = {
        inspiration_template: template,
      }

      if (novelType) collectedInfoData.novelType = novelType
      if (targetWords) collectedInfoData.targetWords = targetWords
      if (coreTheme) collectedInfoData.coreTheme = coreTheme
      if (worldSetting)
      {
        collectedInfoData.worldSetting = worldSetting
        if (customWorldSetting) collectedInfoData.customWorldSetting = customWorldSetting
      }
      if (targetReader) collectedInfoData.targetReader = targetReader
      if (wordsPerChapter)
      {
        collectedInfoData.wordsPerChapter = wordsPerChapter
        if (customWordsPerChapter) collectedInfoData.customWordsPerChapter = customWordsPerChapter
      }
      if (narrative) collectedInfoData.narrative = narrative
      if (stylePreference) collectedInfoData.stylePreference = stylePreference
      if (era) collectedInfoData.era = era

      if (targetReader === 'male')
      {
        const lead = maleLead === 'custom' ? customMaleLead : maleLead
        if (lead) collectedInfoData.protagonist = lead
        const genreVal = genre === 'custom' ? customGenre : genre
        if (genreVal) collectedInfoData.genre = genreVal
        const gf = goldFinger === 'custom' ? customGoldFinger : goldFinger
        if (gf) collectedInfoData.goldFinger = gf
      }
      else if (targetReader === 'female')
      {
        const lead = femaleLead === 'custom' ? customFemaleLead : femaleLead
        if (lead) collectedInfoData.protagonist = lead
      }

      await collectedInfoApi.update(projectId, collectedInfoData)
      toast.success('灵感已确认')

      // 切换到创作 Tab 的小说大纲
      setActiveTab('creation')
      setActiveMenuItem('outline')
    }
    catch (err)
    {
      console.error('Failed to confirm inspiration:', err)
      toast.error('保存失败')
    }
    finally
    {
      setConfirming(false)
    }
  }
```

Remove the `completeness` and `suggestions` calls from the render section (lines 216-217 in current file) since they no longer exist.

- [ ] **Step 7: Rewrite the JSX return — left-right split layout**

Replace the entire return block (from line 277 onward) with the new layout. The header section (title + button) stays, the form fields stay on the left, and the right side becomes the Prompt template preview:

```tsx
  return (
    <div className="flex h-full">
      {/* 左侧：表单选择区 */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between px-6 py-3 border-b bg-white">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            灵感采集
          </h2>
        </div>
        <div className="flex-1 p-6 overflow-auto">
          <div className="max-w-2xl space-y-6">
            {/* 目标读者 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">
                  目标读者 <span className="text-red-500">*</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 max-w-md">
                  {INSPIRATION_OPTIONS.targetReader.map((opt) => (
                    <div
                      key={opt.value}
                      onClick={() =>
                      {
                        setTargetReader(opt.value)
                        if (errors.targetReader) setErrors({ ...errors, targetReader: '' })
                      }}
                      className={`border-2 rounded-lg p-4 text-center cursor-pointer transition-all ${
                        targetReader === opt.value
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-gray-200 hover:border-primary/50 hover:shadow-sm'
                      }`}
                    >
                      <div className="text-2xl mb-1">{TARGET_READER_ICONS[opt.value]}</div>
                      <div className="font-medium">{opt.label}</div>
                      <div className="text-xs text-muted-foreground mt-1">{TARGET_READER_DESC[opt.value]}</div>
                    </div>
                  ))}
                </div>
                {errors.targetReader && <p className="text-red-500 text-xs mt-2">{errors.targetReader}</p>}
              </CardContent>
            </Card>

            {/* 基本设定 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  基本设定
                  <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">必填</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 小说类型 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    小说类型 <span className="text-red-500">*</span>
                  </label>
                  <div className="grid grid-cols-6 gap-2">
                    {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
                      <div
                        key={opt.value}
                        onClick={() =>
                        {
                          setNovelType(opt.value)
                          if (errors.novelType) setErrors({ ...errors, novelType: '' })
                        }}
                        className={`border-2 rounded-lg p-2 text-center cursor-pointer transition-all ${
                          novelType === opt.value
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        <div className="text-base mb-0.5">{NOVEL_TYPE_ICONS[opt.value]}</div>
                        <div className="text-xs font-medium">{opt.label}</div>
                      </div>
                    ))}
                  </div>
                  {errors.novelType && <p className="text-red-500 text-xs mt-2">{errors.novelType}</p>}
                </div>

                {/* 年代 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    年代 <span className="text-red-500">*</span>
                  </label>
                  <div className="grid grid-cols-4 gap-2 max-w-lg">
                    {COMMON_OPTIONS.era.map((opt) => (
                      <div
                        key={opt.value}
                        onClick={() =>
                        {
                          setEra(opt.value)
                          if (errors.era) setErrors({ ...errors, era: '' })
                        }}
                        className={`border-2 rounded-lg p-2 text-center cursor-pointer transition-all ${
                          era === opt.value
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        <div className="text-base mb-0.5">{ERA_ICONS[opt.value]}</div>
                        <div className="text-xs font-medium">{opt.label}</div>
                      </div>
                    ))}
                  </div>
                  {errors.era && <p className="text-red-500 text-xs mt-2">{errors.era}</p>}
                </div>

                {/* 目标字数、每章字数 */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">
                      目标字数 <span className="text-red-500">*</span>
                    </label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        value={targetWords || ''}
                        onChange={(e) =>
                        {
                          setTargetWords(parseInt(e.target.value) || 0)
                          if (errors.targetWords) setErrors({ ...errors, targetWords: '' })
                        }}
                        placeholder="输入目标字数"
                        className={errors.targetWords ? 'border-red-500' : ''}
                      />
                      <span className="text-sm text-muted-foreground">字</span>
                    </div>
                    {errors.targetWords && <p className="text-red-500 text-xs mt-1">{errors.targetWords}</p>}
                  </div>

                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">
                      每章字数 <span className="text-red-500">*</span>
                    </label>
                    <select
                      className={`w-full h-10 px-3 rounded-md border-2 bg-white text-sm ${errors.wordsPerChapter ? 'border-red-500' : 'border-gray-200'}`}
                      value={wordsPerChapter}
                      onChange={(e) =>
                      {
                        setWordsPerChapter(e.target.value)
                        if (errors.wordsPerChapter) setErrors({ ...errors, wordsPerChapter: '' })
                      }}
                    >
                      <option value="">请选择</option>
                      {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}{opt.desc ? `（${opt.desc}）` : ''}
                        </option>
                      ))}
                    </select>
                    {errors.wordsPerChapter && <p className="text-red-500 text-xs mt-1">{errors.wordsPerChapter}</p>}
                  </div>
                </div>

                {wordsPerChapter === 'custom' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">自定义每章字数</label>
                    <Input
                      type="number"
                      value={customWordsPerChapter || ''}
                      onChange={(e) => setCustomWordsPerChapter(parseInt(e.target.value) || undefined)}
                      placeholder="输入字数"
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 进阶设定 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  进阶设定
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">选填</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 叙事视角 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">叙事视角</label>
                  <div className="flex gap-2">
                    {INSPIRATION_OPTIONS.narrative.map((opt) => (
                      <span
                        key={opt.value}
                        onClick={() => setNarrative(opt.value)}
                        className={`px-4 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                          narrative === opt.value
                            ? 'bg-primary text-white border-primary'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        {opt.label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* 核心主题 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    核心主题 <span className="text-red-500">*</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                      <span
                        key={opt.value}
                        onClick={() =>
                        {
                          setCoreTheme(opt.value)
                          if (errors.coreTheme) setErrors({ ...errors, coreTheme: '' })
                        }}
                        className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                          coreTheme === opt.value
                            ? 'bg-primary text-white border-primary'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {errors.coreTheme && <p className="text-red-500 text-xs mt-2">{errors.coreTheme}</p>}
                </div>

                {/* 世界观设定 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">世界观设定</label>
                  <div className="flex flex-wrap gap-2">
                    {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
                      <span
                        key={opt.value}
                        onClick={() => setWorldSetting(opt.value)}
                        className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                          worldSetting === opt.value
                            ? 'bg-primary text-white border-primary'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {worldSetting === 'custom' && (
                    <Input
                      type="text"
                      value={customWorldSetting || ''}
                      onChange={(e) => setCustomWorldSetting(e.target.value)}
                      placeholder="输入自定义世界观设定"
                      className="mt-2 max-w-md"
                    />
                  )}
                </div>

                {/* 流派（男频专属） */}
                {targetReader === 'male' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">流派</label>
                    <div className="flex flex-wrap gap-2">
                      {MALE_OPTIONS.genre.map((opt) => (
                        <span
                          key={opt.value}
                          onClick={() => setGenre(opt.value)}
                          className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                            genre === opt.value
                              ? 'bg-primary text-white border-primary'
                              : 'border-gray-200 hover:border-primary/50'
                          }`}
                        >
                          {opt.label}
                        </span>
                      ))}
                    </div>
                    {genre === 'custom' && (
                      <Input
                        type="text"
                        value={customGenre || ''}
                        onChange={(e) => setCustomGenre(e.target.value)}
                        placeholder="输入自定义流派"
                        className="mt-2 max-w-md"
                      />
                    )}
                  </div>
                )}

                {/* 男主人设（男频专属） */}
                {targetReader === 'male' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">
                      男主人设 <span className="text-red-500">*</span>
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {MALE_OPTIONS.maleLead.map((opt) => (
                        <span
                          key={opt.value}
                          onClick={() =>
                          {
                            setMaleLead(opt.value)
                            if (errors.maleLead) setErrors({ ...errors, maleLead: '' })
                          }}
                          className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                            maleLead === opt.value
                              ? 'bg-primary text-white border-primary'
                              : 'border-gray-200 hover:border-primary/50'
                          }`}
                        >
                          {opt.label}
                        </span>
                      ))}
                    </div>
                    {maleLead === 'custom' && (
                      <Input
                        type="text"
                        value={customMaleLead || ''}
                        onChange={(e) => setCustomMaleLead(e.target.value)}
                        placeholder="输入自定义男主人设"
                        className="mt-2 max-w-md"
                      />
                    )}
                    {errors.maleLead && <p className="text-red-500 text-xs mt-2">{errors.maleLead}</p>}
                  </div>
                )}

                {/* 女主人设（女频专属） */}
                {targetReader === 'female' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">
                      女主人设 <span className="text-red-500">*</span>
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {FEMALE_OPTIONS.femaleLead.map((opt) => (
                        <span
                          key={opt.value}
                          onClick={() =>
                          {
                            setFemaleLead(opt.value)
                            if (errors.femaleLead) setErrors({ ...errors, femaleLead: '' })
                          }}
                          className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                            femaleLead === opt.value
                              ? 'bg-primary text-white border-primary'
                              : 'border-gray-200 hover:border-primary/50'
                          }`}
                        >
                          {opt.label}
                        </span>
                      ))}
                    </div>
                    {femaleLead === 'custom' && (
                      <Input
                        type="text"
                        value={customFemaleLead || ''}
                        onChange={(e) => setCustomFemaleLead(e.target.value)}
                        placeholder="输入自定义女主人设"
                        className="mt-2 max-w-md"
                      />
                    )}
                    {errors.femaleLead && <p className="text-red-500 text-xs mt-2">{errors.femaleLead}</p>}
                  </div>
                )}

                {/* 未选择目标读者时提示 */}
                {!targetReader && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">主角设定</label>
                    <p className="text-sm text-muted-foreground">请先选择目标读者</p>
                  </div>
                )}

                {/* 金手指设定（男频专属） */}
                {targetReader === 'male' && (
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">金手指设定</label>
                    <div className="flex flex-wrap gap-2">
                      {MALE_OPTIONS.goldFinger.map((opt) => (
                        <span
                          key={opt.value}
                          onClick={() => setGoldFinger(opt.value)}
                          className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                            goldFinger === opt.value
                              ? 'bg-primary text-white border-primary'
                              : 'border-gray-200 hover:border-primary/50'
                          }`}
                        >
                          {opt.label}
                        </span>
                      ))}
                    </div>
                    {goldFinger === 'custom' && (
                      <Input
                        type="text"
                        value={customGoldFinger || ''}
                        onChange={(e) => setCustomGoldFinger(e.target.value)}
                        placeholder="输入自定义金手指设定"
                        className="mt-2 max-w-md"
                      />
                    )}
                  </div>
                )}

                {/* 风格偏好 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">风格偏好</label>
                  <div className="flex flex-wrap gap-2">
                    {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
                      <span
                        key={opt.value}
                        onClick={() => setStylePreference(opt.value)}
                        className={`px-3 py-1.5 rounded-full border-2 text-sm cursor-pointer transition-all ${
                          stylePreference === opt.value
                            ? 'bg-primary text-white border-primary'
                            : 'border-gray-200 hover:border-primary/50'
                        }`}
                      >
                        {opt.label}
                      </span>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 底部：确认按钮 */}
        <div className="border-t bg-white px-6 py-3 flex justify-end">
          <Button onClick={handleConfirm} disabled={confirming}>
            {confirming ? (
              <>保存中...</>
            ) : (
              <>
                <Check className="h-4 w-4 mr-2" />
                确认，生成大纲
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 右侧：Prompt 模板区 */}
      <div className="flex-1 border-l bg-white flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h3 className="text-sm font-medium flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            创作 Prompt
          </h3>
          {templateManuallyEdited && (
            <Button variant="ghost" size="sm" onClick={handleResetTemplate}>
              <RotateCcw className="h-4 w-4 mr-1" />
              重置模板
            </Button>
          )}
        </div>
        {templateManuallyEdited && (
          <div className="px-4 py-2 bg-yellow-50 border-b text-xs text-yellow-700">
            手动编辑模式 — 表单修改不再自动更新模板
          </div>
        )}
        <div className="flex-1 p-4">
          <Textarea
            value={template}
            onChange={(e) => handleTemplateChange(e.target.value)}
            placeholder="选择灵感选项后，此处将自动生成创作 Prompt..."
            className="w-full h-full font-mono text-sm leading-relaxed resize-none border-none shadow-none focus-visible:ring-0"
          />
        </div>
      </div>
    </div>
  )
```

Note: The `TARGET_READER_ICONS`, `TARGET_READER_DESC`, `NOVEL_TYPE_ICONS`, and `ERA_ICONS` constants from the original file (lines 26-58) must remain unchanged at the top of the component file.

- [ ] **Step 8: Commit the InspirationPanel changes**

```bash
cd /opt/project/novelagent
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "feat(workbench): refactor InspirationPanel with left-right split layout and real-time Prompt template preview"
```

---

### Task 2: Upgrade WritingPanel — Textarea to TipTap Editor

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: Import TipTapEditor**

Replace the textarea-related imports at the top of the file. Change imports from `Save, ChevronLeft, ChevronRight, Sparkles, Loader2` to include editor-related icons. Add TipTapEditor import:

```tsx
// frontend/src/components/workbench/creation/WritingPanel.tsx

import { useState, useEffect, useMemo, useRef } from 'react'
import { Save, ChevronLeft, ChevronRight, Sparkles, Loader2, Eye, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { chapterOutlinesApi, chaptersApi } from '@/lib/api'
import { createSSEStream } from '@/lib/sseParser'
import { AIAssistantPanel } from './AIAssistantPanel'
import TipTapEditor from '@/components/common/TipTapEditor'
import type { ChapterOutline, Chapter } from '@/types'
import { toast } from 'sonner'
```

- [ ] **Step 2: Add preview/edit mode state**

Add a `mode` state variable after the existing state declarations in the component. Insert after `abortControllerRef`:

```tsx
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
```

- [ ] **Step 3: Replace the textarea with TipTapEditor and preview div**

In the JSX return, find the textarea element (around lines 294-300 of the current file):

```tsx
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="开始写作..."
                  className="w-full h-[calc(100vh-200px)] p-4 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
```

Replace it with:

```tsx
                {mode === 'edit' ? (
                  <TipTapEditor
                    content={content}
                    onChange={setContent}
                    placeholder="开始写作..."
                  />
                ) : (
                  <div
                    className="w-full h-[calc(100vh-200px)] p-4 border rounded-lg overflow-auto prose max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: content
                        ? content
                        : '<p class="text-muted-foreground">点击 AI 生成按钮开始创作</p>'
                    }}
                  />
                )}
```

- [ ] **Step 4: Add preview/edit toggle button next to the AI Generate button**

In the header section where the AI Generate and Save buttons are (around lines 261-288), add a mode toggle button between the generate and save buttons:

Replace the current button group:

```tsx
                <div className="flex gap-2">
                  {generating ? (
                    <Button size="sm" variant="destructive" onClick={handleCancelGenerate}>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      取消生成
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" onClick={handleGenerate}>
                      <Sparkles className="h-4 w-4 mr-2" />
                      AI 生成
                    </Button>
                  )}
                  <Button size="sm" onClick={handleSave} disabled={saving || generating}>
                    {saving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        保存中
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        保存
                      </>
                    )}
                  </Button>
                </div>
```

With:

```tsx
                <div className="flex gap-2">
                  {generating ? (
                    <Button size="sm" variant="destructive" onClick={handleCancelGenerate}>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      取消生成
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" variant="outline" onClick={handleGenerate}>
                        <Sparkles className="h-4 w-4 mr-2" />
                        AI 生成
                      </Button>
                      {content && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setMode(mode === 'preview' ? 'edit' : 'preview')}
                        >
                          {mode === 'preview' ? (
                            <>
                              <Pencil className="h-4 w-4 mr-2" />
                              编辑
                            </>
                          ) : (
                            <>
                              <Eye className="h-4 w-4 mr-2" />
                              预览
                            </>
                          )}
                        </Button>
                      )}
                    </>
                  )}
                  <Button size="sm" onClick={handleSave} disabled={saving || generating}>
                    {saving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        保存中
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        保存
                      </>
                    )}
                  </Button>
                </div>
```

- [ ] **Step 5: Handle AI-generated content correctly for HTML format**

The SSE streaming callback in `handleGenerate` currently appends raw text strings to `content`. TipTapEditor already handles plain-text-to-HTML conversion in its `useEffect` sync (it detects `/<[a-zA-Z][^>]*>/` and wraps text in `<p>` tags). However, to make streaming feel smooth, accumulate text and send it as HTML:

Modify the `handleGenerate` function (lines 138-197). Replace the entire function body's SSE callback with:

```tsx
  const handleGenerate = async () =>
  {
    if (!selectedChapter) return

    if (!selectedChapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }

    setGenerating(true)
    setContent('')
    setMode('preview')

    const controller = new AbortController()
    abortControllerRef.current = controller
    const accumulated: string[] = []

    try
    {
      await createSSEStream(
        {
          url: `/api/projects/${projectId}/chapters/${selectedChapter.chapter_number}/generate`,
          method: 'POST',
          signal: controller.signal
        },
        (type, data) =>
        {
          if (type === 'done')
          {
            const wordCount = typeof data === 'number' ? data : (data as { word_count?: number })?.word_count
            if (wordCount)
            {
              toast.success(`AI 生成完成，共 ${wordCount} 字`)
            }
            else
            {
              toast.success('AI 生成完成')
            }
          }
          else if (typeof data === 'string')
          {
            accumulated.push(data)
            const fullText = accumulated.join('')
            const html = fullText
              .split('\n')
              .filter(p => p.trim())
              .map(p => `<p>${p}</p>`)
              .join('')
            setContent(html)
          }
        },
        (error) =>
        {
          console.error('Failed to generate:', error)
          toast.error('生成失败')
        }
      )
    }
    finally
    {
      setGenerating(false)
      abortControllerRef.current = null
    }
  }
```

- [ ] **Step 6: Commit the WritingPanel changes**

```bash
cd /opt/project/novelagent
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(workbench): upgrade WritingPanel from textarea to TipTap rich text editor with preview/edit toggle"
```

---

### Task 3: Verification — TypeScript Compilation Check

**Files:**
- No file changes needed. Verification only.

- [ ] **Step 1: Run TypeScript type checking**

```bash
cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -50
```

Expected: No new type errors introduced by our changes. If there are pre-existing errors unrelated to our changes, note them but do not fix.

- [ ] **Step 2: If type errors found, fix them and recheck**

Only fix errors related to our modified files (`InspirationPanel.tsx`, `WritingPanel.tsx`).

- [ ] **Step 3: Commit any type fixes**

```bash
cd /opt/project/novelagent
git add frontend/src/
git commit -m "fix(workbench): resolve TypeScript errors in InspirationPanel and WritingPanel"
```