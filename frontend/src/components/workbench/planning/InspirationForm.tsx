// 灵感参数面板 — 替代原 InspirationPanel 中的全部表单 JSX

import { useState, useEffect } from 'react'
import { Lightbulb, Cpu, Settings2, Check, RefreshCw } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  INSPIRATION_OPTIONS, COMMON_OPTIONS, MALE_OPTIONS, FEMALE_OPTIONS,
  CONTEXT_STRATEGY_OPTIONS, QUICK_TEMPLATES,
  NOVEL_TYPE_ICONS, ERA_ICONS, TARGET_READER_ICONS, TARGET_READER_DESC,
  getContextStrategyFromTargetWords,
  type InspirationData, type FieldStatus,
} from '@/lib/inspiration'
import { modelConfigsApi } from '@/lib/api'
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { InspirationFieldGroup } from './InspirationFieldGroup'
import { InspirationTemplatePreview } from './InspirationTemplatePreview'
import { useInspirationForm } from './useInspirationForm'

/** 扁平化后的模型选项 */
export interface ModelOption
{
  modelConfigId: number
  modelName: string
  configName: string
  isDefault: boolean
}

interface InspirationFormProps
{
  projectId: number
  hasOutline?: boolean
  /** 确认灵感：校验 → 调用 API 保存 → 返回 collectedInfo 供父组件打开进度弹窗 */
  onConfirm: (collectedInfo: Record<string, unknown>) => Promise<void>
  /** 重新规划请求：校验 → 构建 collectedInfo → 通知父组件显示确认弹窗 */
  onRequestReplan: (collectedInfo: Record<string, unknown>) => void
}

