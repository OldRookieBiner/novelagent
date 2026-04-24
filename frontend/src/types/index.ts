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
 * 工作流状态（后端 WorkflowState 模型）
 */
export interface WorkflowStateData {
  id: number
  project_id: number
  thread_id: string
  stage: WorkflowStage
  workflow_mode: WorkflowMode
  max_rewrite_count: number
  current_chapter: number
  waiting_for_confirmation: boolean
  confirmation_type: ConfirmationType | null
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
  projects: Project[]
  total: number
}

export interface ProjectCreate {
  name: string
  target_words?: number
}

export interface ProjectUpdate {
  name?: string
  target_words?: number
}

// ==================== Outline Types ====================

export interface CollectedInfo {
  novelType?: string;
  targetWords?: number;
  coreTheme?: string;
  worldSetting?: string;
  customWorldSetting?: string;
  protagonist?: string;
  customProtagonist?: string;
  stylePreference?: string;
  // 新增字段
  targetReader?: string;          // 'male' | 'female'
  wordsPerChapter?: string;       // 每章字数
  customWordsPerChapter?: number;
  narrative?: string;             // 'first' | 'third'
  goldFinger?: string;            // 金手指类型
  customGoldFinger?: string;
}

// v0.6.1: 情节节点增强结构
export interface PlotPoint {
  order: number;
  event: string;
  conflict?: string;
  hook?: string;
}

// v0.6.1: 人物设定结构
export interface Character {
  name: string;
  role: string;
  personality?: string;
  motivation?: string;
  arc?: string;
}

// v0.6.1: 世界观设定结构
export interface WorldSetting {
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
  characters?: Character[];   // v0.6.1: 人物设定
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
  characters?: Character[];
  world_setting?: WorldSetting;
  emotional_curve?: string;
  collected_info?: CollectedInfo;
  inspiration_template?: string;
}

export interface ChapterCountRequest {
  chapter_count: number;
}

// ==================== Chapter Types ====================

export interface ChapterOutline {
  id: number;
  project_id: number;
  chapter_number: number;
  title?: string;
  scene?: string;
  characters?: string;
  plot?: string;
  conflict?: string;
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
  created_at: string;
  updated_at: string;
}

export interface ChapterContentUpdate {
  content: string;
}

export interface ReviewRequest {
  strictness?: "loose" | "standard" | "strict";
}

export interface ReviewResponse {
  passed: boolean;
  feedback: string;
  issues: string[];
}

// ==================== Settings Types ====================

export interface UserSettings {
  model_provider: string;
  model_name: string;
  has_api_key: boolean;
  review_enabled: boolean;
  review_strictness: string;
}

export interface SettingsUpdate {
  model_provider?: string;
  model_name?: string;
  api_key?: string;
  clear_api_key?: boolean;
  review_enabled?: boolean;
  review_strictness?: string;
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

// ==================== Agent Prompt Types ====================

export interface AgentPrompt {
  agent_type: string;
  agent_name: string;
  description: string;
  prompt_content: string;
  variables: string[];
  is_default: boolean;
  updated_at?: string;
}

export interface AgentPromptListResponse {
  prompts: AgentPrompt[];
}

export interface AgentPromptUpdate {
  prompt_content: string;
}

export interface ProjectAgentPromptItem {
  agent_type: string;
  agent_name: string;
  description: string;
  use_custom: boolean;
  custom_content?: string;
  variables: string[];
}

export interface ProjectAgentPromptsResponse {
  project_id: number;
  project_name: string;
  agents: ProjectAgentPromptItem[];
}

export interface EffectivePromptResponse {
  source: string;
  prompt_content: string;
}

// ==================== Model Config Types ====================

export interface ModelConfig {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  has_api_key: boolean;
  is_enabled: boolean;
  is_default: boolean;
  health_status: 'healthy' | 'unhealthy' | 'unknown' | null;
  health_latency: number | null;
  last_health_check: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelConfigListResponse {
  models: ModelConfig[];
}

export interface ModelConfigCreate {
  name: string;
  provider?: string;
  base_url: string;
  model_name: string;
  api_key?: string;
}

export interface ModelConfigUpdate {
  name?: string;
  base_url?: string;
  model_name?: string;
  api_key?: string;
  is_enabled?: boolean;
  clear_api_key?: boolean;
}

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy';
  latency?: number;
  error?: string;
}

// ==================== Workflow Types ====================

/**
 * 工作流模式
 * - step_by_step: 步步为营模式，每个阶段需手动确认
 * - hybrid: 混合模式，大纲和章节大纲需确认，写作自动进行
 * - auto: 全自动模式，无需确认
 */
export type WorkflowMode = 'step_by_step' | 'hybrid' | 'auto'

/**
 * 工作流阶段
 */
export type WorkflowStage =
  | 'inspiration'
  | 'outline'
  | 'chapter_outlines'
  | 'writing'
  | 'review'
  | 'complete'

/**
 * 确认类型
 */
export type ConfirmationType = 'outline' | 'chapter_outlines' | 'review_failed'

/**
 * 工作流状态
 */
export interface WorkflowState {
  stage: WorkflowStage
  currentChapter: number
  totalChapters: number
  writtenChaptersCount: number
  waitingForConfirmation: boolean
  confirmationType: ConfirmationType | null
  hasCheckpoint: boolean
  updatedAt: string | null
}

/**
 * 工作流 API 响应
 */
export interface WorkflowStateResponse {
  project_id: number
  stage: WorkflowStage
  has_checkpoint: boolean
  current_chapter: number
  total_chapters: number
  written_chapters_count: number
  waiting_for_confirmation: boolean
  confirmation_type: ConfirmationType | null
  updated_at: string | null
}

/**
 * SSE 事件类型
 */
export interface WorkflowSSEEvent {
  type: 'node_start' | 'node_done' | 'chunk' | 'checkpoint' | 'waiting' | 'done' | 'error'
  data: unknown
}

/**
 * 已写章节
 */
export interface WrittenChapter {
  chapter_number: number
  content: string
  word_count: number
}