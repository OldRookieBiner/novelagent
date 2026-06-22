/**
 * 人物设定模块 TypeScript 类型定义
 * 与后端 Pydantic schemas 对应
 */

// ==================== 角色类型常量 ====================

/** 角色定位类型 */
export type CharacterRole = '主角' | '核心反派' | '重要配角' | '配角'

/** 关系类型 */
export type RelationType = '信任' | '敌对' | '感情' | '合作' | '利用' | '陌生'

/** 关系方向 */
export type RelationDirection = '双向' | '单向A→B' | '单向B→A'

// ==================== Character Types ====================

/**
 * 人物设定
 */
export interface Character
{
    id: number
    project_id: number
    name: string
    role: string
    personality?: string
    catchphrase?: string
    habit_action?: string
    deep_fear?: string
    core_motivation?: string
    growth_arc?: string
    appearance?: string
    backstory?: string
    signature_item?: string
    knowledge_boundary?: string
    speech_style?: string
    speech_samples?: string
    created_at: string
    updated_at: string
}

/**
 * 人物设定创建请求
 */
export interface CharacterCreate
{
    name: string
    role: string
    personality?: string
    catchphrase?: string
    habit_action?: string
    deep_fear?: string
    core_motivation?: string
    growth_arc?: string
    appearance?: string
    backstory?: string
    signature_item?: string
    knowledge_boundary?: string
    speech_style?: string
    speech_samples?: string
}

/**
 * 人物设定更新请求
 */
export interface CharacterUpdate
{
    name?: string
    role?: string
    personality?: string
    catchphrase?: string
    habit_action?: string
    deep_fear?: string
    core_motivation?: string
    growth_arc?: string
    appearance?: string
    backstory?: string
    signature_item?: string
    knowledge_boundary?: string
    speech_style?: string
    speech_samples?: string
}

/**
 * 人物设定列表响应
 */
export interface CharacterListResponse
{
    characters: Character[]
    total: number
}

// ==================== Relation Types ====================

/**
 * 人物关系
 */
export interface Relation
{
    id: number
    project_id: number
    character_a_id: number
    character_b_id: number
    relation_type: string
    direction: string
    current_status?: string
    trust_level: number  // 0-100
    created_at: string
    updated_at: string
}

/**
 * 人物关系创建请求
 */
export interface RelationCreate
{
    character_a_id: number
    character_b_id: number
    relation_type: string
    direction?: string  // 默认 "双向"
    current_status?: string
    trust_level?: number  // 默认 50
}

/**
 * 人物关系更新请求
 */
export interface RelationUpdate
{
    character_a_id?: number
    character_b_id?: number
    relation_type?: string
    direction?: string
    current_status?: string
    trust_level?: number  // 0-100
}

/**
 * 人物简要信息（用于关系响应中的人物信息）
 */
export interface CharacterBrief
{
    id: number
    name: string
    role: string
}

/**
 * 人物关系（包含人物详情）
 */
export interface RelationWithCharacters extends Relation
{
    character_a?: CharacterBrief
    character_b?: CharacterBrief
}

/**
 * 人物关系列表响应
 */
export interface RelationListResponse
{
    relations: RelationWithCharacters[]
    total: number
}

// ==================== EvolutionPlan Types ====================

/**
 * 关系演变规划
 */
export interface EvolutionPlan
{
    id: number
    relation_id: number
    trigger_chapter: number
    event_description: string
    status_before?: string
    status_after: string
    trust_before?: number  // 0-100
    trust_after?: number   // 0-100
    is_triggered: boolean
    created_at: string
    updated_at: string
}

/**
 * 关系演变规划创建请求
 */
export interface EvolutionPlanCreate
{
    trigger_chapter: number
    event_description: string
    status_before?: string
    status_after: string
    trust_before?: number  // 0-100
    trust_after?: number   // 0-100
    is_triggered?: boolean  // 默认 false
}

/**
 * 关系演变规划更新请求
 */
export interface EvolutionPlanUpdate
{
    trigger_chapter?: number
    event_description?: string
    status_before?: string
    status_after?: string
    trust_before?: number  // 0-100
    trust_after?: number   // 0-100
    is_triggered?: boolean
}

/**
 * 关系演变规划列表响应
 */
export interface EvolutionPlanListResponse
{
    plans: EvolutionPlan[]
    total: number
}

// ==================== EvolutionRecord Types ====================

/**
 * 关系演变追溯记录
 */
export interface EvolutionRecord
{
    id: number
    relation_id: number
    chapter_number: number
    content: string
    status_change?: string
    trust_change?: number  // 正负值
    triggered_plan_id?: number
    created_at: string
}

/**
 * 关系演变追溯记录创建请求
 */
export interface EvolutionRecordCreate
{
    chapter_number: number
    content: string
    status_change?: string
    trust_change?: number
    triggered_plan_id?: number
}

/**
 * 关系演变追溯记录列表响应
 */
export interface EvolutionRecordListResponse
{
    records: EvolutionRecord[]
    total: number
}

// ==================== AI 生成请求 Types ====================

/**
 * AI 批量生成人物请求
 */
export interface CharacterGenerateRequest
{
    count?: number  // 默认 3，范围 1-20
    roles?: string[]  // 指定角色类型列表
    additional_context?: string
}

/**
 * AI 生成关系规划请求
 */
export interface RelationGenerateRequest
{
    character_ids?: number[]  // 为空则生成所有人物间的关系
    relation_types?: string[]  // 指定关系类型列表
    additional_context?: string
}

/**
 * AI 优化单个人物请求
 */
export interface CharacterOptimizeRequest
{
    fields?: string[]  // 为空则优化所有可空字段
    additional_context?: string
}