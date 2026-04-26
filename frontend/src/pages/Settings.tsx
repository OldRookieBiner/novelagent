import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'
import { settingsApi, systemPromptsApi, modelConfigsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import ModelConfigItem from '@/components/settings/ModelConfigItem'
import ModelConfigDialog from '@/components/settings/ModelConfigDialog'
import { ReviewModeSelect } from '@/components/project/ReviewModeSelect'
import type { SettingsUpdate, SystemPrompt, ModelConfig, ModelConfigCreate, WorkflowMode } from '@/types'

const SETTINGS_TABS = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
  { id: 'agents', label: '智能体管理' },
] as const

type SettingsTab = typeof SETTINGS_TABS[number]['id']

// Agent type labels for tabs
const AGENT_TABS = [
  { id: 'outline_generation', label: '大纲生成' },
  { id: 'chapter_outline_generation', label: '章节大纲' },
  { id: 'chapter_content_generation', label: '正文生成' },
  { id: 'review', label: '审核' },
  { id: 'rewrite', label: '重写' },
] as const

type AgentTab = typeof AGENT_TABS[number]['id']

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // 模型配置状态
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [configsLoading, setConfigsLoading] = useState(false)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null)

  // 审核设置状态
  const [reviewMode, setReviewMode] = useState<'off' | 'manual' | 'auto'>('manual')
  const [maxRewriteCount, setMaxRewriteCount] = useState(3)

  // 工作流模式状态
  const workflowMode = useSettingsStore((state) => state.workflowMode)
  const setWorkflowMode = useSettingsStore((state) => state.setWorkflowMode)

  // 系统提示词状态
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [promptsLoading, setPromptsLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentTab>('outline_generation')
  const [editContent, setEditContent] = useState('')
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [resettingPrompt, setResettingPrompt] = useState(false)

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await settingsApi.get()
        if (!data.review_enabled) {
          setReviewMode('off')
        } else {
          setReviewMode('manual')
        }
        useSettingsStore.getState().setSettings(data)
      } catch (err) {
        console.error('Failed to fetch settings:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  // 加载模型配置
  const loadModelConfigs = async () => {
    setConfigsLoading(true)
    try {
      const data = await modelConfigsApi.list()
      setModelConfigs(data.models)
    } catch (err) {
      console.error('Failed to load model configs:', err)
    } finally {
      setConfigsLoading(false)
    }
  }

  // 切换到模型配置 tab 时加载
  useEffect(() => {
    if (activeTab === 'model') {
      loadModelConfigs()
    }
  }, [activeTab])

  // 加载系统提示词
  useEffect(() => {
    if (activeTab === 'agents') {
      loadPrompts()
    }
  }, [activeTab])

  // 当 prompts 加载后，更新编辑内容
  useEffect(() => {
    const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)
    if (currentPrompt) {
      setEditContent(currentPrompt.prompt_content)
    }
  }, [prompts, selectedAgent])

  const loadPrompts = async () => {
    setPromptsLoading(true)
    try {
      const data = await systemPromptsApi.list()
      setPrompts(data.prompts)
    } catch (err) {
      console.error('Failed to load system prompts:', err)
    } finally {
      setPromptsLoading(false)
    }
  }

  const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)

  const handleSavePrompt = async () => {
    if (!currentPrompt) return
    setSavingPrompt(true)
    try {
      const updated = await systemPromptsApi.update(selectedAgent, { prompt_content: editContent })
      setPrompts((prev) =>
        prev.map((p) => (p.agent_type === selectedAgent ? updated : p))
      )
    } catch (err) {
      console.error('Failed to save prompt:', err)
    } finally {
      setSavingPrompt(false)
    }
  }

  const handleResetPrompt = async () => {
    if (!confirm('确定要重置为默认值吗？您的修改将丢失。')) return
    setResettingPrompt(true)
    try {
      const updated = await systemPromptsApi.reset(selectedAgent)
      setPrompts((prev) =>
        prev.map((p) => (p.agent_type === selectedAgent ? updated : p))
      )
      setEditContent(updated.prompt_content)
    } catch (err) {
      console.error('Failed to reset prompt:', err)
    } finally {
      setResettingPrompt(false)
    }
  }

  // 保存审核设置
  const handleSaveReviewSettings = async () => {
    setSaving(true)
    setSaved(false)

    try {
      const update: SettingsUpdate = {
        review_enabled: reviewMode !== 'off',
        review_strictness: 'standard',
      }

      const updated = await settingsApi.update(update)
      useSettingsStore.getState().setSettings(updated)
      setSaved(true)
    } catch (err) {
      console.error('Failed to save settings:', err)
    } finally {
      setSaving(false)
    }
  }

  // 添加或更新模型配置
  const handleSaveModel = async (data: ModelConfigCreate) => {
    setSavingConfig(true)
    try {
      if (editingConfig) {
        await modelConfigsApi.update(editingConfig.id, data)
      } else {
        await modelConfigsApi.create(data)
      }
      await loadModelConfigs()
    } finally {
      setSavingConfig(false)
    }
  }

  // 打开编辑对话框
  const handleEditModel = (config: ModelConfig) => {
    setEditingConfig(config)
    setShowConfigDialog(true)
  }

  // 打开新增对话框
  const handleAddModel = () => {
    setEditingConfig(null)
    setShowConfigDialog(true)
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
  }

  return (
    <div className="flex flex-1">
      {/* 左侧导航栏 */}
      <nav className="w-[220px] border-r bg-background">
        <div className="p-4 border-b">
          <h2 className="font-semibold">设置</h2>
        </div>
        <div className="p-3 space-y-1" role="tablist">
          {SETTINGS_TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full px-3 py-2 text-sm rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-secondary text-foreground font-medium'
                  : 'bg-transparent text-muted-foreground hover:bg-secondary/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* 右侧内容区 */}
      <div className="flex-1 p-6 flex flex-col">
        <div className="flex-1">
          {/* 模型配置 */}
          {activeTab === 'model' && (
            <div id="model-panel" role="tabpanel" className="max-w-2xl">
              <h3 className="text-lg font-semibold mb-1">模型配置</h3>
              <p className="text-muted-foreground text-sm mb-6">管理 AI 模型配置，设置默认模型</p>

              {configsLoading ? (
                <div className="text-muted-foreground">加载中...</div>
              ) : (
                <>
                  {modelConfigs.map((config) => (
                    <ModelConfigItem
                      key={config.id}
                      config={config}
                      onSetDefault={async () => {
                        try {
                          await modelConfigsApi.setDefault(config.id)
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Failed to set default:', err)
                        }
                      }}
                      onEdit={handleEditModel}
                      onDelete={config.is_default ? undefined : async () => {
                        if (!confirm('确定要删除这个模型配置吗？')) return
                        try {
                          await modelConfigsApi.delete(config.id)
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Failed to delete:', err)
                        }
                      }}
                      onRefresh={async () => {
                        try {
                          await modelConfigsApi.checkHealth(config.id)
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Health check failed:', err)
                        }
                      }}
                    />
                  ))}

                  {/* 添加自定义模型按钮 */}
                  <button
                    onClick={handleAddModel}
                    className="w-full border-2 border-dashed border-gray-300 rounded-lg p-4 text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-all"
                  >
                    + 添加自定义模型
                  </button>
                </>
              )}
            </div>
          )}

          {/* 审核设置 */}
          {activeTab === 'review' && (
            <div id="review-panel" role="tabpanel" className="max-w-xl">
              <h3 className="text-lg font-semibold mb-1">审核设置</h3>
              <p className="text-muted-foreground text-sm mb-6">配置章节审核行为</p>

              <ReviewModeSelect
                value={reviewMode}
                maxRewriteCount={maxRewriteCount}
                onValueChange={setReviewMode}
                onMaxRewriteChange={setMaxRewriteCount}
              />

              {/* 工作流模式设置 */}
              <div className="mt-8 pt-6 border-t">
                <h4 className="font-medium mb-1">工作流模式</h4>
                <p className="text-muted-foreground text-sm mb-4">选择小说创作的自动化程度</p>

                <RadioGroup
                  value={workflowMode}
                  onValueChange={(value) => setWorkflowMode(value as WorkflowMode)}
                  className="space-y-3"
                >
                  {/* 逐步确认模式 */}
                  <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                    <RadioGroupItem value="step_by_step" id="step_by_step" className="mt-0.5" />
                    <div className="space-y-1">
                      <Label htmlFor="step_by_step" className="cursor-pointer font-medium">
                        逐步确认模式
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        每个步骤完成后暂停，等待您确认后继续
                      </p>
                    </div>
                  </div>

                  {/* 智能混合模式（推荐） */}
                  <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                    <RadioGroupItem value="hybrid" id="hybrid" className="mt-0.5" />
                    <div className="space-y-1">
                      <Label htmlFor="hybrid" className="cursor-pointer font-medium">
                        智能混合模式（推荐）
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        大纲和章节大纲需要确认，正文自动生成
                      </p>
                    </div>
                  </div>

                  {/* 全自动模式 */}
                  <div className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                    <RadioGroupItem value="auto" id="auto" className="mt-0.5" />
                    <div className="space-y-1">
                      <Label htmlFor="auto" className="cursor-pointer font-medium">
                        全自动模式
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        一键完成，仅在审核不通过时暂停
                      </p>
                    </div>
                  </div>
                </RadioGroup>
              </div>

              <div className="mt-6 pt-4 border-t">
                <div className="flex items-center gap-4">
                  <Button onClick={handleSaveReviewSettings} disabled={saving}>
                    {saving ? '保存中...' : '保存设置'}
                  </Button>
                  {saved && (
                    <span className="text-sm text-green-600">已保存</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 智能体管理 */}
          {activeTab === 'agents' && (
            <div id="agents-panel" role="tabpanel" className="max-w-4xl">
              <h3 className="text-lg font-semibold mb-1">智能体管理</h3>
              <p className="text-muted-foreground text-sm mb-6">配置系统级 Prompt 模板</p>

              {promptsLoading ? (
                <div className="text-muted-foreground">加载中...</div>
              ) : (
                <>
                  {/* 标签切换 */}
                  <div className="border-b mb-4">
                    <div className="flex">
                      {AGENT_TABS.map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setSelectedAgent(tab.id)}
                          className={`px-4 py-2 text-sm transition-colors ${
                            selectedAgent === tab.id
                              ? 'bg-background border-b-2 border-primary font-medium text-foreground'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 编辑区 */}
                  {currentPrompt && (
                    <>
                      {/* 变量提示 */}
                      <div className="p-4 bg-muted rounded-lg mb-4">
                        <div className="text-sm text-muted-foreground mb-2">可用变量</div>
                        <div className="flex flex-wrap gap-2">
                          {currentPrompt.variables.map((v) => (
                            <code key={v} className="bg-background px-2 py-1 rounded text-sm">
                              {`{${v}}`}
                            </code>
                          ))}
                        </div>
                      </div>

                      {/* 编辑器 */}
                      <Textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="min-h-[400px] font-mono text-sm"
                      />

                      {/* 操作按钮 */}
                      <div className="mt-4 flex items-center justify-between">
                        <div className="text-sm text-muted-foreground">
                          {currentPrompt.updated_at && `上次更新：${new Date(currentPrompt.updated_at).toLocaleString()}`}
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" onClick={handleResetPrompt} disabled={resettingPrompt}>
                            {resettingPrompt ? '重置中...' : '重置默认'}
                          </Button>
                          <Button onClick={handleSavePrompt} disabled={savingPrompt}>
                            {savingPrompt ? '保存中...' : '保存'}
                          </Button>
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 模型配置弹窗 */}
      <ModelConfigDialog
        open={showConfigDialog}
        onClose={() => {
          setShowConfigDialog(false)
          setEditingConfig(null)
        }}
        onSubmit={handleSaveModel}
        loading={savingConfig}
        editConfig={editingConfig}
      />
    </div>
  )
}
