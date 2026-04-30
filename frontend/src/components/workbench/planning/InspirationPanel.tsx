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

interface InspirationPanelProps
{
  projectId: number
}

// 小说类型图标
const NOVEL_TYPE_ICONS: Record<string, string> = {
  xuanhuan: '⚔️',
  dushi: '🏙️',
  xianxia: '☁️',
  yanqing: '💕',
  lishi: '📜',
  xuanyi: '🔍',
  kehuan: '🚀',
  youxi: '🎮',
  qihuan: '🧙',
  junshi: '🎖️',
  lingyi: '👻',
  jingji: '🏆',
  tongren: '📖',
}

// 年代图标
const ERA_ICONS: Record<string, string> = {
  ancient: '🏛️',
  modern: '🏙️',
  future: '🚀',
  fantasy: '🌐',
}

// 目标读者图标和描述
const TARGET_READER_ICONS: Record<string, string> = {
  male: '👨',
  female: '👩',
}

const TARGET_READER_DESC: Record<string, string> = {
  male: '热血、爽文、升级',
  female: '言情、甜宠、逆袭',
}

export function InspirationPanel({ projectId }: InspirationPanelProps)
{
  // 必填项状态
  const [targetReader, setTargetReader] = useState('')
  const [novelType, setNovelType] = useState('')
  const [targetWords, setTargetWords] = useState<number>(0)
  const [wordsPerChapter, setWordsPerChapter] = useState('')
  const [customWordsPerChapter, setCustomWordsPerChapter] = useState<number | undefined>()
  const [era, setEra] = useState('')

  // 选填项状态
  const [narrative, setNarrative] = useState('')
  const [coreTheme, setCoreTheme] = useState('')
  const [worldSetting, setWorldSetting] = useState('')
  const [customWorldSetting, setCustomWorldSetting] = useState('')
  const [genre, setGenre] = useState('')
  const [customGenre, setCustomGenre] = useState('')
  const [maleLead, setMaleLead] = useState('')
  const [customMaleLead, setCustomMaleLead] = useState('')
  const [femaleLead, setFemaleLead] = useState('')
  const [customFemaleLead, setCustomFemaleLead] = useState('')
  const [goldFinger, setGoldFinger] = useState('')
  const [customGoldFinger, setCustomGoldFinger] = useState('')
  const [stylePreference, setStylePreference] = useState('')

  // 模板相关状态
  const [template, setTemplate] = useState('')
  const [templateManuallyEdited, setTemplateManuallyEdited] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const [errors, setErrors] = useState<Record<string, string>>({})

  const { setActiveTab, setActiveMenuItem } = useWorkbenchStore()

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

  // 实时更新模板（用户未手动编辑时）
  useEffect(() =>
  {
    if (!templateManuallyEdited)
    {
      const generated = generateInspirationTemplate(formData)
      setTemplate(generated)
    }
  }, [formData, templateManuallyEdited])

  // 加载草稿
  useEffect(() =>
  {
    const draft = loadInspirationDraft()
    if (draft)
    {
      if (draft.targetReader) setTargetReader(draft.targetReader)
      if (draft.novelType) setNovelType(draft.novelType)
      if (draft.targetWords) setTargetWords(draft.targetWords)
      if (draft.wordsPerChapter) setWordsPerChapter(draft.wordsPerChapter)
      if (draft.customWordsPerChapter) setCustomWordsPerChapter(draft.customWordsPerChapter)
      if (draft.era) setEra(draft.era)
      if (draft.narrative) setNarrative(draft.narrative)
      if (draft.coreTheme) setCoreTheme(draft.coreTheme)
      if (draft.worldSetting) setWorldSetting(draft.worldSetting)
      if (draft.customWorldSetting) setCustomWorldSetting(draft.customWorldSetting)
      if (draft.genre) setGenre(draft.genre)
      if (draft.customGenre) setCustomGenre(draft.customGenre)
      if (draft.maleLead) setMaleLead(draft.maleLead)
      if (draft.customMaleLead) setCustomMaleLead(draft.customMaleLead)
      if (draft.femaleLead) setFemaleLead(draft.femaleLead)
      if (draft.customFemaleLead) setCustomFemaleLead(draft.customFemaleLead)
      if (draft.goldFinger) setGoldFinger(draft.goldFinger)
      if (draft.customGoldFinger) setCustomGoldFinger(draft.customGoldFinger)
      if (draft.stylePreference) setStylePreference(draft.stylePreference)
    }
  }, [])

  // 当目标读者切换时，清除不相关的字段
  useEffect(() =>
  {
    if (targetReader === 'female')
    {
      setGenre('')
      setCustomGenre('')
      setMaleLead('')
      setCustomMaleLead('')
      setGoldFinger('')
      setCustomGoldFinger('')
    }
    else if (targetReader === 'male')
    {
      setFemaleLead('')
      setCustomFemaleLead('')
    }
  }, [targetReader])

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

                {/* 自定义每章字数 */}
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
}