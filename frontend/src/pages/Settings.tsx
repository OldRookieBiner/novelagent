import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Monitor, Shield, Bot, ArrowLeft } from 'lucide-react'
import { useSettings } from '@/components/settings/hooks/useSettings'
import Header from '@/components/layout/Header'
import ModelConfigPanel from '@/components/settings/ModelConfigPanel'
import ReviewConfigPanel from '@/components/settings/ReviewConfigPanel'
import AgentPromptPanel from '@/components/settings/AgentPromptPanel'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const SETTINGS_NAV = [
  {
    group: '配置',
    items: [
      { id: 'model' as const, label: '模型配置', icon: Monitor },
      { id: 'review' as const, label: '审核设置', icon: Shield },
    ],
  },
  {
    group: '智能体',
    items: [
      { id: 'agents' as const, label: 'Prompt 管理', icon: Bot },
    ],
  },
]

type SettingsTab = 'model' | 'review' | 'agents'

export default function Settings()
{
  const [activeTab, setActiveTab] = useState<SettingsTab>('model')
  const navigate = useNavigate()
  const {
    loading,
    // 模型配置
    modelConfigs,
    configsLoading,
    selectedConfigId,
    savingConfig,
    loadModelConfigs,
    handleSaveModel,
    handleSetDefault,
    handleDeleteModel,
    handleCheckHealth,
    handleToggleEnabled,
    handleSelectConfig,
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
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 页面 Header */}
      <header className="h-14 border-b bg-white flex items-center px-6 shrink-0">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors mr-4"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="text-sm">返回</span>
        </button>
        <h1 className="text-lg font-semibold">系统设置</h1>
      </header>

      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧导航栏 */}
        <nav className="w-[200px] border-r bg-white shrink-0" role="tablist">
          {SETTINGS_NAV.map((group) => (
            <div key={group.group}>
              <div className="px-4 pt-4 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {group.group}
              </div>
              {group.items.map((item) =>
              {
                const Icon = item.icon
                return (
                  <button
                    key={item.id}
                    role="tab"
                    aria-selected={activeTab === item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                      activeTab === item.id
                        ? 'text-primary bg-primary/10 border-r-2 border-primary font-medium'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    )}
                  >
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* 右侧内容区 */}
        <main className="flex-1 p-6 overflow-auto">
          {activeTab === 'model' && (
            <ModelConfigPanel
              modelConfigs={modelConfigs}
              configsLoading={configsLoading}
              selectedConfigId={selectedConfigId}
              savingConfig={savingConfig}
              onSaveModel={handleSaveModel}
              onSetDefault={handleSetDefault}
              onDeleteModel={handleDeleteModel}
              onCheckHealth={handleCheckHealth}
              onToggleEnabled={handleToggleEnabled}
              onSelectConfig={handleSelectConfig}
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
        </main>
      </div>
    </div>
  )
}
