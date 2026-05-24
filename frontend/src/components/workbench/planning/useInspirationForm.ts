// 灵感表单逻辑 Hook

import { useState, useEffect, useRef, useCallback } from 'react'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import {
  type InspirationData, REQUIRED_FIELDS, MALE_REQUIRED_FIELDS, FEMALE_REQUIRED_FIELDS,
  getContextStrategyFromTargetWords, generateInspirationTemplate,
  saveInspirationDraft, loadInspirationDraft,
} from '@/lib/inspiration'
import { outlineApi } from '@/lib/api'

interface UseInspirationFormOptions
{
  projectId: number
}

export function useInspirationForm({ projectId }: UseInspirationFormOptions)
{
  const {
    inspirationFields, setInspirationField, setInspirationFields,
    inspirationFieldStatus,
  } = useWorkbenchStore()

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [confirming, setConfirming] = useState(false)
  const [template, setTemplate] = useState('')
  const [templateManuallyEdited, setTemplateManuallyEdited] = useState(false)
  const initializedRef = useRef(false)
  // 防抖自动保存：用 ref 追踪最新状态，避免闭包捕获旧值
  const fieldsRef = useRef(inspirationFields)
  fieldsRef.current = inspirationFields

  // 初始化：从后端或 localStorage 加载
  useEffect(() =>
  {
    if (initializedRef.current) return
    const load = async () =>
    {
      let source: Record<string, unknown> | null = null
      try
      {
        const outline = await outlineApi.get(projectId)
        if (outline.collected_info && Object.keys(outline.collected_info).length > 0)
        {
          source = outline.collected_info as Record<string, unknown>
        }
      } catch { /* 新项目无 outline */ }
      if (!source)
      {
        const draft = loadInspirationDraft()
        if (draft) source = draft as Record<string, unknown>
      }
      if (source)
      {
        const fields: Partial<InspirationData> = {}
        for (const [key, val] of Object.entries(source))
        {
          if (key in inspirationFields && val !== undefined && val !== '')
          {
            (fields as Record<string, unknown>)[key] = val
          }
        }
        setInspirationFields(fields)
      }
      initializedRef.current = true
    }
    load()
  }, [projectId])

  // 自动保存草稿（用 ref 读取最新状态，避免防抖闭包捕获旧值）
  useEffect(() =>
  {
    if (!initializedRef.current) return
    const timer = setTimeout(() =>
    {
      const fields = fieldsRef.current
      if (fields.novelType || fields.targetReader || fields.targetWords)
      {
        saveInspirationDraft(fields)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [inspirationFields])

  // 自动生成模板
  useEffect(() =>
  {
    if (!templateManuallyEdited)
    {
      setTemplate(generateInspirationTemplate(inspirationFields))
    }
  }, [inspirationFields, templateManuallyEdited])

  // targetReader 变化时清除不相关字段
  // 使用 prevReaderRef 防止初始化加载时误清
  const prevReaderRef = useRef<string | undefined>(undefined)
  useEffect(() =>
  {
    if (!initializedRef.current) return
    const reader = inspirationFields.targetReader
    const prevReader = prevReaderRef.current
    prevReaderRef.current = reader
    if (prevReader && reader !== prevReader)
    {
      if (reader === 'female')
      {
        setInspirationFields({ genre: '', customGenre: '', maleLead: '', customMaleLead: '', goldFinger: '', customGoldFinger: '' })
      }
      else if (reader === 'male')
      {
        setInspirationFields({ femaleLead: '', customFemaleLead: '' })
      }
    }
  }, [inspirationFields.targetReader])

  // 设置单个字段（清除对应 error）
  const setField = useCallback(<K extends keyof InspirationData>(key: K, value: InspirationData[K]) =>
  {
    setInspirationField(key, value)
    if (errors[key])
    {
      setErrors(prev => { const next = { ...prev }; delete next[key]; return next })
    }
    if (!value) return
    // 自动推荐上下文策略
    if (key === 'targetWords')
    {
      setInspirationField('contextStrategy', getContextStrategyFromTargetWords(value as number))
    }
  }, [errors, setInspirationField])

  // 校验
  const validate = useCallback((): boolean =>
  {
    const newErrors: Record<string, string> = {}
    const reader = inspirationFields.targetReader
    for (const f of REQUIRED_FIELDS)
    {
      if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
    }
    if (reader === 'male')
    {
      for (const f of MALE_REQUIRED_FIELDS)
      {
        if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
      }
    }
    else if (reader === 'female')
    {
      for (const f of FEMALE_REQUIRED_FIELDS)
      {
        if (!inspirationFields[f]) newErrors[f] = `请选择${f}`
      }
    }
    if (inspirationFields.targetWords < 10000) newErrors.targetWords = '目标字数至少1万字'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [inspirationFields])

  // 构建 collectedInfo（供 confirm 和 replan 共用）
  // selectedModelKey 从 store 实时读取，避免闭包捕获旧值
  const buildCollectedInfoData = useCallback((): Record<string, unknown> =>
  {
    const data: Record<string, unknown> = { inspiration_template: template }
    const f = inspirationFields
    if (f.novelType) data.novelType = f.novelType
    data.targetWords = f.targetWords
    data.contextStrategy = f.contextStrategy
    if (f.novelLength) data.novelLength = f.novelLength
    if (f.coreTheme) data.coreTheme = f.coreTheme
    if (f.worldSetting) { data.worldSetting = f.worldSetting; if (f.customWorldSetting) data.customWorldSetting = f.customWorldSetting }
    if (f.targetReader) data.targetReader = f.targetReader
    if (f.wordsPerChapter) { data.wordsPerChapter = f.wordsPerChapter; if (f.customWordsPerChapter) data.customWordsPerChapter = f.customWordsPerChapter }
    if (f.narrative) data.narrative = f.narrative
    if (f.stylePreference) data.stylePreference = f.stylePreference
    if (f.era) data.era = f.era
    if (f.targetReader === 'male')
    {
      if (f.maleLead) data.maleLead = f.maleLead
      if (f.customMaleLead) data.customMaleLead = f.customMaleLead
      const lead = f.maleLead === 'custom' ? f.customMaleLead : f.maleLead
      if (lead) data.protagonist = lead
      const genreVal = f.genre === 'custom' ? f.customGenre : f.genre
      if (genreVal) data.genre = genreVal
      const gf = f.goldFinger === 'custom' ? f.customGoldFinger : f.goldFinger
      if (gf) data.goldFinger = gf
    }
    else if (f.targetReader === 'female')
    {
      if (f.femaleLead) data.femaleLead = f.femaleLead
      if (f.customFemaleLead) data.customFemaleLead = f.customFemaleLead
      const lead = f.femaleLead === 'custom' ? f.customFemaleLead : f.femaleLead
      if (lead) data.protagonist = lead
    }
    // 模型信息：从 store 实时读取，不依赖闭包
    const selectedModelKey = useWorkbenchStore.getState().selectedModelKey
    if (selectedModelKey)
    {
      const [configIdStr, ...modelNameParts] = selectedModelKey.split(':')
      const configId = parseInt(configIdStr)
      const modelName = modelNameParts.join(':')
      if (!isNaN(configId) && modelName)
      {
        data.model_config_id = configId
        data.model_name = modelName
      }
    }
    return data
  }, [inspirationFields, template])

  // 进度计算
  const progress = (() =>
  {
    let required = [...REQUIRED_FIELDS]
    if (inspirationFields.targetReader === 'male') required = [...required, ...MALE_REQUIRED_FIELDS]
    else if (inspirationFields.targetReader === 'female') required = [...required, ...FEMALE_REQUIRED_FIELDS]
    const filled = required.filter(k =>
    {
      const val = inspirationFields[k]
      return val !== undefined && val !== null && val !== ''
    }).length
    return { requiredFilled: filled, requiredTotal: required.length }
  })()

  // 模板编辑
  const handleTemplateChange = useCallback((value: string) =>
  {
    setTemplate(value)
    setTemplateManuallyEdited(true)
  }, [])

  const handleResetTemplate = useCallback(() =>
  {
    setTemplate(generateInspirationTemplate(inspirationFields))
    setTemplateManuallyEdited(false)
  }, [inspirationFields])

  return {
    fields: inspirationFields,
    fieldStatus: inspirationFieldStatus,
    errors,
    confirming,
    setConfirming,
    template,
    templateManuallyEdited,
    setField,
    validate,
    buildCollectedInfoData,
    progress,
    handleTemplateChange,
    handleResetTemplate,
    initializedRef,
  }
}
