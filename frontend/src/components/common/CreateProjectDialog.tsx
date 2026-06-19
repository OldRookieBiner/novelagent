import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { projectsApi, modelConfigsApi } from '@/lib/api'


interface CreateProjectDialogProps
{
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface StageState
{
  concept: boolean
  seed: boolean
  name: boolean
  world: boolean
  characters: boolean
  outline: boolean
  style: boolean
  errors: Record<string, string>
}

// 展平后的模型选项
interface ModelOption {
  configId: number
  modelId?: string
  displayName: string
}

export default function CreateProjectDialog({ open, onOpenChange }: CreateProjectDialogProps)
{
  const navigate = useNavigate()
  const [concept, setConcept] = useState('')
  const [targetWords, setTargetWords] = useState(100000)
  const [modelConfigId, setModelConfigId] = useState<number | null>(null)
  const [modelId, setModelId] = useState<string | undefined>(undefined)
  const [selectedModelKey, setSelectedModelKey] = useState<string>('')

  // 生成模型选项的唯一 key（configId 与 modelId 组合）
  const makeModelKey = (opt: ModelOption) => `${opt.configId}::${opt.modelId ?? ''}`
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [stage, setStage] = useState<StageState>({
    concept: false,
    seed: false,
    name: false,
    world: false,
    characters: false,
    outline: false,
    style: false,
    errors: {},
  })
  const [currentStage, setCurrentStage] = useState('')
  const [progress, setProgress] = useState(0)
  const abortControllerRef = useRef<AbortController | null>(null)

  // 加载模型配置并展平为模型选项列表
  useEffect(() =>
  {
    if (open)
    {
      modelConfigsApi.list().then(configs =>
      {
        const options: ModelOption[] = []
        
        for (const config of configs.models || [])
        {
          if (!config.is_enabled) continue
          
          // 如果有 models 数组（无论 provider_type），遍历它
          if (config.models && config.models.length > 0)
          {
            for (const model of config.models)
            {
              if (model.is_enabled)
              {
                options.push({
                  configId: config.id,
                  modelId: model.id,
                  displayName: `${config.name} - ${model.name}`,
                })
              }
            }
          }
          // 否则使用 model_name（单个模型的情况）
          else if (config.model_name)
          {
            options.push({
              configId: config.id,
              displayName: `${config.name} - ${config.model_name}`,
            })
          }
        }
        
        setModelOptions(options)
        
        // 默认选择 DeepSeek v4 Pro
        const deepseekPro = options.find(o => 
          o.displayName.toLowerCase().includes('deepseek') && 
          o.displayName.toLowerCase().includes('pro')
        )
        if (deepseekPro)
        {
          setModelConfigId(deepseekPro.configId)
          setModelId(deepseekPro.modelId)
          setSelectedModelKey(`${deepseekPro.configId}::${deepseekPro.modelId ?? ''}`)
        }
        else if (options.length > 0)
        {
          setModelConfigId(options[0].configId)
          setModelId(options[0].modelId)
          setSelectedModelKey(`${options[0].configId}::${options[0].modelId ?? ''}`)
        }
      }).catch(() => {})
    }
  }, [open])

  const handleCreate = async () =>
  {
    if (!concept.trim()) 
    {
      setError('请输入概念描述')
      return
    }

    // 创建 AbortController 用于取消请求
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    setCreating(true)
    setError('')
    setProgress(0)
    setStage({
      concept: false,
      seed: false,
      name: false,
      world: false,
      characters: false,
      outline: false,
      style: false,
      errors: {},
    })

    try
    {
      const result = await projectsApi.initialize(
        concept.trim(),
        {
          onEvent: (type: string, data: Record<string, unknown>) =>
          {
            const stageNames: Record<string, string> = {
              concept: '解析概念',
              seed: '生成故事种子',
              name: '生成小说名',
              world: '生成世界观',
              characters: '生成角色',
              outline: '生成大纲',
              style: '设定风格',
            }
            
            if (type === 'start' || type === 'init:start')
            {
              setCurrentStage('正在开始...')
              setProgress(5)
            }
            else if (type === 'init:concept')
            {
              setStage(s => ({ ...s, concept: true }))
              setCurrentStage(stageNames.concept)
              setProgress(15)
            }
            else if (type === 'init:novel_name')
            {
              setStage(s => ({ ...s, name: true, seed: true }))
              setCurrentStage(stageNames.name)
              setProgress(30)
            }
            else if (type === 'init:world')
            {
              setStage(s => ({ ...s, world: true }))
              setCurrentStage(stageNames.world)
              setProgress(45)
            }
            else if (type === 'init:characters')
            {
              setStage(s => ({ ...s, characters: true }))
              setCurrentStage(stageNames.characters)
              setProgress(60)
            }
            else if (type === 'init:outline')
            {
              setStage(s => ({ ...s, outline: true }))
              setCurrentStage(stageNames.outline)
              setProgress(80)
            }
            else if (type === 'init:style')
            {
              setStage(s => ({ ...s, style: true }))
              setCurrentStage(stageNames.style)
              setProgress(95)
            }
            else if (type === 'init:error')
            {
              const stageName = data.stage as string
              const errorMsg = data.error as string
              const stageKeyMap: Record<string, string | null> = {
                story_seed: 'seed',
                novel_name: 'name',
                world_setting: 'world',
                characters: 'characters',
                outline: 'outline',
                style: 'style',
                llm_init: null,
              }
              const key = stageKeyMap[stageName]
              if (key)
              {
                setStage(s => ({ ...s, [key]: true, errors: { ...s.errors, [key]: errorMsg } }))
              }
            }
            else if (type === 'init:cancelled')
            {
              setError('创建已取消')
            }
            else if (type === 'init:timeout')
            {
              setError('创建超时，AI 长时间未响应，请检查模型配置后重试')
            }
            else if (type === 'init:done')
            {
              if (data.status === 'partial')
              {
                setError('部分步骤失败，项目已创建但可能不完整')
              }
              setProgress(100)
            }
          },
        },
        targetWords,
        modelConfigId || undefined,
        modelId || undefined,
        abortController.signal
      )

      // 只有当初始化成功完成时才跳转到工作台
      // status 为 complete 时项目已完整创建；timeout/partial/cancelled 时项目已被删除或未完成
      if (result.status === 'complete' && result.project_id)
      {
        setConcept('')
        setTargetWords(100000)
        onOpenChange(false)
        
        setTimeout(() =>
        {
          navigate(`/project/${result.project_id}/workbench`)
        }, 500)
      }
      else if (result.cancelled)
      {
        // 用户主动取消，不跳转
      }
      else
      {
        // 超时或部分失败，项目已被后端删除，停留在当前页面并显示错误
        setError('项目创建失败，请重试')
      }
    } catch (err)
    {
      // AbortError 是用户主动取消，不显示错误
      if (err instanceof Error && err.name === 'AbortError')
      {
        return
      }
      setError(err instanceof Error ? err.message : '创建项目失败')
    } finally
    {
      setCreating(false)
      abortControllerRef.current = null
    }
  }

  const handleCancel = () =>
  {
    // 只发送 abort 信号，状态重置由 finally 块统一处理
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }

  const handleOpenChange = (isOpen: boolean) =>
  {
    // 创建中不允许关闭弹框
    if (creating && !isOpen)
    {
      return
    }
    if (!isOpen)
    {
      setConcept('')
      setTargetWords(100000)
      setModelConfigId(null)
      setModelId(undefined)
      setSelectedModelKey('')
      setError('')
      setStage({
        concept: false,
        seed: false,
        name: false,
        world: false,
        characters: false,
        outline: false,
        style: false,
      errors: {},
      })
      setProgress(0)
    }
    onOpenChange(isOpen)
  }

  const stages = [
    { key: 'concept', label: '解析概念', done: stage.concept },
    { key: 'seed', label: '生成故事种子', done: stage.seed },
    { key: 'name', label: '生成小说名', done: stage.name },
    { key: 'world', label: '生成世界观', done: stage.world },
    { key: 'characters', label: '生成角色', done: stage.characters },
    { key: 'outline', label: '生成大纲', done: stage.outline },
    { key: 'style', label: '设定风格', done: stage.style },
  ]

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>创建新项目</DialogTitle>
          <DialogDescription>告诉我你的小说想法，AI 会帮你构建基础设定</DialogDescription>
        </DialogHeader>
        
        {!creating ? (
          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-2">
                概念描述
              </label>
              <Textarea
                placeholder="例如：我想写一个关于人工智能觉醒的故事..."
                value={concept}
                onChange={(e) => { setConcept(e.target.value); setError('') }}
                className="min-h-[100px]"
                maxLength={5000}
              />
              <p className="text-xs text-gray-500 mt-1">
                尽量详细地描述你的想法，AI 会据此生成世界观、角色和大纲
              </p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-2">
                  目标字数
                </label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={targetWords}
                    onChange={(e) => setTargetWords(parseInt(e.target.value) || 100000)}
                    min={10000}
                    max={1000000}
                    step={10000}
                    className="w-24"
                  />
                  <span className="text-gray-500">字</span>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 block mb-2">
                  使用模型
                </label>
                <select
                  value={selectedModelKey}
                  onChange={(e) => {
                    const key = e.target.value
                    setSelectedModelKey(key)
                    if (!key) {
                      setModelConfigId(null)
                      setModelId(undefined)
                    } else {
                      const opt = modelOptions.find(o => makeModelKey(o) === key)
                      if (opt) {
                        setModelConfigId(opt.configId)
                        setModelId(opt.modelId)
                      }
                    }
                  }}
                  className="w-full h-10 px-3 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="">默认模型</option>
                  {modelOptions.map(option => (
                    <option key={makeModelKey(option)} value={makeModelKey(option)}>
                      {option.displayName}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
          </div>
        ) : (
          <div className="space-y-4 py-2">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-500">进度</span>
                <span className="font-medium text-indigo-600">{progress}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-3 space-y-1">
              {stages.map((s) => {
                const hasError = stage.errors[s.key]
                return (
                  <div
                    key={s.key}
                    className={`flex items-center text-sm ${
                      hasError ? 'text-red-500' :
                      s.done ? 'text-gray-500' :
                      (stage as any)[s.key] ? 'text-indigo-600 font-medium' :
                      'text-gray-300'
                    }`}
                  >
                    <span className={`w-5 h-5 rounded-full border-2 border-current flex items-center justify-center mr-2 text-xs ${
                      hasError ? 'bg-red-50' : ''
                    }`}>
                      {hasError ? '✗' : s.done ? '✓' : (stage as any)[s.key] ? '●' : '○'}
                    </span>
                    <span className="flex-1">{s.label}</span>
                    {hasError && (
                      <span className="text-[10px] text-red-400 truncate max-w-[120px]" title={hasError}>
                        失败
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}

            <p className="text-center text-xs text-gray-400">
              {currentStage || '正在准备...'}
            </p>
          </div>
        )}
        
        <DialogFooter>
          {creating ? (
            <Button variant="outline" onClick={handleCancel}>
              取消创建
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button 
                onClick={handleCreate} 
                disabled={!concept.trim()}
              >
                创建项目
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
