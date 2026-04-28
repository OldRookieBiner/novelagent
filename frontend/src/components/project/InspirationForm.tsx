import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  INSPIRATION_OPTIONS,
  COMMON_OPTIONS,
  MALE_OPTIONS,
  FEMALE_OPTIONS,
  saveInspirationDraft,
  loadInspirationDraft,
  clearInspirationDraft,
  type InspirationData,
} from '@/lib/inspiration'
import { modelConfigsApi } from '@/lib/api'
import type { ModelConfig } from '@/types'

interface InspirationFormProps {
  initialData?: Partial<InspirationData>
  onSubmit: (data: InspirationData, modelId?: number) => void
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

export default function InspirationForm({ initialData, onSubmit }: InspirationFormProps) {
  // 必填项状态
  const [targetReader, setTargetReader] = useState(initialData?.targetReader || '')
  const [novelType, setNovelType] = useState(initialData?.novelType || '')
  const [targetWords, setTargetWords] = useState<number>(initialData?.targetWords || 0)
  const [wordsPerChapter, setWordsPerChapter] = useState(initialData?.wordsPerChapter || '')
  const [customWordsPerChapter, setCustomWordsPerChapter] = useState<number | undefined>(initialData?.customWordsPerChapter)
  const [era, setEra] = useState(initialData?.era || '')  // 年代

  // 选填项状态
  const [narrative, setNarrative] = useState(initialData?.narrative || '')
  const [coreTheme, setCoreTheme] = useState(initialData?.coreTheme || '')
  const [worldSetting, setWorldSetting] = useState(initialData?.worldSetting || '')
  const [customWorldSetting, setCustomWorldSetting] = useState(initialData?.customWorldSetting || '')
  const [genre, setGenre] = useState(initialData?.genre || '')  // 流派（男频专属）
  const [maleLead, setMaleLead] = useState(initialData?.maleLead || '')  // 男主人设
  const [customMaleLead, setCustomMaleLead] = useState(initialData?.customMaleLead || '')
  const [femaleLead, setFemaleLead] = useState(initialData?.femaleLead || '')  // 女主人设
  const [customFemaleLead, setCustomFemaleLead] = useState(initialData?.customFemaleLead || '')
  const [goldFinger, setGoldFinger] = useState(initialData?.goldFinger || '')
  const [customGoldFinger, setCustomGoldFinger] = useState(initialData?.customGoldFinger || '')
  const [stylePreference, setStylePreference] = useState(initialData?.stylePreference || '')

  const [errors, setErrors] = useState<Record<string, string>>({})

  // 模型选择状态
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([])
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)

  // 加载草稿
  useEffect(() => {
    if (!initialData || Object.keys(initialData).length === 0) {
      const draft = loadInspirationDraft()
      if (draft) {
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
        if (draft.maleLead) setMaleLead(draft.maleLead)
        if (draft.customMaleLead) setCustomMaleLead(draft.customMaleLead)
        if (draft.femaleLead) setFemaleLead(draft.femaleLead)
        if (draft.customFemaleLead) setCustomFemaleLead(draft.customFemaleLead)
        if (draft.goldFinger) setGoldFinger(draft.goldFinger)
        if (draft.customGoldFinger) setCustomGoldFinger(draft.customGoldFinger)
        if (draft.stylePreference) setStylePreference(draft.stylePreference)
      }
    }
  }, [initialData])

  // 当目标读者切换时，清除不相关的字段
  useEffect(() => {
    if (targetReader === 'female') {
      // 切换到女频时清除男频专属字段
      setGenre('')
      setMaleLead('')
      setCustomMaleLead('')
      setGoldFinger('')
      setCustomGoldFinger('')
    } else if (targetReader === 'male') {
      // 切换到男频时清除女频专属字段
      setFemaleLead('')
      setCustomFemaleLead('')
    }
  }, [targetReader])

