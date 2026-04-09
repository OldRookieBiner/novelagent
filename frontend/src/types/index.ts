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

export interface Project {
  id: number;
  user_id: number;
  name: string;
  target_words: number;
  stage: string;
  total_words: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  chapter_count: number;
  completed_chapters: number;
  progress_percentage: number;
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
}

export interface ProjectCreate {
  name: string;
  target_words?: number;
}

export interface ProjectUpdate {
  name?: string;
  stage?: string;
  target_words?: number;
}

// ==================== Outline Types ====================

export interface CollectedInfo {
  genre?: string;
  theme?: string;
  main_characters?: string;
  world_setting?: string;
  style_preference?: string;
}

export interface Outline {
  id: number;
  project_id: number;
  title?: string;
  summary?: string;
  plot_points?: string[];
  collected_info?: CollectedInfo;
  chapter_count_suggested: number;
  chapter_count_confirmed: boolean;
  confirmed: boolean;
  created_at: string;
  updated_at: string;
}

export interface OutlineUpdate {
  title?: string;
  summary?: string;
  plot_points?: string[];
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