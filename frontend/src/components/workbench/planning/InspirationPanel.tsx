// frontend/src/components/workbench/planning/InspirationPanel.tsx

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Lightbulb, RotateCcw, RefreshCw, ArrowRight, Check, ChevronDown, ChevronUp, Copy, ChevronLeft, ChevronRight, Cpu } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  INSPIRATION_OPTIONS,
  COMMON_OPTIONS,
  MALE_OPTIONS,
  FEMALE_OPTIONS,
  CONTEXT_STRATEGY_OPTIONS,
  getContextStrategyFromTargetWords,
generateInspirationTemplate,
  saveInspirationDraft,
  loadInspirationDraft,
  type InspirationData,
} from '@/lib/inspiration'
import { collectedInfoApi, modelConfigsApi } from '@/lib/api'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { OutlineProgressDialog } from './OutlineProgressDialog'
import { toast } from 'sonner'

interface InspirationPanelProps
{
  projectId: number
  hasOutline?: boolean
  onPlanningComplete?: () => void
}

/** 扁平化后的模型选项 */
interface ModelOption
{
  modelConfigId: number  // model_configs 表 ID
  modelName: string      // 具体模型名
  providerName: string   // 提供商显示名
  provider: string       // 提供商标识
  isDefault: boolean     // 是否为默认配置
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

export function InspirationPanel({ projectId, hasOutline = false, onPlanningComplete }: InspirationPanelProps)
{
  // 必填项状态
  const [targetReader, setTargetReader] = useState('')
  const [novelType, setNovelType] = useState('')
  const [targetWords, setTargetWords] = useState<number>(50000)  // 独立的目标字数
  const [contextStrategy, setContextStrategy] = useState<string>('fulltext')
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
  const [advancedExpanded, setAdvancedExpanded] = useState(false)

  // 模板相关状态
  const [template, setTemplate] = useState('')
  const [templateManuallyEdited, setTemplateManuallyEdited] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [showProgressDialog, setShowProgressDialog] = useState(false)
  const [showReplanConfirm, setShowReplanConfirm] = useState(false)
  const [replanCollectedInfo, setReplanCollectedInfo] = useState<Record<string, unknown> | null>(null)

  // 模型选择器状态
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [loadingModels, setLoadingModels] = useState(false)

  const { setActiveMenuItem, selectedModelKey, setSelectedModelKey } = useWorkbenchStore()

  const handleTargetWordsChange = (value: string) =>
  {
    const num = parseInt(value)
    if (!isNaN(num) && num > 0)
    {
      setTargetWords(num)
    }
  }

  // 目标字数变化时智能推荐上下文策略
  const handleTargetWordsBlur = () =>
  {
    const recommended = getContextStrategyFromTargetWords(targetWords)
    setContextStrategy(recommended)
  }

  // 构建完整的表单数据对象（用于生成模板）
  const formData = useMemo((): InspirationData => ({
    novelType,
    targetWords,
    contextStrategy,
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
  }), [novelType, targetWords, contextStrategy, coreTheme, worldSetting, customWorldSetting, era, genre, customGenre, maleLead, customMaleLead, femaleLead, customFemaleLead, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])

  // 实时更新模板（用户未手动编辑时）
  useEffect(() =>
  {
    if (!templateManuallyEdited)
    {
      const generated = generateInspirationTemplate(formData)
      setTemplate(generated)
    }
  }, [formData, templateManuallyEdited])

  // 加载草稿或初始数据后，立即生成初始模板
  useEffect(() =>
  {
    if (!template && !templateManuallyEdited)
    {
      const generated = generateInspirationTemplate(formData)
      setTemplate(generated)
    }
  }, [formData, template, templateManuallyEdited])

  // 加载草稿
  useEffect(() =>
  {
    const draft = loadInspirationDraft()
    if (draft)
    {
      if (draft.targetReader) setTargetReader(draft.targetReader)
      if (draft.novelType) setNovelType(draft.novelType)
      if (draft.targetWords) setTargetWords(draft.targetWords)
      if (draft.contextStrategy) setContextStrategy(draft.contextStrategy)
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

  // 加载可用模型列表
  useEffect(() =>
  {
    const loadModels = async () =>
    {
      setLoadingModels(true)
      try
      {
        const response = await modelConfigsApi.list()
        const options: ModelOption[] = []
        // 提供商的显示名称映射
        const providerNames: Record<string, string> = {
          deepseek: 'DeepSeek (深度求索)',
          openai: 'OpenAI',
          anthropic: 'Anthropic',
          baidu: '百度文心',
          volcengine: '火山引擎',
          unicom: '联通云',
          custom: '自定义',
        }
        for (const config of response.models)
        {
          // 只显示已启用的配置
          if (!config.is_enabled) continue
          const providerDisplayName = providerNames[config.provider] || config.provider
          if (config.provider_type === 'coding_plan' && config.models && config.models.length > 0)
          {
            // coding_plan 类型：展开 models 数组，每个 model 一个选项
            for (const model of config.models)
            {
              if (!model.is_enabled) continue
              options.push({
                modelConfigId: config.id,
                modelName: model.name,
                providerName: providerDisplayName,
                provider: config.provider,
                isDefault: config.is_default,
              })
            }
          }
          else if (config.model_name)
          {
            // single 类型：一个配置一个选项
            options.push({
              modelConfigId: config.id,
              modelName: config.model_name,
              providerName: providerDisplayName,
              provider: config.provider,
              isDefault: config.is_default,
            })
          }
        }
        setModelOptions(options)
        // 设置默认选中：仅当 store 中没有选择时
        if (!selectedModelKey)
        {
          const defaultOption = options.find(o => o.isDefault) || options[0]
          if (defaultOption)
          {
            setSelectedModelKey(`${defaultOption.modelConfigId}:${defaultOption.modelName}`)
          }
        }
      }
      catch (err)
      {
        console.error('Failed to load model options:', err)
      }
      finally
      {
        setLoadingModels(false)
      }
    }
    loadModels()
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
      contextStrategy,
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
    if (novelType || targetWords || contextStrategy || coreTheme || targetReader)
    {
      saveInspirationDraft(data)
    }
  }, [novelType, targetWords, contextStrategy, coreTheme, worldSetting, customWorldSetting, era, genre, customGenre, maleLead, customMaleLead, femaleLead, customFemaleLead, stylePreference, targetReader, wordsPerChapter, customWordsPerChapter, narrative, goldFinger, customGoldFinger])

  // 用户手动编辑模板
  const handleTemplateChange = useCallback((value: string) =>
  {
    setTemplate(value)
    setTemplateManuallyEdited(true)
  }, [])

  // 重置模板（恢复自动同步）
  const handleResetTemplate = () =>
  {
    setTemplate(generateInspirationTemplate(formData))
    setTemplateManuallyEdited(false)
  }

  const handleCopyTemplate = () =>
  {
    navigator.clipboard.writeText(template).then(() =>
    {
      toast.success('Prompt 已复制到剪贴板')
    }).catch(() =>
    {
      toast.error('复制失败')
    })
  }

  // 重新规划处理：先保存表单数据，再打开进度弹窗
  const handleReplan = async () =>
  {
    setShowReplanConfirm(false)

    // 构建灵感采集数据并保存到后端（与 handleConfirm 相同逻辑）
    try
    {
      const collectedInfoData: Record<string, unknown> = {
        inspiration_template: template,
      }

      if (novelType) collectedInfoData.novelType = novelType
      collectedInfoData.targetWords = targetWords
      collectedInfoData.contextStrategy = contextStrategy
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
        if (maleLead) collectedInfoData.maleLead = maleLead
        if (customMaleLead) collectedInfoData.customMaleLead = customMaleLead
        const lead = maleLead === 'custom' ? customMaleLead : maleLead
        if (lead) collectedInfoData.protagonist = lead
        const genreVal = genre === 'custom' ? customGenre : genre
        if (genreVal) collectedInfoData.genre = genreVal
        const gf = goldFinger === 'custom' ? customGoldFinger : goldFinger
        if (gf) collectedInfoData.goldFinger = gf
      }
      else if (targetReader === 'female')
      {
        if (femaleLead) collectedInfoData.femaleLead = femaleLead
        if (customFemaleLead) collectedInfoData.customFemaleLead = customFemaleLead
        const lead = femaleLead === 'custom' ? customFemaleLead : femaleLead
        if (lead) collectedInfoData.protagonist = lead
      }

      // 将灵感数据暂存，供 OutlineProgressDialog 传递给 replan API
      setReplanCollectedInfo(collectedInfoData)
    }
    catch (err)
    {
      console.error('Failed to prepare replan data:', err)
    }

    setShowProgressDialog(true)
  }

  // 确认灵感，生成大纲
  const handleConfirm = async () =>
  {
    // 验证必填项
    const newErrors: Record<string, string> = {}
    if (!targetReader) newErrors.targetReader = '请选择目标读者'
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!targetWords || targetWords < 10000) newErrors.targetWords = '目标字数至少1万字'
    if (!contextStrategy) newErrors.contextStrategy = '请选择上下文策略'
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
      collectedInfoData.targetWords = targetWords
      collectedInfoData.contextStrategy = contextStrategy
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
        // 保存原始 maleLead 字段（含 custom），供后端 fallback 使用
        if (maleLead) collectedInfoData.maleLead = maleLead
        if (customMaleLead) collectedInfoData.customMaleLead = customMaleLead

        const lead = maleLead === 'custom' ? customMaleLead : maleLead
        if (lead) collectedInfoData.protagonist = lead
        const genreVal = genre === 'custom' ? customGenre : genre
        if (genreVal) collectedInfoData.genre = genreVal
        const gf = goldFinger === 'custom' ? customGoldFinger : goldFinger
        if (gf) collectedInfoData.goldFinger = gf
      }
      else if (targetReader === 'female')
      {
        // 保存原始 femaleLead 字段（含 custom），供后端 fallback 使用
        if (femaleLead) collectedInfoData.femaleLead = femaleLead
        if (customFemaleLead) collectedInfoData.customFemaleLead = customFemaleLead

        const lead = femaleLead === 'custom' ? customFemaleLead : femaleLead
        if (lead) collectedInfoData.protagonist = lead
      }

      // 解析选中的模型信息
      if (selectedModelKey)
      {
        const [configIdStr, ...modelNameParts] = selectedModelKey.split(':')
        const configId = parseInt(configIdStr)
        // modelName 可能包含冒号，重新拼接
        const modelName = modelNameParts.join(':')
        if (!isNaN(configId) && modelName)
        {
          collectedInfoData.model_config_id = configId
          collectedInfoData.model_name = modelName
        }
      }

      await collectedInfoApi.update(projectId, collectedInfoData)
      toast.success('灵感已确认')
      // 不清空草稿 — 数据已保存到数据库，草稿作为本地缓存保留

      // 弹出进度弹窗，不跳转
      setShowProgressDialog(true)
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
      {/* 左侧：表单选择区 (70%) */}
      <div className="flex-[7] flex flex-col">
        <div className="flex items-center justify-between px-6 py-3 border-b bg-white">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            灵感采集
          </h2>
          {/* 步骤引导 */}
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 text-indigo-600 font-medium">
              <span className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold">1</span>
              必填信息 (7)
            </div>
            <span className="text-gray-300">→</span>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <span className="w-5 h-5 rounded-full bg-gray-100 flex items-center justify-center text-muted-foreground">2</span>
              高级设定
            </div>
          </div>
        </div>
        <div className="flex-1 p-6 overflow-auto">
          <div className="max-w-2xl space-y-5">
            {/* 目标读者 */}
            <Card className="border-2 border-indigo-200">
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
                        if (errors.targetReader) setErrors(prev => ({ ...prev, targetReader: '' }))
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

            {/* 核心设定 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <span className="text-indigo-500">📋</span>
                  核心设定
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
                          if (errors.novelType) setErrors(prev => ({ ...prev, novelType: '' }))
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
                          if (errors.era) setErrors(prev => ({ ...prev, era: '' }))
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

                {/* 上下文策略 */}
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    上下文策略 <span className="text-red-500">*</span>
                  </label>
                  <RadioGroup
                    value={contextStrategy}
                    onValueChange={setContextStrategy}
                    className="space-y-2"
                  >
                    {CONTEXT_STRATEGY_OPTIONS.map((option) => (
                      <div key={option.value} className="flex items-center space-x-2">
                        <RadioGroupItem
                          value={option.value}
                          id={`strategy-${option.value}`}
                          disabled={option.value !== 'fulltext'}
                        />
                        <label
                          htmlFor={`strategy-${option.value}`}
                          className={`text-sm ${option.value !== 'fulltext' ? 'text-muted-foreground cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          {option.label} — {option.desc}
                          <span className="ml-1 text-xs text-muted-foreground">（推荐{option.recommendedWords}）</span>
                          {option.value !== 'fulltext' && (
                            <span className="ml-1 text-xs text-muted-foreground">（待开发）</span>
                          )}
                        </label>
                      </div>
                    ))}
                  </RadioGroup>
                </div>

                {/* 目标字数 + 每章字数 并排 */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">
                      目标字数 <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <Input
                        type="number"
                        min={10000}
                        step={10000}
                        value={targetWords || ''}
                        onChange={(e) =>
                        {
                          handleTargetWordsChange(e.target.value)
                          if (errors.targetWords) setErrors(prev => ({ ...prev, targetWords: '' }))
                        }}
                        onBlur={handleTargetWordsBlur}
                        placeholder="50000"
                        className={`pr-8 ${errors.targetWords ? 'border-red-500' : ''}`}
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">字</span>
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
                        if (errors.wordsPerChapter) setErrors(prev => ({ ...prev, wordsPerChapter: '' }))
                      }}
                    >
                      <option value="">请选择</option>
                      {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}{opt.desc ? `（${opt.desc}）` : ''}</option>
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

            {/* 核心主题 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <span className="text-amber-500">🎯</span>
                  核心主题
                  <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">必填</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {INSPIRATION_OPTIONS.coreThemes.map((opt) => (
                    <span
                      key={opt.value}
                      onClick={() =>
                      {
                        setCoreTheme(opt.value)
                        if (errors.coreTheme) setErrors(prev => ({ ...prev, coreTheme: '' }))
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
              </CardContent>
            </Card>

            {/* 高级设定（可折叠） */}
            <Card>
              <button
                onClick={() => setAdvancedExpanded(!advancedExpanded)}
                className="w-full flex items-center justify-between p-4 hover:bg-muted/30 transition-colors text-left"
              >
                <CardTitle className="text-sm flex items-center gap-2">
                  <span className="text-gray-500">📝</span>
                  高级设定
                  <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">选填</span>
                  {(narrative || worldSetting || genre || maleLead || femaleLead || goldFinger || stylePreference) && (
                    <span className="text-[10px] text-indigo-500 font-normal">
                      · 已填 {[narrative, worldSetting, genre, maleLead, femaleLead, goldFinger, stylePreference].filter(Boolean).length} 项
                    </span>
                  )}
                </CardTitle>
                {advancedExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
              </button>
              {advancedExpanded && (
                <CardContent className="space-y-4 pt-0">
                  {/* 叙事视角 */}
                  <div>
                    <label className="text-sm text-muted-foreground mb-2 block">叙事视角</label>
                    <div className="flex flex-wrap gap-2">
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
                              if (errors.maleLead) setErrors(prev => ({ ...prev, maleLead: '' }))
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
                              if (errors.femaleLead) setErrors(prev => ({ ...prev, femaleLead: '' }))
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
              )}
            </Card>
          </div>
        </div>

        {/* 底部：模型选择 + 确认按钮 */}
        <div className="border-t bg-white px-6 py-4">
          <div className="flex items-center gap-3 max-w-2xl mx-auto">
            {/* AI 模型选择器 */}
            <div className="flex-1 min-w-0">
              <label className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1" htmlFor="model-select-trigger">
                <Cpu className="h-3 w-3" />
                AI 模型
              </label>
              <Select value={selectedModelKey} onValueChange={setSelectedModelKey} disabled={loadingModels || modelOptions.length === 0}>
                <SelectTrigger id="model-select-trigger" className="w-full h-9 text-sm">
                  <SelectValue placeholder={loadingModels ? '加载中...' : '请选择模型'} />
                </SelectTrigger>
                <SelectContent>
                  {/* 按提供商分组 */}
                  {(() =>
                  {
                    // 按 provider 分组
                    const grouped = new Map<string, ModelOption[]>()
                    for (const opt of modelOptions)
                    {
                      if (!grouped.has(opt.provider))
                      {
                        grouped.set(opt.provider, [])
                      }
                      grouped.get(opt.provider)!.push(opt)
                    }
                    return Array.from(grouped.entries()).map(([provider, options]) => (
                      <SelectGroup key={provider}>
                        <SelectLabel>{options[0].providerName}</SelectLabel>
                        {options.map(opt => (
                          <SelectItem
                            key={`${opt.modelConfigId}:${opt.modelName}`}
                            value={`${opt.modelConfigId}:${opt.modelName}`}
                          >
                            <span className="flex items-center gap-1.5">
                              {opt.modelName}
                              {opt.isDefault && (
                                <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">默认</span>
                              )}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    ))
                  })()}
                </SelectContent>
              </Select>
            </div>

            {/* 确认/重新规划按钮 */}
            {hasOutline ? (
              <Button onClick={() => setShowReplanConfirm(true)} className="px-6 mt-[22px]" variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                重新规划
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button onClick={handleConfirm} disabled={confirming} className="px-6 mt-[22px]">
                {confirming ? (
                  <>保存中...</>
                ) : (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    开始规划
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground text-center mt-1.5">
            {hasOutline ? '重新生成大纲、人物和关系' : '确认后自动开始规划'}
          </p>
        </div>
      </div>

      {/* 右侧：Prompt 模板区 */}
      <div className={`border-l bg-white flex flex-col shrink-0 transition-all duration-300 ${rightCollapsed ? 'w-12' : 'w-[360px]'} relative`}>
        {/* 收缩展开按钮 */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
        >
          {rightCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
        {!rightCollapsed && (
          <>
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h3 className="text-sm font-medium flex items-center gap-2">
                <Lightbulb className="h-4 w-4" />
                创作 Prompt
              </h3>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleCopyTemplate}>
                  <Copy className="h-3 w-3 mr-1" />
                  复制
                </Button>
                {templateManuallyEdited && (
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleResetTemplate}>
                    <RotateCcw className="h-3 w-3 mr-1" />
                    重置
                  </Button>
                )}
              </div>
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
            </>
        )}
        {rightCollapsed && (
          <div className="flex flex-col items-center pt-4 gap-3">
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
            <Copy className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
      </div>
      {/* 重新规划确认对话框 */}
      <AlertDialog open={showReplanConfirm} onOpenChange={setShowReplanConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认重新规划？</AlertDialogTitle>
            <AlertDialogDescription>
              重新规划将清除当前的大纲、人物和关系数据，基于当前灵感重新生成。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleReplan}>确认重新规划</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      {/* 大纲生成进度弹窗 */}
      <OutlineProgressDialog
        open={showProgressDialog}
        onClose={() => setShowProgressDialog(false)}
        projectId={projectId}
        modelConfigId={selectedModelKey ? parseInt(selectedModelKey.split(':')[0]) : undefined}
        modelName={selectedModelKey ? selectedModelKey.split(':').slice(1).join(':') : undefined}
        isReplan={hasOutline}
        collectedInfo={replanCollectedInfo}
        inspirationTemplate={template}
        onComplete={() => { onPlanningComplete?.() }}
        onViewOutline={() =>
        {
          onPlanningComplete?.()
          setShowProgressDialog(false)
          setActiveMenuItem('outline')
        }}
      />
    </div>
  )
}