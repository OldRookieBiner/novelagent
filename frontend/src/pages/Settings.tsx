import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { settingsApi, agentPromptsApi, projectsApi, modelConfigsApi } from '@/lib/api'
import { useSettingsStore } from '@/stores/settingsStore'
import { AgentPromptEditor } from '@/components/settings/AgentPromptEditor'
import { ProjectPromptConfig } from '@/components/settings/ProjectPromptConfig'
import ModelConfigCard from '@/components/settings/ModelConfigCard'
import AddModelDialog from '@/components/settings/AddModelDialog'
import type { SettingsUpdate, AgentPrompt, Project, ModelConfig, ModelConfigCreate } from '@/types'

const REVIEW_STRICTNESS = [
  { value: 'loose', label: '宽松' },
  { value: 'standard', label: '标准' },
  { value: 'strict', label: '严格' },
] as const

type ReviewStrictnessValue = typeof REVIEW_STRICTNESS[number]['value']

const SETTINGS_TABS = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
  { id: 'agents', label: '智能体管理' },
] as const

type SettingsTab = typeof SETTINGS_TABS[number]['id']

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // 模型配置状态
  const [modelConfigs, setModelConfigs] = useState<ModelConfig[]>([])
  const [configsLoading, setConfigsLoading] = useState(false)
  const [checkingHealthId, setCheckingHealthId] = useState<number | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [editingConfig, setEditingConfig] = useState<ModelConfig | null>(null)
  const [editApiKey, setEditApiKey] = useState('')
  const [savingConfig, setSavingConfig] = useState(false)

  // 审核设置状态
  const [reviewEnabled, setReviewEnabled] = useState(true)
  const [reviewStrictness, setReviewStrictness] = useState<ReviewStrictnessValue>('standard')

  // Agent prompts 状态
  const [globalPrompts, setGlobalPrompts] = useState<AgentPrompt[]>([])
  const [promptsLoading, setPromptsLoading] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await settingsApi.get()
        setReviewEnabled(data.review_enabled)
        setReviewStrictness(data.review_strictness as ReviewStrictnessValue)
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

  // Load agent prompts when tab is switched to agents
  useEffect(() => {
    if (activeTab === 'agents') {
      loadAgentPrompts()
      loadProjects()
    }
  }, [activeTab])

  const loadAgentPrompts = async () => {
    setPromptsLoading(true)
    try {
      const data = await agentPromptsApi.getGlobal()
      setGlobalPrompts(data.prompts)
    } catch (err) {
      console.error('Failed to load agent prompts:', err)
    } finally {
      setPromptsLoading(false)
    }
  }

  const loadProjects = async () => {
    try {
      const data = await projectsApi.list()
      setProjects(data.projects)
    } catch (err) {
      console.error('Failed to load projects:', err)
    }
  }

  const handleSavePrompt = async (agentType: string, content: string) => {
    await agentPromptsApi.updateGlobal(agentType, { prompt_content: content })
    // Update local state
    setGlobalPrompts((prev) =>
      prev.map((p) =>
        p.agent_type === agentType
          ? { ...p, prompt_content: content, is_default: false }
          : p
      )
    )
  }

  const handleResetPrompt = async (agentType: string) => {
    const updated = await agentPromptsApi.resetGlobal(agentType)
    setGlobalPrompts((prev) =>
      prev.map((p) => (p.agent_type === agentType ? updated : p))
    )
  }

  // 保存审核设置
  const handleSaveReviewSettings = async () => {
    setSaving(true)
    setSaved(false)

    try {
      const update: SettingsUpdate = {
        review_enabled: reviewEnabled,
        review_strictness: reviewStrictness,
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

  // 添加自定义模型
  const handleAddModel = async (data: ModelConfigCreate) => {
    setSavingConfig(true)
    try {
      await modelConfigsApi.create(data)
      await loadModelConfigs()
    } finally {
      setSavingConfig(false)
    }
  }

  // 保存编辑的 API Key
  const handleSaveEditApiKey = async () => {
    if (!editingConfig || !editApiKey.trim()) return

    setSavingConfig(true)
    try {
      await modelConfigsApi.update(editingConfig.id, { api_key: editApiKey })
      setEditingConfig(null)
      setEditApiKey('')
      await loadModelConfigs()
    } finally {
      setSavingConfig(false)
    }
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
                    <ModelConfigCard
                      key={config.id}
                      config={config}
                      checkingHealth={checkingHealthId === config.id}
                      onHealthCheck={async () => {
                        setCheckingHealthId(config.id)
                        try {
                          await modelConfigsApi.checkHealth(config.id)
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Health check failed:', err)
                        } finally {
                          setCheckingHealthId(null)
                        }
                      }}
                      onEdit={() => {
                        setEditingConfig(config)
                        setEditApiKey('')
                      }}
                      onToggleStatus={async () => {
                        try {
                          if (config.is_enabled) {
                            // 停用模型
                            await modelConfigsApi.update(config.id, { is_enabled: false })
                          } else {
                            // 启用模型并设为默认
                            await modelConfigsApi.update(config.id, { is_enabled: true })
                            await modelConfigsApi.setDefault(config.id)
                          }
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Failed to toggle status:', err)
                        }
                      }}
                      onDelete={!config.is_default ? async () => {
                        if (!confirm('确定要删除这个模型配置吗？')) return
                        try {
                          await modelConfigsApi.delete(config.id)
                          await loadModelConfigs()
                        } catch (err) {
                          console.error('Failed to delete:', err)
                        }
                      } : undefined}
                    />
                  ))}

                  {/* 添加自定义模型按钮 */}
                  <button
                    onClick={() => setShowAddDialog(true)}
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

              <div className="space-y-4">
                <div className="flex items-center justify-between py-2">
                  <label className="text-sm font-medium">启用审核</label>
                  <input
                    type="checkbox"
                    checked={reviewEnabled}
                    onChange={(e) => setReviewEnabled(e.target.checked)}
                    className="h-4 w-4"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">审核严格度</label>
                  <select
                    className="w-full h-10 px-3 rounded-md border border-input bg-background"
                    value={reviewStrictness}
                    onChange={(e) => setReviewStrictness(e.target.value as ReviewStrictnessValue)}
                    disabled={!reviewEnabled}
                  >
                    {REVIEW_STRICTNESS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
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
            <div id="agents-panel" role="tabpanel" className="max-w-3xl">
              <h3 className="text-lg font-semibold mb-1">智能体管理</h3>
              <p className="text-muted-foreground text-sm mb-6">管理全局 Prompt 模板和项目级自定义</p>

              {selectedProject ? (
                <div className="mb-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedProject(null)}
                    className="mb-4"
                  >
                    &larr; 返回项目列表
                  </Button>
                  <ProjectPromptConfig
                    projectId={selectedProject.id}
                    projectName={selectedProject.name}
                    onClose={() => setSelectedProject(null)}
                  />
                </div>
              ) : (
                <>
                  {/* Global Prompts Section */}
                  <div className="mb-8">
                    <h4 className="font-medium mb-3">全局 Prompt 模板</h4>
                    {promptsLoading ? (
                      <div className="text-muted-foreground">加载中...</div>
                    ) : (
                      globalPrompts.map((prompt) => (
                        <AgentPromptEditor
                          key={prompt.agent_type}
                          prompt={prompt}
                          onSave={(content) => handleSavePrompt(prompt.agent_type, content)}
                          onReset={() => handleResetPrompt(prompt.agent_type)}
                        />
                      ))
                    )}
                  </div>

                  {/* Projects Section */}
                  <div>
                    <h4 className="font-medium mb-3">项目级自定义</h4>
                    {projects.length === 0 ? (
                      <div className="text-muted-foreground text-sm">暂无项目</div>
                    ) : (
                      <div className="border rounded-lg divide-y">
                        {projects.map((project) => (
                          <div
                            key={project.id}
                            className="p-3 flex items-center justify-between hover:bg-gray-50"
                          >
                            <div>
                              <div className="font-medium">{project.name}</div>
                              <div className="text-sm text-muted-foreground">
                                {project.total_words} 字 / {project.stage}
                              </div>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setSelectedProject(project)}
                            >
                              管理
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 添加模型弹窗 */}
      <AddModelDialog
        open={showAddDialog}
        onClose={() => setShowAddDialog(false)}
        onSubmit={handleAddModel}
        loading={savingConfig}
      />

      {/* 编辑 API Key 弹窗 */}
      {editingConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-[420px] max-w-[90vw]">
            <div className="text-lg font-medium mb-4">配置 API Key</div>
            <div className="text-sm text-gray-600 mb-4">
              为 <strong>{editingConfig.name}</strong> 配置 API Key
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">API Key</label>
                <Input
                  type="password"
                  value={editApiKey}
                  onChange={(e) => setEditApiKey(e.target.value)}
                  placeholder="输入 API Key"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <Button variant="outline" onClick={() => {
                setEditingConfig(null)
                setEditApiKey('')
              }}>
                取消
              </Button>
              <Button onClick={handleSaveEditApiKey} disabled={savingConfig || !editApiKey.trim()}>
                {savingConfig ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
