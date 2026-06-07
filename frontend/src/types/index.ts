/**
 * TypeScript type definitions for NovelAgent frontend
 */

// ==================== User Types ====================

export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  user: User;
  session_token: string;
}

// ==================== Project Types ====================

/**
 * 创作阶段（Agent 模式，与后端 Phase enum 对齐）
 */
export type Phase = 'incubation' | 'structure' | 'writing' | 'revision'

/**
 * 工作流状态（后端 WorkflowState 模型，Agent 模式精简版）
 */
export interface WorkflowStateData {
  id: number
  project_id: number
  stage: Phase
  current_chapter: number
  created_at: string
  updated_at: string
}

export interface Project {
  id: number
  user_id: number
  name: string
  target_words: number
  total_words: number
  created_at: string
  updated_at: string
  workflow_state: WorkflowStateData | null
}

export interface ProjectDetail extends Project {
  chapter_count: number
  completed_chapters: number
  progress_percentage: number
}

export interface ProjectListResponse {
  projects: ProjectDetail[]
  total: number
}

export interface ProjectInitializeRequest {
  concept: string
  target_words?: number
}

export interface ProjectCreate {
  name: string
  target_words?: number
}

export interface ProjectUpdate {
  name?: string
  target_words?: number
  stage?: string
}

// ==================== Outline Types ====================

export interface CollectedInfo {
  novelType?: string;
  novelLength?: 'short' | 'medium' | 'long';  // 小说长度分类
  targetWords?: number;
  coreTheme?: string;
  worldSetting?: string;
  customWorldSetting?: string;
  protagonist?: string;
  customProtagonist?: string;
  stylePreference?: string;
  targetReader?: string;
  wordsPerChapter?: string;
  customWordsPerChapter?: number;
  narrative?: string;
  goldFinger?: string;
  customGoldFinger?: string;
  era?: string;
  genre?: string;
  customGenre?: string;
  maleLead?: string;
  customMaleLead?: string;
  femaleLead?: string;
  customFemaleLead?: string;
  contextStrategy?: 'fulltext' | 'hybrid' | 'summary'
}

// v0.6.1: 情节节点增强结构
export interface PlotPoint {
  order: number;
  event: string;
  conflict?: string;
  hook?: string;
}

// v0.6.1: 人物设定结构（用于大纲，简化版）
export interface OutlineCharacter {
  name: string;
  role: string;
  personality?: string;
  motivation?: string;
  arc?: string;
}

// 世界观设定结构（与后端 WorldSettingResponse 对齐）
export interface WorldSetting {
  id?: number;
  project_id?: number;
  core_concept?: string;
  tiered_settings?: {
    red?: string[];
    yellow?: string[];
    green?: string[];
  };
  key_locations?: string[];
  // 旧格式字段（Outline.world_setting），兼容显示
  era?: string;
  core_rules?: string;
  power_system?: string;
}

