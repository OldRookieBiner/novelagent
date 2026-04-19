import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  INSPIRATION_OPTIONS,
  saveInspirationDraft,
  loadInspirationDraft,
  clearInspirationDraft,
  type InspirationData,
} from '@/lib/inspiration'

interface InspirationFormProps {
  initialData?: Partial<InspirationData>
  onSubmit: (data: InspirationData) => void
}

export default function InspirationForm({ initialData, onSubmit }: InspirationFormProps) {
  // 优先使用传入的 initialData，其次使用 localStorage 草稿
  const [novelType, setNovelType] = useState(
    initialData?.novelType || ''
  )
  const [novelLength, setNovelLength] = useState(
    initialData?.novelLength || ''
  )
  const [customChapterCount, setCustomChapterCount] = useState<number | undefined>(
    initialData?.customChapterCount
  )
  const [targetWords, setTargetWords] = useState(
    initialData?.targetWords || ''
  )
  const [customTargetWords, setCustomTargetWords] = useState<number | undefined>(
    initialData?.customTargetWords
  )
  const [coreTheme, setCoreTheme] = useState(
    initialData?.coreTheme || ''
  )
  const [worldSetting, setWorldSetting] = useState(
    initialData?.worldSetting || ''
  )
  const [customWorldSetting, setCustomWorldSetting] = useState(
    initialData?.customWorldSetting || ''
  )
  const [protagonist, setProtagonist] = useState(
    initialData?.protagonist || ''
  )
  const [customProtagonist, setCustomProtagonist] = useState(
    initialData?.customProtagonist || ''
  )
  const [stylePreference, setStylePreference] = useState(
    initialData?.stylePreference || ''
  )

  const [errors, setErrors] = useState<Record<string, string>>({})

  // 如果没有 initialData，尝试从 localStorage 加载草稿
  useEffect(() => {
    if (!initialData || Object.keys(initialData).length === 0) {
      const draft = loadInspirationDraft()
      if (draft) {
        if (draft.novelType) setNovelType(draft.novelType)
        if (draft.novelLength) setNovelLength(draft.novelLength)
        if (draft.customChapterCount) setCustomChapterCount(draft.customChapterCount)
        if (draft.targetWords) setTargetWords(draft.targetWords)
        if (draft.customTargetWords) setCustomTargetWords(draft.customTargetWords)
        if (draft.coreTheme) setCoreTheme(draft.coreTheme)
        if (draft.worldSetting) setWorldSetting(draft.worldSetting)
        if (draft.customWorldSetting) setCustomWorldSetting(draft.customWorldSetting)
        if (draft.protagonist) setProtagonist(draft.protagonist)
        if (draft.customProtagonist) setCustomProtagonist(draft.customProtagonist)
        if (draft.stylePreference) setStylePreference(draft.stylePreference)
      }
    }
  }, [initialData])

  // 自动保存草稿
  useEffect(() => {
    const data: InspirationData = {
      novelType,
      novelLength,
      customChapterCount,
      targetWords,
      customTargetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      protagonist,
      customProtagonist,
      stylePreference,
    }
    // 只有有数据时才保存
    if (novelType || novelLength || targetWords || coreTheme) {
      saveInspirationDraft(data)
    }
  }, [novelType, novelLength, customChapterCount, targetWords, customTargetWords, coreTheme, worldSetting, customWorldSetting, protagonist, customProtagonist, stylePreference])

  const handleSubmit = () => {
    // 验证必填项
    const newErrors: Record<string, string> = {}
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!novelLength) newErrors.novelLength = '请选择小说篇幅'
    if (!targetWords) newErrors.targetWords = '请选择目标字数'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    const data: InspirationData = {
      novelType,
      novelLength,
      customChapterCount,
      targetWords,
      customTargetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      protagonist,
      customProtagonist,
      stylePreference,
    }

    // 提交后清除草稿
    clearInspirationDraft()
    onSubmit(data)
  }

  const showCustomChapter = novelLength === 'custom'
  const showCustomWords = targetWords === 'custom'
  const showCustomWorld = worldSetting === 'custom'
  const showCustomProtagonist = protagonist === 'custom'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 小说类型 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">
            小说类型 <span className="text-red-500">*</span>
          </label>
          <select
            className={`w-full h-10 px-3 rounded-md border bg-background ${
              errors.novelType ? 'border-red-500' : 'border-input'
            }`}
            value={novelType}
            onChange={(e) => {
              setNovelType(e.target.value)
              if (errors.novelType) setErrors({ ...errors, novelType: '' })
            }}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.novelType && <p className="text-red-500 text-xs mt-1">{errors.novelType}</p>}
        </div>

        {/* 小说篇幅 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">
            小说篇幅 <span className="text-red-500">*</span>
          </label>
          <select
            className={`w-full h-10 px-3 rounded-md border bg-background ${
              errors.novelLength ? 'border-red-500' : 'border-input'
            }`}
            value={novelLength}
            onChange={(e) => {
              setNovelLength(e.target.value)
              if (errors.novelLength) setErrors({ ...errors, novelLength: '' })
            }}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.novelLength.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
                {opt.chapters ? ` (${opt.chapters}章)` : ''}
              </option>
            ))}
          </select>
          {errors.novelLength && <p className="text-red-500 text-xs mt-1">{errors.novelLength}</p>}
        </div>

        {/* 目标字数 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">
            目标字数 <span className="text-red-500">*</span>
          </label>
          <select
            className={`w-full h-10 px-3 rounded-md border bg-background ${
              errors.targetWords ? 'border-red-500' : 'border-input'
            }`}
            value={targetWords}
            onChange={(e) => {
              setTargetWords(e.target.value)
              if (errors.targetWords) setErrors({ ...errors, targetWords: '' })
            }}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.targetWords.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.targetWords && <p className="text-red-500 text-xs mt-1">{errors.targetWords}</p>}
        </div>

        {/* 自定义章节数 */}
        {showCustomChapter && (
          <div>
            <label className="block text-sm font-medium mb-1.5">自定义章节数</label>
            <Input
              type="number"
              value={customChapterCount || ''}
              onChange={(e) => setCustomChapterCount(parseInt(e.target.value) || undefined)}
              placeholder="输入章节数"
            />
          </div>
        )}

        {/* 自定义字数 */}
        {showCustomWords && (
          <div>
            <label className="block text-sm font-medium mb-1.5">自定义字数（万字）</label>
            <Input
              type="number"
              value={customTargetWords || ''}
              onChange={(e) => setCustomTargetWords(parseInt(e.target.value) || undefined)}
              placeholder="输入目标字数"
            />
          </div>
        )}

        {/* 核心主题 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">
            核心主题 <span className="text-red-500">*</span>
          </label>
          <select
            className={`w-full h-10 px-3 rounded-md border bg-background ${
              errors.coreTheme ? 'border-red-500' : 'border-input'
            }`}
            value={coreTheme}
            onChange={(e) => {
              setCoreTheme(e.target.value)
              if (errors.coreTheme) setErrors({ ...errors, coreTheme: '' })
            }}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {errors.coreTheme && <p className="text-red-500 text-xs mt-1">{errors.coreTheme}</p>}
        </div>

        {/* 世界观设定 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">世界观设定</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={worldSetting}
            onChange={(e) => setWorldSetting(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 自定义世界观 */}
        {showCustomWorld && (
          <div>
            <label className="block text-sm font-medium mb-1.5">自定义世界观</label>
            <Input
              type="text"
              value={customWorldSetting || ''}
              onChange={(e) => setCustomWorldSetting(e.target.value)}
              placeholder="输入世界观设定"
            />
          </div>
        )}

        {/* 主角设定 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">主角设定</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={protagonist}
            onChange={(e) => setProtagonist(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.protagonistTypes.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* 自定义主角 */}
        {showCustomProtagonist && (
          <div>
            <label className="block text-sm font-medium mb-1.5">自定义主角</label>
            <Input
              type="text"
              value={customProtagonist || ''}
              onChange={(e) => setCustomProtagonist(e.target.value)}
              placeholder="输入主角设定"
            />
          </div>
        )}

        {/* 风格偏好 */}
        <div>
          <label className="block text-sm font-medium mb-1.5">风格偏好</label>
          <select
            className="w-full h-10 px-3 rounded-md border border-input bg-background"
            value={stylePreference}
            onChange={(e) => setStylePreference(e.target.value)}
          >
            <option value="">请选择</option>
            {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4">
        <Button
          variant="outline"
          onClick={() => {
            clearInspirationDraft()
            setNovelType('')
            setNovelLength('')
            setCustomChapterCount(undefined)
            setTargetWords('')
            setCustomTargetWords(undefined)
            setCoreTheme('')
            setWorldSetting('')
            setCustomWorldSetting('')
            setProtagonist('')
            setCustomProtagonist('')
            setStylePreference('')
          }}
        >
          清空表单
        </Button>
        <Button onClick={handleSubmit}>生成灵感模板</Button>
      </div>
    </div>
  )
}
