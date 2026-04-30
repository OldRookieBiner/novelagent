/**
 * 人物设定模块 API 客户端
 * 包含 Character, Relation, EvolutionPlan, EvolutionRecord 的 CRUD 操作
 */

import { request } from './api'
import type {
  Character,
  CharacterCreate,
  CharacterUpdate,
  CharacterListResponse,
  Relation,
  RelationCreate,
  RelationUpdate,
  RelationWithCharacters,
  RelationListResponse,
  EvolutionPlan,
  EvolutionPlanCreate,
  EvolutionPlanUpdate,
  EvolutionPlanListResponse,
  EvolutionRecordListResponse,
} from '@/types/character'

// ==================== Character API ====================

export const characterApi = {
  /**
   * 获取项目下的人物列表
   * @param projectId - 项目 ID
   * @param role - 可选的角色过滤（主角/核心反派/重要配角/配角）
   */
  async list(projectId: number, role?: string, params?: { limit?: number; offset?: number }): Promise<CharacterListResponse>
  {
    const searchParams = new URLSearchParams()
    if (role) searchParams.set('role', encodeURIComponent(role))
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return request<CharacterListResponse>(`/api/projects/${projectId}/characters${query ? '?' + query : ''}`)
  },

  /**
   * 获取单个人物详情
   * @param projectId - 项目 ID
   * @param characterId - 人物 ID
   */
  async get(projectId: number, characterId: number): Promise<Character>
  {
    return request<Character>(`/api/projects/${projectId}/characters/${characterId}`)
  },

  /**
   * 创建人物
   * @param projectId - 项目 ID
   * @param data - 人物创建请求
   */
  async create(projectId: number, data: CharacterCreate): Promise<Character>
  {
    return request<Character>(`/api/projects/${projectId}/characters`, {
      method: 'POST',
      body: data,
    })
  },

  /**
   * 更新人物
   * @param projectId - 项目 ID
   * @param characterId - 人物 ID
   * @param data - 人物更新请求
   */
  async update(projectId: number, characterId: number, data: CharacterUpdate): Promise<Character>
  {
    return request<Character>(`/api/projects/${projectId}/characters/${characterId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 删除人物
   * @param projectId - 项目 ID
   * @param characterId - 人物 ID
   */
  async delete(projectId: number, characterId: number): Promise<void>
  {
    return request(`/api/projects/${projectId}/characters/${characterId}`, {
      method: 'DELETE',
    })
  },
}

// ==================== Relation API ====================

export const relationApi = {
  /**
   * 获取项目下的人物关系列表
   * @param projectId - 项目 ID
   * @param relationType - 可选的关系类型过滤
   */
  async list(projectId: number, relationType?: string): Promise<RelationListResponse>
  {
    const params = relationType ? `?relation_type=${encodeURIComponent(relationType)}` : ''
    return request<RelationListResponse>(`/api/projects/${projectId}/relations${params}`)
  },

  /**
   * 获取单个关系详情
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   */
  async get(projectId: number, relationId: number): Promise<RelationWithCharacters>
  {
    return request<RelationWithCharacters>(`/api/projects/${projectId}/relations/${relationId}`)
  },

  /**
   * 创建人物关系
   * @param projectId - 项目 ID
   * @param data - 关系创建请求
   */
  async create(projectId: number, data: RelationCreate): Promise<Relation>
  {
    return request<Relation>(`/api/projects/${projectId}/relations`, {
      method: 'POST',
      body: data,
    })
  },

  /**
   * 更新人物关系
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   * @param data - 关系更新请求
   */
  async update(projectId: number, relationId: number, data: RelationUpdate): Promise<Relation>
  {
    return request<Relation>(`/api/projects/${projectId}/relations/${relationId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 删除人物关系
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   */
  async delete(projectId: number, relationId: number): Promise<void>
  {
    return request(`/api/projects/${projectId}/relations/${relationId}`, {
      method: 'DELETE',
    })
  },
}

// ==================== EvolutionPlan API ====================

export const evolutionPlanApi = {
  /**
   * 获取关系的演变规划列表
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   */
  async list(projectId: number, relationId: number): Promise<EvolutionPlanListResponse>
  {
    return request<EvolutionPlanListResponse>(
      `/api/projects/${projectId}/relations/${relationId}/evolution-plans`
    )
  },

  /**
   * 获取单个演变规划详情
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   * @param planId - 演变规划 ID
   */
  async get(projectId: number, relationId: number, planId: number): Promise<EvolutionPlan>
  {
    return request<EvolutionPlan>(
      `/api/projects/${projectId}/relations/${relationId}/evolution-plans/${planId}`
    )
  },

  /**
   * 创建关系演变规划
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   * @param data - 演变规划创建请求
   */
  async create(
    projectId: number,
    relationId: number,
    data: EvolutionPlanCreate
  ): Promise<EvolutionPlan>
  {
    return request<EvolutionPlan>(
      `/api/projects/${projectId}/relations/${relationId}/evolution-plans`,
      {
        method: 'POST',
        body: data,
      }
    )
  },

  /**
   * 更新关系演变规划
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   * @param planId - 演变规划 ID
   * @param data - 演变规划更新请求
   */
  async update(
    projectId: number,
    relationId: number,
    planId: number,
    data: EvolutionPlanUpdate
  ): Promise<EvolutionPlan>
  {
    return request<EvolutionPlan>(
      `/api/projects/${projectId}/relations/${relationId}/evolution-plans/${planId}`,
      {
        method: 'PUT',
        body: data,
      }
    )
  },

  /**
   * 删除关系演变规划
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   * @param planId - 演变规划 ID
   */
  async delete(projectId: number, relationId: number, planId: number): Promise<void>
  {
    return request(
      `/api/projects/${projectId}/relations/${relationId}/evolution-plans/${planId}`,
      {
        method: 'DELETE',
      }
    )
  },
}

// ==================== EvolutionRecord API ====================

export const evolutionRecordApi = {
  /**
   * 获取关系的演变记录列表
   * @param projectId - 项目 ID
   * @param relationId - 关系 ID
   */
  async list(projectId: number, relationId: number): Promise<EvolutionRecordListResponse>
  {
    return request<EvolutionRecordListResponse>(
      `/api/projects/${projectId}/relations/${relationId}/evolution-records`
    )
  },
}
