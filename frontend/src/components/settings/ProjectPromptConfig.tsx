import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { agentPromptsApi } from '@/lib/api'
import type { ProjectAgentPromptItem } from '@/types'

interface ProjectPromptConfigProps {
  projectId: number
  projectName: string
  initialAgents?: ProjectAgentPromptItem[]
  onClose?: () => void
}

export function ProjectPromptConfig({
  projectId,
  projectName,
  initialAgents,
  onClose,
}: ProjectPromptConfigProps) {
  const [agents, setAgents] = useState<ProjectAgentPromptItem[]>(initialAgents || [])
  const [loading, setLoading] = useState(!initialAgents)
  const [editingType, setEditingType] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!initialAgents) {
      loadAgents()
    }
  }, [projectId])

  const loadAgents = async () => {
    setLoading(true)
    try {
      const data = await agentPromptsApi.getProject(projectId)
      setAgents(data.agents)
    } catch (error) {
      console.error('Failed to load project prompts:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleStartEdit = (agent: ProjectAgentPromptItem) => {
    setEditingType(agent.agent_type)
    setEditContent(agent.custom_content || '')
  }

  const handleSave = async (agentType: string) => {
    setSaving(true)
    try {
      await agentPromptsApi.setProjectCustom(projectId, agentType, {
        prompt_content: editContent,
      })
      setAgents((prev) =>
        prev.map((a) =>
          a.agent_type === agentType
            ? { ...a, use_custom: true, custom_content: editContent }
            : a
        )
      )
      setEditingType(null)
    } catch (error) {
      console.error('Failed to save:', error)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCustom = async (agentType: string) => {
    if (!confirm('确定要删除自定义配置，恢复使用全局默认吗？')) return

    try {
      await agentPromptsApi.deleteProjectCustom(projectId, agentType)
      setAgents((prev) =>
        prev.map((a) =>
          a.agent_type === agentType
            ? { ...a, use_custom: false, custom_content: undefined }
            : a
        )
      )
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  if (loading) {
    return <div className="p-4">加载中...</div>
  }

  return (
    <div className="border rounded-lg bg-white">
      <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
        <h3 className="font-semibold">{projectName} - 智能体配置</h3>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            关闭
          </Button>
        )}
      </div>

      <div className="p-4 space-y-2">
        {agents.map((agent) => (
          <div key={agent.agent_type} className="border rounded p-3">
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="font-medium">{agent.agent_name}</span>
                {agent.use_custom && (
                  <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                    使用自定义
                  </span>
                )}
              </div>

              {editingType === agent.agent_type ? null : agent.use_custom ? (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleStartEdit(agent)}
                  >
                    编辑
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600"
                    onClick={() => handleDeleteCustom(agent.agent_type)}
                  >
                    恢复全局
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleStartEdit(agent)}
                >
                  为此项目自定义
                </Button>
              )}
            </div>

            {editingType === agent.agent_type && (
              <div className="mt-3">
                <Textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="min-h-[150px] font-mono text-sm"
                  placeholder="输入自定义 Prompt..."
                />
                <div className="mt-2 flex items-center justify-between">
                  <div className="text-sm text-gray-500">
                    变量: {agent.variables.map((v) => `{${v}}`).join(' ')}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingType(null)}
                    >
                      取消
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleSave(agent.agent_type)}
                      disabled={saving}
                    >
                      {saving ? '保存中...' : '保存'}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}