export function InspirationForm({ projectId, hasOutline, onConfirm, onRequestReplan }: InspirationFormProps)
{
  const {
    fields, fieldStatus, errors, confirming, setConfirming,
    template, templateManuallyEdited,
    setField, validate, buildCollectedInfoData, progress,
    handleTemplateChange, handleResetTemplate,
  } = useInspirationForm({ projectId })

  const { selectedModelKey, setSelectedModelKey } = useWorkbenchStore()
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [reviewLlmConfigId, setReviewLlmConfigId] = useState<number | null>(null)
  const [showReviewModelAdvanced, setShowReviewModelAdvanced] = useState(false)
  const [advancedExpanded, setAdvancedExpanded] = useState(false)
  const [quickTemplateOpen, setQuickTemplateOpen] = useState(false)

  // 加载模型列表
  useEffect(() =>
  {
    const load = async () =>
    {
      setLoadingModels(true)
      try
      {
        const response = await modelConfigsApi.list()
        const options: ModelOption[] = []
        for (const config of response.models)
        {
          if (!config.is_enabled) continue
          if (config.models && config.models.length > 0)
          {
            for (const model of config.models)
            {
              if (!model.is_enabled) continue
              options.push({ modelConfigId: config.id, modelName: model.name, configName: config.name, isDefault: config.is_default })
            }
          }
          else if (config.model_name)
          {
            options.push({ modelConfigId: config.id, modelName: config.model_name, configName: config.name, isDefault: config.is_default })
          }
        }
        setModelOptions(options)
        if (!selectedModelKey)
        {
          const def = options.find(o => o.isDefault) || options[0]
          if (def) setSelectedModelKey(`${def.modelConfigId}:${def.modelName}`)
        }
      }
      catch (err) { console.error('Failed to load models:', err) }
      finally { setLoadingModels(false) }
    }
    load()
  }, [])

  // 快捷模板
  const applyQuickTemplate = (tpl: typeof QUICK_TEMPLATES[0]) =>
  {
    setQuickTemplateOpen(false)
    for (const [key, val] of Object.entries(tpl.data))
    {
      if (val !== undefined) setField(key as keyof InspirationData, val as never)
    }
  }

  // 计算每个字段组的状态
  const baseGroupStatus: FieldStatus = ['novelType', 'targetReader', 'era', 'targetWords', 'wordsPerChapter', 'coreTheme']
    .some(k => fieldStatus[k] === 'agent_asking') ? 'agent_asking'
    : ['novelType', 'targetReader', 'era', 'targetWords', 'wordsPerChapter', 'coreTheme']
      .some(k => fieldStatus[k] === 'agent_populated') ? 'agent_populated' : 'empty'

  const protagonistGroupStatus: FieldStatus = fields.targetReader === 'male'
    ? (fieldStatus.maleLead === 'agent_asking' || fieldStatus.goldFinger === 'agent_asking' ? 'agent_asking'
      : fieldStatus.maleLead === 'agent_populated' || fieldStatus.goldFinger === 'agent_populated' ? 'agent_populated' : 'empty')
    : fields.targetReader === 'female'
      ? (fieldStatus.femaleLead === 'agent_asking' ? 'agent_asking'
        : fieldStatus.femaleLead === 'agent_populated' ? 'agent_populated' : 'empty')
      : 'empty'

  // 高级设定已填项数
  const advancedFilled = [fields.narrative, fields.worldSetting, fields.genre, fields.stylePreference, fields.goldFinger]
    .filter(Boolean).length

  // 确认
  const handleConfirm = async () =>
  {
    if (!validate()) return
    setConfirming(true)
    try
    {
      const data = buildCollectedInfoData()
      await onConfirm(data)
    }
    catch (err)
    {
      console.error('Failed to confirm:', err)
    }
    finally { setConfirming(false) }
  }

  // 重新规划请求
  const handleReplanRequest = () =>
  {
    if (!validate()) return
    const data = buildCollectedInfoData()
    onRequestReplan(data)
  }

  // 模型分组渲染
  const renderModelGroups = (prefix?: string) =>
  {
    const grouped = new Map<number, ModelOption[]>()
    for (const opt of modelOptions)
    {
      if (!grouped.has(opt.modelConfigId)) grouped.set(opt.modelConfigId, [])
      grouped.get(opt.modelConfigId)!.push(opt)
    }
    return Array.from(grouped.entries()).map(([configId, options]) => (
      <SelectGroup key={configId}>
        <SelectLabel>{options[0].configName}</SelectLabel>
        {options.map(opt => (
          <SelectItem key={`${prefix || ''}${opt.modelConfigId}:${opt.modelName}`} value={`${opt.modelConfigId}:${opt.modelName}`}>
            <span className="flex items-center gap-1.5">
              {opt.modelName}
              {opt.isDefault && <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">默认</span>}
            </span>
          </SelectItem>
        ))}
      </SelectGroup>
    ))
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-white">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2"><Lightbulb className="h-4 w-4" />灵感参数面板</h2>
          <p className="text-[10px] text-muted-foreground mt-0.5">填写创作参数，或让 AI 搭档帮你完成</p>
        </div>
        <div className="relative">
          <Button variant="outline" size="sm" className="text-xs h-7" onClick={() => setQuickTemplateOpen(!quickTemplateOpen)}>
            快捷模板 {quickTemplateOpen ? '▴' : '▾'}
          </Button>
          {quickTemplateOpen && (
            <div className="absolute right-0 top-full mt-1 z-20 w-56 bg-white border rounded-lg shadow-lg py-1">
              {QUICK_TEMPLATES.map(tpl => (
                <button key={tpl.id} onClick={() => applyQuickTemplate(tpl)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-indigo-50 text-left">
                  <span>{tpl.icon}</span>
                  <div><div className="font-medium">{tpl.label}</div></div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 可滚动表单 */}
      <div className="flex-1 p-4 overflow-auto">
        <div className="max-w-3xl space-y-3">
          {/* 基础设定 */}
          <InspirationFieldGroup title="基础设定" icon="📋" required groupStatus={baseGroupStatus}>
            {/* 目标读者 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">目标读者 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-2 gap-3 max-w-md">
                {INSPIRATION_OPTIONS.targetReader.map(opt => (
                  <div key={opt.value} onClick={() => setField('targetReader', opt.value)}
                    className={`border-2 rounded-lg p-3 text-center cursor-pointer transition-all ${fields.targetReader === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-xl mb-0.5">{TARGET_READER_ICONS[opt.value]}</div>
                    <div className="text-xs font-medium">{opt.label}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{TARGET_READER_DESC[opt.value]}</div>
                  </div>
                ))}
              </div>
              {errors.targetReader && <p className="text-red-500 text-[10px] mt-1">{errors.targetReader}</p>}
            </div>
            {/* 小说类型 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">小说类型 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-6 gap-1.5">
                {INSPIRATION_OPTIONS.novelTypes.map(opt => (
                  <div key={opt.value} onClick={() => setField('novelType', opt.value)}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.novelType === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-sm mb-0.5">{NOVEL_TYPE_ICONS[opt.value]}</div>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                  </div>
                ))}
              </div>
              {errors.novelType && <p className="text-red-500 text-[10px] mt-1">{errors.novelType}</p>}
            </div>
            {/* 篇幅 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">篇幅类型</label>
              <div className="grid grid-cols-3 gap-1.5 max-w-lg">
                {[
                  { value: 'short' as const, label: '短篇', desc: '<5万字' },
                  { value: 'medium' as const, label: '中篇', desc: '5-20万字' },
                  { value: 'long' as const, label: '长篇', desc: '20万字+' },
                ].map(opt => (
                  <div key={opt.value} onClick={() => {
                    setField('novelLength', opt.value)
                    setField('targetWords', opt.value === 'short' ? 30000 : opt.value === 'medium' ? 100000 : 250000 as never)
                    setField('contextStrategy', opt.value === 'short' ? 'fulltext' : opt.value === 'medium' ? 'hybrid' : 'summary' as never)
                  }}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.novelLength === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                    <div className="text-[10px] text-muted-foreground">{opt.desc}</div>
                  </div>
                ))}
              </div>
            </div>
            {/* 年代 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">年代 <span className="text-red-500">*</span></label>
              <div className="grid grid-cols-4 gap-1.5 max-w-lg">
                {COMMON_OPTIONS.era.map(opt => (
                  <div key={opt.value} onClick={() => setField('era', opt.value)}
                    className={`border-2 rounded-lg p-1.5 text-center cursor-pointer transition-all text-xs ${fields.era === opt.value ? 'border-primary bg-primary/5 shadow-sm' : 'border-gray-200 hover:border-primary/50'}`}>
                    <div className="text-sm mb-0.5">{ERA_ICONS[opt.value]}</div>
                    <div className="text-[10px] font-medium">{opt.label}</div>
                  </div>
                ))}
              </div>
              {errors.era && <p className="text-red-500 text-[10px] mt-1">{errors.era}</p>}
            </div>
            {/* 核心主题 */}
            <div className="mb-3">
              <label className="text-xs text-muted-foreground mb-2 block">核心主题 <span className="text-red-500">*</span></label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.coreThemes.map(opt => (
                  <span key={opt.value} onClick={() => setField('coreTheme', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.coreTheme === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
              {errors.coreTheme && <p className="text-red-500 text-[10px] mt-1">{errors.coreTheme}</p>}
            </div>
            {/* 目标字数 + 每章字数 */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">目标字数 <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Input type="number" min={10000} step={10000} value={fields.targetWords || ''}
                    onChange={(e) => setField('targetWords', parseInt(e.target.value) || 50000)}
                    onBlur={() => { if (fields.targetWords) setField('contextStrategy', getContextStrategyFromTargetWords(fields.targetWords) as never) }}
                    className={`pr-7 text-xs ${errors.targetWords ? 'border-red-500' : ''}`}
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground">字</span>
                </div>
                {errors.targetWords && <p className="text-red-500 text-[10px] mt-0.5">{errors.targetWords}</p>}
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">每章字数 <span className="text-red-500">*</span></label>
                <Select value={fields.wordsPerChapter || ''} onValueChange={(v) => setField('wordsPerChapter', v)}>
                  <SelectTrigger className={`w-full h-9 text-xs ${errors.wordsPerChapter ? 'border-red-500' : ''}`}>
                    <SelectValue placeholder="请选择" />
                  </SelectTrigger>
                  <SelectContent>
                    {INSPIRATION_OPTIONS.wordsPerChapter.map(opt => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}{opt.desc ? ` (${opt.desc})` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.wordsPerChapter && <p className="text-red-500 text-[10px] mt-0.5">{errors.wordsPerChapter}</p>}
              </div>
            </div>
            {/* 上下文策略 */}
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">上下文策略</label>
              <RadioGroup value={fields.contextStrategy} onValueChange={(v) => setField('contextStrategy', v as never)} className="space-y-1">
                {CONTEXT_STRATEGY_OPTIONS.map(opt => (
                  <div key={opt.value} className="flex items-center space-x-2">
                    <RadioGroupItem value={opt.value} id={`strategy-${opt.value}`} disabled={opt.value !== 'fulltext'} />
                    <label htmlFor={`strategy-${opt.value}`} className={`text-xs ${opt.value !== 'fulltext' ? 'text-muted-foreground cursor-not-allowed' : 'cursor-pointer'}`}>
                      {opt.label} — {opt.desc}
                      <span className="ml-1 text-[10px] text-muted-foreground">(推荐{opt.recommendedWords})</span>
                      {opt.value !== 'fulltext' && <span className="ml-1 text-[10px] text-muted-foreground">(待开发)</span>}
                    </label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          </InspirationFieldGroup>

          {/* 主角设定 */}
          <InspirationFieldGroup title="主角设定" icon="👤" required groupStatus={protagonistGroupStatus}>
            {fields.targetReader === 'male' && (
              <>
                <div className="mb-2">
                  <label className="text-xs text-muted-foreground mb-1.5 block">男主人设 <span className="text-red-500">*</span></label>
                  <div className="flex flex-wrap gap-1.5">
                    {MALE_OPTIONS.maleLead.map(opt => (
                      <span key={opt.value} onClick={() => setField('maleLead', opt.value)}
                        className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.maleLead === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {fields.maleLead === 'custom' && <Input type="text" value={fields.customMaleLead || ''} onChange={(e) => setField('customMaleLead', e.target.value)} placeholder="自定义男主人设" className="mt-1.5 max-w-md text-xs" />}
                  {errors.maleLead && <p className="text-red-500 text-[10px] mt-1">{errors.maleLead}</p>}
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1.5 block">金手指设定</label>
                  <div className="flex flex-wrap gap-1.5">
                    {MALE_OPTIONS.goldFinger.map(opt => (
                      <span key={opt.value} onClick={() => setField('goldFinger', opt.value)}
                        className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.goldFinger === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                        {opt.label}
                      </span>
                    ))}
                  </div>
                  {fields.goldFinger === 'custom' && <Input type="text" value={fields.customGoldFinger || ''} onChange={(e) => setField('customGoldFinger', e.target.value)} placeholder="自定义金手指" className="mt-1.5 max-w-md text-xs" />}
                </div>
              </>
            )}
            {fields.targetReader === 'female' && (
              <div>
                <label className="text-xs text-muted-foreground mb-1.5 block">女主人设 <span className="text-red-500">*</span></label>
                <div className="flex flex-wrap gap-1.5">
                  {FEMALE_OPTIONS.femaleLead.map(opt => (
                    <span key={opt.value} onClick={() => setField('femaleLead', opt.value)}
                      className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.femaleLead === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                      {opt.label}
                    </span>
                  ))}
                </div>
                {fields.femaleLead === 'custom' && <Input type="text" value={fields.customFemaleLead || ''} onChange={(e) => setField('customFemaleLead', e.target.value)} placeholder="自定义女主人设" className="mt-1.5 max-w-md text-xs" />}
                {errors.femaleLead && <p className="text-red-500 text-[10px] mt-1">{errors.femaleLead}</p>}
              </div>
            )}
            {!fields.targetReader && <p className="text-xs text-muted-foreground">请先选择目标读者</p>}
          </InspirationFieldGroup>

          {/* 高级设定 */}
          <InspirationFieldGroup title="高级设定" icon="📝" collapsible collapsed={!advancedExpanded}
            onToggleCollapse={() => setAdvancedExpanded(!advancedExpanded)} optionalFilledCount={advancedFilled}>
            <div className="mb-2">
              <label className="text-xs text-muted-foreground mb-1.5 block">叙事视角</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.narrative.map(opt => (
                  <span key={opt.value} onClick={() => setField('narrative', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.narrative === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="mb-2">
              <label className="text-xs text-muted-foreground mb-1.5 block">世界观设定</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.worldSettings.map(opt => (
                  <span key={opt.value} onClick={() => setField('worldSetting', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.worldSetting === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
              {fields.worldSetting === 'custom' && <Input type="text" value={fields.customWorldSetting || ''} onChange={(e) => setField('customWorldSetting', e.target.value)} placeholder="自定义世界观" className="mt-1.5 max-w-md text-xs" />}
            </div>
            {fields.targetReader === 'male' && (
              <div className="mb-2">
                <label className="text-xs text-muted-foreground mb-1.5 block">流派</label>
                <div className="flex flex-wrap gap-1.5">
                  {MALE_OPTIONS.genre.map(opt => (
                    <span key={opt.value} onClick={() => setField('genre', opt.value)}
                      className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.genre === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                      {opt.label}
                    </span>
                  ))}
                </div>
                {fields.genre === 'custom' && <Input type="text" value={fields.customGenre || ''} onChange={(e) => setField('customGenre', e.target.value)} placeholder="自定义流派" className="mt-1.5 max-w-md text-xs" />}
              </div>
            )}
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">风格偏好</label>
              <div className="flex flex-wrap gap-1.5">
                {INSPIRATION_OPTIONS.stylePreferences.map(opt => (
                  <span key={opt.value} onClick={() => setField('stylePreference', opt.value)}
                    className={`px-2.5 py-1 rounded-full border-2 text-xs cursor-pointer transition-all ${fields.stylePreference === opt.value ? 'bg-primary text-white border-primary' : 'border-gray-200 hover:border-primary/50'}`}>
                    {opt.label}
                  </span>
                ))}
              </div>
            </div>
          </InspirationFieldGroup>

          {/* Prompt 预览 */}
          <InspirationTemplatePreview
            template={template}
            manuallyEdited={templateManuallyEdited}
            onTemplateChange={handleTemplateChange}
            onResetTemplate={handleResetTemplate}
          />
        </div>
      </div>

      {/* 底部操作栏 */}
      <div className="border-t bg-white px-4 py-3">
        <div className="flex items-center gap-3 max-w-3xl mx-auto">
          <div className="flex-1 min-w-0">
            <label className="text-[10px] text-muted-foreground mb-1 flex items-center gap-1" htmlFor="model-select-trigger">
              <Cpu className="h-3 w-3" />AI 模型
            </label>
            <Select value={selectedModelKey} onValueChange={setSelectedModelKey} disabled={loadingModels || modelOptions.length === 0}>
              <SelectTrigger id="model-select-trigger" className="w-full h-8 text-xs">
                <SelectValue placeholder={loadingModels ? '加载中...' : '请选择模型'} />
              </SelectTrigger>
              <SelectContent>{renderModelGroups()}</SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-0">
            <button type="button" onClick={() => setShowReviewModelAdvanced(!showReviewModelAdvanced)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors mb-1">
              <Settings2 className="h-3 w-3" />审核模型
            </button>
            {showReviewModelAdvanced && (
              <Select value={reviewLlmConfigId?.toString() || '__default__'}
                onValueChange={(v) => setReviewLlmConfigId(v === '__default__' ? null : parseInt(v))}>
                <SelectTrigger className="w-full h-8 text-xs">
                  <SelectValue placeholder="使用创作模型（默认）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">使用创作模型（默认）</SelectItem>
                  {renderModelGroups('review-')}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground">{progress.requiredFilled}/{progress.requiredTotal}</span>
            <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all bg-primary"
                style={{ width: `${progress.requiredTotal > 0 ? (progress.requiredFilled / progress.requiredTotal * 100) : 0}%` }} />
            </div>
          </div>
          {hasOutline ? (
            <Button onClick={handleReplanRequest} className="px-4 h-8 text-xs" variant="outline">
              <RefreshCw className="h-3.5 w-3.5 mr-1" />重新规划
            </Button>
          ) : (
            <Button onClick={handleConfirm} disabled={confirming} className="px-4 h-8 text-xs">
              {confirming ? '保存中...' : <><Check className="h-3.5 w-3.5 mr-1" />开始规划</>}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
