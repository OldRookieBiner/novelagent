import { create } from 'zustand'
import type { AgentPrompt, ProjectAgentPromptItem } from '@/types'

interface AgentPromptState {
  // Global prompts
  globalPrompts: AgentPrompt[]
  loadingGlobal: boolean

  // Project prompts
  projectPrompts: Map<number, ProjectAgentPromptItem[]>
  loadingProject: number | null

  // Editing state
  editingAgent: string | null
  editingProjectId: number | null

  // Actions
  setGlobalPrompts: (prompts: AgentPrompt[]) => void
  updateGlobalPrompt: (agentType: string, content: string) => void
  setProjectPrompts: (projectId: number, agents: ProjectAgentPromptItem[]) => void
  updateProjectCustom: (projectId: number, agentType: string, content: string) => void
  removeProjectCustom: (projectId: number, agentType: string) => void
  setEditingAgent: (agentType: string | null, projectId: number | null) => void
  setLoadingGlobal: (loading: boolean) => void
  setLoadingProject: (projectId: number | null) => void
}

export const useAgentPromptStore = create<AgentPromptState>((set) => ({
  globalPrompts: [],
  loadingGlobal: false,
  projectPrompts: new Map(),
  loadingProject: null,
  editingAgent: null,
  editingProjectId: null,

  setGlobalPrompts: (prompts) => set({ globalPrompts: prompts }),

  updateGlobalPrompt: (agentType, content) =>
    set((state) => ({
      globalPrompts: state.globalPrompts.map((p) =>
        p.agent_type === agentType
          ? { ...p, prompt_content: content, is_default: false }
          : p
      ),
    })),

  setProjectPrompts: (projectId, agents) =>
    set((state) => {
      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, agents)
      return { projectPrompts: newMap }
    }),

  updateProjectCustom: (projectId, agentType, content) =>
    set((state) => {
      const agents = state.projectPrompts.get(projectId)
      if (!agents) return state

      const newAgents = agents.map((a) =>
        a.agent_type === agentType
          ? { ...a, use_custom: true, custom_content: content }
          : a
      )

      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, newAgents)
      return { projectPrompts: newMap }
    }),

  removeProjectCustom: (projectId, agentType) =>
    set((state) => {
      const agents = state.projectPrompts.get(projectId)
      if (!agents) return state

      const newAgents = agents.map((a) =>
        a.agent_type === agentType
          ? { ...a, use_custom: false, custom_content: undefined }
          : a
      )

      const newMap = new Map(state.projectPrompts)
      newMap.set(projectId, newAgents)
      return { projectPrompts: newMap }
    }),

  setEditingAgent: (agentType, projectId) =>
    set({ editingAgent: agentType, editingProjectId: projectId }),

  setLoadingGlobal: (loading) => set({ loadingGlobal: loading }),

  setLoadingProject: (projectId) => set({ loadingProject: projectId }),
}))