export interface Outline {
  id: number;
  project_id: number;
  title?: string;
  summary?: string;
  plot_points?: PlotPoint[];  // v0.6.1: 改为字典数组
  characters?: OutlineCharacter[];   // v0.6.1: 人物设定（简化版）
  world_setting?: WorldSetting;  // v0.6.1: 世界观
  emotional_curve?: string;   // v0.6.1: 情感曲线
  collected_info?: CollectedInfo;
  inspiration_template?: string;
  chapter_count_suggested: number;
  chapter_count_confirmed: boolean;
  confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface OutlineUpdate {
  title?: string;
  summary?: string;
  plot_points?: PlotPoint[];  // v0.6.1: 改为字典数组
  characters?: OutlineCharacter[];  // v0.6.1: 人物设定（简化版）
  world_setting?: WorldSetting;
  emotional_curve?: string;
  collected_info?: CollectedInfo;
  inspiration_template?: string;
}

export interface ChapterCountRequest {
  chapter_count: number;
}

// ==================== Volume/Arc Types ====================

export interface Volume
{
  id: number
  project_id: number
  volume_number: number
  title: string | null
  summary: string | null
  arcs?: Arc[]
}

export interface Arc
{
  id: number
  volume_id: number
  arc_number: number
  title: string | null
  summary: string | null
  outline?: string
  outline_confirmed?: boolean
  chapter_count: number
}

export interface ArcUpdate
{
  title?: string
  summary?: string
  outline?: string
  outline_confirmed?: boolean
  chapter_count?: number
}

// ==================== Chapter Types ====================

export interface ChapterOutline {
  id: number;
  project_id: number;
  chapter_number: number;
  arc_id: number | null;
  title?: string;
  scene?: string;
  characters?: string;
  plot?: string;
  conflict?: string;
  turning_point?: string;
  hook?: string;
  transition?: string;
  ending?: string;
  target_words: number;
  confirmed: boolean;
  created_at: string;
  has_content: boolean;
}

export interface ChapterOutlineUpdate {
  title?: string;
  scene?: string;
  characters?: string;
  plot?: string;
  conflict?: string;
  turning_point?: string;
  hook?: string;
  transition?: string;
  ending?: string;
  target_words?: number;
}

export interface Chapter {
  id: number;
  chapter_outline_id: number;
  content?: string;
  word_count: number;
  review_passed: boolean;
  review_feedback?: string;
  summary?: string | null;
  review_result?: {
    passed: boolean;
    scores: Record<string, number>;
    issues: ReviewIssue[];
    suggestions: string;
    raw_response?: string;
  } | null;
  rewrite_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChapterContentUpdate {
  content: string;
}

export interface ReviewRequest {
  strictness?: "loose" | "standard" | "strict";
}

// 审核问题条目（兼容后端两种格式：JSON 返回结构化对象，旧格式返回字符串）
export interface ReviewIssue {
  type?: string;
  location?: string;
  description: string;
  paragraph_start?: string;
  suggestion?: string;
}

export interface ReviewResponse {
  passed: boolean;
  feedback: string;
  issues: ReviewIssue[];
  scores?: Record<string, number>;
}

/** 从后端 review_result JSON 映射为前端 ReviewResponse */
export function mapReviewResult(result: Chapter['review_result']): ReviewResponse | null {
  if (!result) return null
  return {
    passed: result.passed ?? false,
    feedback: result.suggestions || '',
    issues: (result.issues || []).map(issue =>
      typeof issue === 'string' ? { description: issue } : issue
    ),
    scores: result.scores || {},
  }
}

// ==================== Settings Types ====================

export interface UserSettings {
  model_provider: string;
  model_name: string;
  has_api_key: boolean;
  review_enabled: boolean;
  review_strictness: string;
  // Agent 模型选择持久化
  agent_model_config_id?: number | null;
  agent_model_name?: string | null;
}

export interface SettingsUpdate {
  model_provider?: string;
  model_name?: string;
  api_key?: string;
  clear_api_key?: boolean;
  review_enabled?: boolean;
  review_strictness?: string;
  // Agent 模型选择持久化
  agent_model_config_id?: number | null;
  agent_model_name?: string | null;
}

// ==================== Chat Types ====================

export interface ChatMessage {
  message: string;
}

export interface ChatResponse {
  response: string;
  collected_info?: CollectedInfo;
  is_info_sufficient: boolean;
}

// ==================== API Error Types ====================

export interface ApiError {
  detail: string;
}

// ==================== Model Config Types ====================

/**
 * 模型项
 */
export interface ModelItem {
  id: string
  name: string
  is_enabled: boolean
  health_status?: string
  health_latency?: number
  temperature: number
  reasoning_effort?: string | null
  context_window?: number | null
}

/**
 * 模型配置
 * - single: 单一模型配置
 * - coding_plan: 编码套餐（包含多个模型）
 */
export interface ModelConfig {
  id: number
  name: string
  provider: string
  provider_type: 'single' | 'coding_plan'
  base_url: string
  model_name?: string
  models?: ModelItem[]
  has_api_key: boolean
  is_enabled: boolean
  is_default: boolean
  health_status?: string
  health_latency?: number
  last_health_check?: string
  context_window?: number
  created_at: string
  updated_at: string
}

export interface ModelConfigListResponse {
  models: ModelConfig[]
}

/**
 * 提供商信息
 */
export interface ProviderInfo {
  id: string
  name: string
  provider_type: 'single' | 'coding_plan'
  base_url: string
  models_api?: string
}

export interface ProvidersListResponse {
  providers: ProviderInfo[]
}

/**
 * 获取模型列表响应
 */
export interface FetchModelsResponse {
  models: { id: string; name: string }[]
  error?: string
  allow_manual: boolean
}

export interface ModelConfigCreate {
  name: string
  provider: string
  provider_type: string
  base_url: string
  model_name?: string
  models?: ModelItem[]
  api_key?: string
}

export interface ModelConfigUpdate {
  name?: string
  provider?: string
  base_url?: string
  model_name?: string
  models?: ModelItem[]
  is_enabled?: boolean
  api_key?: string
  clear_api_key?: boolean
}

/** 单个模型健康检查结果 */
export interface ModelHealthResult {
  model_id: string
  model_name: string
  status: 'healthy' | 'unhealthy'
  latency?: number
  error?: string
}

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy'
  latency?: number
  error?: string
  model_results?: ModelHealthResult[]
}

// SSE 数据类型（定义在 sseParser.ts，此处 re-export）
export type { SSEData } from '@/lib/sseParser'  

// ==================== Character Setting Module Types ====================

export * from './character'