import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { AGENT_TABS, type AgentTab } from './hooks/useSettings'
import type { SystemPrompt } from '@/types'

interface AgentPromptPanelProps
{
  prompts: SystemPrompt[]
  promptsLoading: boolean
  selectedAgent: AgentTab
  editContent: string
  savingPrompt: boolean
  resettingPrompt: boolean
  onAgentChange: (agent: AgentTab) => void
  onContentChange: (content: string) => void
  onSave: () => Promise<void>
  onReset: () => Promise<void>
}

export default function AgentPromptPanel({
  prompts,
  promptsLoading,
  selectedAgent,
  editContent,
  savingPrompt,
  resettingPrompt,
  onAgentChange,
  onContentChange,
  onSave,
  onReset,
}: AgentPromptPanelProps)
{
  const currentPrompt = prompts.find((p) => p.agent_type === selectedAgent)

  return (
    <div id="agents-panel" role="tabpanel" className="max-w-4xl flex flex-col" style={{ height: 'calc(100vh - 200px)' }}>
      <h3 className="text-lg font-semibold mb-1">智能体管理</h3>
      <p className="text-muted-foreground text-sm mb-6">配置系统级 Prompt 模板</p>

      {promptsLoading ? (
        <LoadingSpinner text="加载中..." />
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          {/* 标签切换 */}
          <div className="border-b mb-4 shrink-0">
            <div className="flex">
              {AGENT_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => onAgentChange(tab.id)}
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
            <div className="flex-1 flex flex-col min-h-0">
              {/* 变量提示 - 带释义 */}
              <div className="p-4 bg-muted rounded-lg mb-4 shrink-0">
                <div className="text-sm text-muted-foreground mb-2">可用变量（悬停查看说明）</div>
                <div className="flex flex-wrap gap-2">
                  {currentPrompt.variables.map((v) => (
                    <div key={v} className="group relative">
                      <code className="bg-background px-2 py-1 rounded text-sm cursor-help border border-transparent hover:border-primary transition-colors">
                        {`{${v}}`}
                      </code>
                      {/* 悬停显示释义 */}
                      <div className="absolute bottom-full left-0 mb-2 px-3 py-2 bg-foreground text-background text-xs rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 min-w-[180px] max-w-[350px] whitespace-normal">
                        <span className="font-medium">{v}:</span>{' '}
                        {currentPrompt.variable_descriptions?.[v] || '无说明'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 编辑器 */}
              <Textarea
                value={editContent}
                onChange={(e) => onContentChange(e.target.value)}
                className="flex-1 min-h-0 font-mono text-sm resize-none"
              />

              {/* 操作按钮 */}
              <div className="mt-4 flex items-center justify-between shrink-0">
                <div className="text-sm text-muted-foreground">
                  {currentPrompt.updated_at && `上次更新：${new Date(currentPrompt.updated_at).toLocaleString()}`}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={onReset} disabled={resettingPrompt}>
                    {resettingPrompt ? '重置中...' : '重置默认'}
                  </Button>
                  <Button onClick={onSave} disabled={savingPrompt}>
                    {savingPrompt ? '保存中...' : '保存'}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