  // 自动保存草稿
  useEffect(() => {
    const data: InspirationData = {
      novelType,
      targetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      era,
      genre,
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
    if (novelType || targetWords || coreTheme || targetReader) {
      saveInspirationDraft(data)
    }
  }, [novelType, targetWords, coreTheme, worldSetting, customWorldSetting, era, genre, maleLead, customMaleLead, femaleLead, customFemaleLead, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])

  // 加载可用模型列表
  useEffect(() => {
    async function loadModels() {
      try {
        const result = await modelConfigsApi.list()
        const enabledModels = result.models.filter(m => m.is_enabled)
        setAvailableModels(enabledModels)

        // 默认选中用户的默认模型
        const defaultModel = enabledModels.find(m => m.is_default)
        if (defaultModel) {
          setSelectedModelId(defaultModel.id)
        }
      } catch (err) {
        console.error('Failed to load models:', err)
      }
    }
    loadModels()
  }, [])

  const handleSubmit = () => {
    const newErrors: Record<string, string> = {}
    if (!targetReader) newErrors.targetReader = '请选择目标读者'
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!targetWords) newErrors.targetWords = '请输入目标字数'
    else if (targetWords < 10000) newErrors.targetWords = '目标字数不能少于1万字'
    if (!wordsPerChapter) newErrors.wordsPerChapter = '请选择每章字数'
    if (!era) newErrors.era = '请选择年代'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'

    // 根据目标读者验证主角设定
    if (targetReader === 'male' && !maleLead) {
      newErrors.maleLead = '请选择男主人设'
    }
    if (targetReader === 'female' && !femaleLead) {
      newErrors.femaleLead = '请选择女主人设'
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    const data: InspirationData = {
      novelType,
      targetWords,
      coreTheme,
      worldSetting,
      customWorldSetting,
      era,
      genre,
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

    clearInspirationDraft()
    onSubmit(data, selectedModelId || undefined)
  }

  const handleClear = () => {
    clearInspirationDraft()
    setTargetReader('')
    setNovelType('')
    setTargetWords(0)
    setWordsPerChapter('')
    setCustomWordsPerChapter(undefined)
    setEra('')
    setNarrative('')
    setCoreTheme('')
    setWorldSetting('')
    setCustomWorldSetting('')
    setGenre('')
    setMaleLead('')
    setCustomMaleLead('')
    setFemaleLead('')
    setCustomFemaleLead('')
    setGoldFinger('')
    setCustomGoldFinger('')
    setStylePreference('')
    setErrors({})
  }

  return (
    <div className="space-y-8">
      {/* 目标读者：独占一行，卡片选择 */}
      <div>
        <div className="text-sm font-medium text-gray-700 mb-3">
          目标读者 <span className="text-red-500">*</span>
        </div>
        <div className="grid grid-cols-2 gap-4 max-w-md">
          {INSPIRATION_OPTIONS.targetReader.map((opt) => (
            <div
              key={opt.value}
              onClick={() => {
                setTargetReader(opt.value)
                if (errors.targetReader) setErrors({ ...errors, targetReader: '' })
              }}
              className={`border-2 rounded-lg p-5 text-center cursor-pointer transition-all ${
                targetReader === opt.value
                  ? 'border-blue-500 bg-blue-50 shadow-sm'
                  : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
              }`}
            >
              <div className="text-3xl mb-2">{TARGET_READER_ICONS[opt.value]}</div>
              <div className="font-medium text-base">{opt.label}</div>
              <div className="text-xs text-gray-500 mt-1">{TARGET_READER_DESC[opt.value]}</div>
            </div>
          ))}
        </div>
        {errors.targetReader && <p className="text-red-500 text-xs mt-2">{errors.targetReader}</p>}
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 基本设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">基本设定</span>
          <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">必填</span>
        </div>

        {/* 小说类型：卡片选择 */}
        <div className="mb-6">
          <div className="text-sm font-medium text-gray-700 mb-3">
            小说类型 <span className="text-red-500">*</span>
          </div>
          <div className="grid grid-cols-6 gap-2">
            {INSPIRATION_OPTIONS.novelTypes.map((opt) => (
              <div
                key={opt.value}
                onClick={() => {
                  setNovelType(opt.value)
                  if (errors.novelType) setErrors({ ...errors, novelType: '' })
                }}
                className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${
                  novelType === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="text-lg mb-1">{NOVEL_TYPE_ICONS[opt.value]}</div>
                <div className="text-sm font-medium">{opt.label}</div>
              </div>
            ))}
          </div>
          {errors.novelType && <p className="text-red-500 text-xs mt-2">{errors.novelType}</p>}
        </div>

        {/* 年代：卡片选择 */}
        <div className="mb-6">
          <div className="text-sm font-medium text-gray-700 mb-3">
            年代 <span className="text-red-500">*</span>
          </div>
          <div className="grid grid-cols-4 gap-2 max-w-lg">
            {COMMON_OPTIONS.era.map((opt) => (
              <div
                key={opt.value}
                onClick={() => {
                  setEra(opt.value)
                  if (errors.era) setErrors({ ...errors, era: '' })
                }}
                className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${
                  era === opt.value
                    ? 'border-blue-500 bg-blue-50 shadow-sm'
                    : 'border-gray-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="text-lg mb-1">{ERA_ICONS[opt.value]}</div>
                <div className="text-sm font-medium">{opt.label}</div>
              </div>
            ))}
          </div>
          {errors.era && <p className="text-red-500 text-xs mt-2">{errors.era}</p>}
        </div>

        {/* 下拉框选项：目标字数、每章字数 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
              目标字数
              <span className="text-red-500">*</span>
              {/* Tips 图标 */}
              <div className="relative group ml-1">
                <svg
                  className="w-4 h-4 text-gray-400 cursor-help hover:text-blue-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {/* Tooltip */}
                <div className="absolute bottom-full left-0 mb-2 w-56 p-3 bg-gray-800 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  <div className="font-medium mb-2">📖 字数与篇幅对应关系：</div>
                  <ul className="space-y-1">
                    <li>• 超短篇：1万-5万字</li>
                    <li>• 短篇：5万-20万字</li>
                    <li>• 中篇：20万-50万字</li>
                    <li>• 长篇：50万-100万字</li>
                    <li>• 超长篇：100万字以上</li>
                  </ul>
                  <div className="absolute bottom-0 left-4 transform translate-y-full">
                    <div className="border-8 border-transparent border-t-gray-800"></div>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={targetWords || ''}
                onChange={(e) => {
                  setTargetWords(parseInt(e.target.value) || 0)
                  if (errors.targetWords) setErrors({ ...errors, targetWords: '' })
                }}
                placeholder="输入目标字数"
                className={`flex-1 h-11 ${errors.targetWords ? 'border-red-500' : ''}`}
              />
              <span className="text-sm text-gray-500">字</span>
            </div>
            {errors.targetWords && <p className="text-red-500 text-xs mt-1">{errors.targetWords}</p>}
          </div>

          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              每章字数 <span className="text-red-500">*</span>
            </div>
            <select
              className={`w-full h-11 px-3 rounded-lg border-2 bg-white text-sm ${
                errors.wordsPerChapter ? 'border-red-500' : 'border-gray-200'
              }`}
              value={wordsPerChapter}
              onChange={(e) => {
                setWordsPerChapter(e.target.value)
                if (errors.wordsPerChapter) setErrors({ ...errors, wordsPerChapter: '' })
              }}
            >
              <option value="">请选择</option>
              {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                  {opt.desc ? `（${opt.desc}）` : ''}
                </option>
              ))}
            </select>
            {errors.wordsPerChapter && <p className="text-red-500 text-xs mt-1">{errors.wordsPerChapter}</p>}
          </div>
        </div>

        {/* 自定义输入 */}
        {wordsPerChapter === 'custom' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">自定义每章字数</div>
              <Input
                type="number"
                value={customWordsPerChapter || ''}
                onChange={(e) => setCustomWordsPerChapter(parseInt(e.target.value) || undefined)}
                placeholder="输入字数"
                className="h-11"
              />
            </div>
          </div>
        )}
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 进阶设定 */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm font-semibold text-gray-700">进阶设定</span>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">选填</span>
        </div>

        <div className="space-y-6">
          {/* 叙事视角 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">叙事视角</div>
            <div className="flex gap-2">
              {INSPIRATION_OPTIONS.narrative.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setNarrative(opt.value)}
                  className={`px-5 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    narrative === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>

          {/* 核心主题 */}
          <div>
            <div className="text-sm font-medium text-gray-700 mb-2">
              核心主题 <span className="text-red-500">*</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => {
                    setCoreTheme(opt.value)
                    if (errors.coreTheme) setErrors({ ...errors, coreTheme: '' })
                  }}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    coreTheme === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
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
            <div className="text-sm font-medium text-gray-700 mb-2">世界观设定</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.worldSettings.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setWorldSetting(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    worldSetting === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
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
              <div className="text-sm font-medium text-gray-700 mb-2">流派</div>
              <div className="flex flex-wrap gap-2">
                {MALE_OPTIONS.genre.map((opt) => (
                  <span
                    key={opt.value}
                    onClick={() => setGenre(opt.value)}
                    className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                      genre === opt.value
                        ? 'bg-blue-500 text-white border-blue-500'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    {opt.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 男主人设（男频专属） */}
          {targetReader === 'male' && (
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">
                男主人设 <span className="text-red-500">*</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {MALE_OPTIONS.maleLead.map((opt) => (
                  <span
                    key={opt.value}
                    onClick={() => {
                      setMaleLead(opt.value)
                      if (errors.maleLead) setErrors({ ...errors, maleLead: '' })
                    }}
                    className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                      maleLead === opt.value
                        ? 'bg-blue-500 text-white border-blue-500'
                        : 'border-gray-200 hover:border-blue-300'
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
              <div className="text-sm font-medium text-gray-700 mb-2">
                女主人设 <span className="text-red-500">*</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {FEMALE_OPTIONS.femaleLead.map((opt) => (
                  <span
                    key={opt.value}
                    onClick={() => {
                      setFemaleLead(opt.value)
                      if (errors.femaleLead) setErrors({ ...errors, femaleLead: '' })
                    }}
                    className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                      femaleLead === opt.value
                        ? 'bg-blue-500 text-white border-blue-500'
                        : 'border-gray-200 hover:border-blue-300'
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
              <div className="text-sm font-medium text-gray-700 mb-2">主角设定</div>
              <p className="text-sm text-gray-400">请先选择目标读者</p>
            </div>
          )}

          {/* 金手指设定（男频专属） */}
          {targetReader === 'male' && (
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">金手指设定</div>
              <div className="flex flex-wrap gap-2">
                {MALE_OPTIONS.goldFinger.map((opt) => (
                  <span
                    key={opt.value}
                    onClick={() => setGoldFinger(opt.value)}
                    className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                      goldFinger === opt.value
                        ? 'bg-blue-500 text-white border-blue-500'
                        : 'border-gray-200 hover:border-blue-300'
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
            <div className="text-sm font-medium text-gray-700 mb-2">风格偏好</div>
            <div className="flex flex-wrap gap-2">
              {INSPIRATION_OPTIONS.stylePreferences.map((opt) => (
                <span
                  key={opt.value}
                  onClick={() => setStylePreference(opt.value)}
                  className={`px-4 py-2 rounded-full border-2 text-sm cursor-pointer transition-all ${
                    stylePreference === opt.value
                      ? 'bg-blue-500 text-white border-blue-500'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {opt.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 分隔线 */}
      <div className="border-t border-gray-200" />

      {/* 模型选择 */}
      <div>
        <div className="text-sm font-medium text-gray-700 mb-2">
          生成模型
        </div>
        <select
          className="w-full h-11 px-3 rounded-lg border-2 border-gray-200 bg-white text-sm focus:border-blue-500 focus:outline-none"
          value={selectedModelId || ''}
          onChange={(e) => setSelectedModelId(Number(e.target.value) || null)}
        >
          {availableModels.length === 0 ? (
            <option value="">请先在设置中添加模型</option>
          ) : (
            availableModels.map(model => (
              <option key={model.id} value={model.id}>
                {model.name}{model.is_default ? '（默认）' : ''}
              </option>
            ))
          )}
        </select>
        <p className="text-xs text-gray-500 mt-1">
          选择用于生成内容的 AI 模型
        </p>
      </div>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button variant="outline" onClick={handleClear}>
          清空表单
        </Button>
        <Button onClick={handleSubmit}>生成大纲</Button>
      </div>
    </div>
  )
}
