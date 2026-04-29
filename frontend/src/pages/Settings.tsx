import { useState, useEffect } from 'react'
import { useSettings } from '@/components/settings/hooks/useSettings'
import ModelConfigPanel from '@/components/settings/ModelConfigPanel'
import ReviewConfigPanel from '@/components/settings/ReviewConfigPanel'
import AgentPromptPanel from '@/components/settings/AgentPromptPanel'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

const SETTINGS_TABS = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
  { id: 'agents', label: '智能体管理' },
] as const

type SettingsTab = typeof SETTINGS_TABS[number]['id']

export default function Settings()
{
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const {
    loading,
    // 模型配置
    modelConfigs,
    configsLoading,
    showConfigDialog,
    savingConfig,
    editingConfig,
    loadModelConfigs,
    handleSaveModel,
    handleEditModel,
    handleAddModel,
    handleSetDefault,
    handleDeleteModel,
    handleCheckHealth,
    handleCloseConfigDialog,
    // 审核设置
    reviewMode,
    setReviewMode,
    maxRewriteCount,
    setMaxRewriteCount,
    workflowMode,
    setWorkflowMode,
    saving,
    saved,
    handleSaveReviewSettings,
    // 系统提示词
    prompts,
    promptsLoading,
    loadPrompts,
    selectedAgent,
    setSelectedAgent,
    editContent,
    setEditContent,
    savingPrompt,
    resettingPrompt,
    handleSavePrompt,
    handleResetPrompt,
  } = useSettings()

  // 切换到模型配置 tab 时加载
  useEffect(() =>
  {
    if (activeTab === 'model')
    {
      loadModelConfigs()
    }
  }, [activeTab, loadModelConfigs])

  // 切换到智能体管理 tab 时加载
  useEffect(() =>
  {
    if (activeTab === 'agents')
    {
      loadPrompts()
    }
  }, [activeTab, loadPrompts])

  if (loading)
  {
    return <LoadingSpinner fullPage text="加载中..." />
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
          {activeTab === 'model' && (
            <ModelConfigPanel
              modelConfigs={modelConfigs}
              configsLoading={configsLoading}
              onSetDefault={handleSetDefault}
              onEdit={handleEditModel}
              onDelete={handleDeleteModel}
              onCheckHealth={handleCheckHealth}
              onAdd={handleAddModel}
              showConfigDialog={showConfigDialog}
              savingConfig={savingConfig}
              editingConfig={editingConfig}
              onSaveModel={handleSaveModel}
              onCloseConfigDialog={handleCloseConfigDialog}
            />
          )}

          {activeTab === 'review' && (
            <ReviewConfigPanel
              reviewMode={reviewMode}
              maxRewriteCount={maxRewriteCount}
              onReviewModeChange={setReviewMode}
              onMaxRewriteCountChange={setMaxRewriteCount}
              workflowMode={workflowMode}
              onWorkflowModeChange={setWorkflowMode}
              saving={saving}
              saved={saved}
              onSave={handleSaveReviewSettings}
            />
          )}

          {activeTab === 'agents' && (
            <AgentPromptPanel
              prompts={prompts}
              promptsLoading={promptsLoading}
              selectedAgent={selectedAgent}
              editContent={editContent}
              savingPrompt={savingPrompt}
              resettingPrompt={resettingPrompt}
              onAgentChange={setSelectedAgent}
              onContentChange={setEditContent}
              onSave={handleSavePrompt}
              onReset={handleResetPrompt}
            />
          )}
        </div>
      </div>
    </div>
  )
}
