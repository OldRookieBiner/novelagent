// 知识库相关类型定义

export interface PlotBlock {
  id: number
  project_id: number
  title: string
  questions_to_answer: string[]
  questions_to_raise: string[]
  must_happen: string[]
  expected_mood: string | null
  chapter_start: number | null
  chapter_end: number | null
  completion_summary: string | null
}

export interface PlotBlockUpdate {
  title?: string
  questions_to_answer?: string[]
  questions_to_raise?: string[]
  must_happen?: string[]
  expected_mood?: string
  chapter_start?: number
  chapter_end?: number
  completion_summary?: string
}

export interface Subplot {
  id: number
  project_id: number
  name: string
  characters: string[]
  current_status: string
  raised_in_chapter: number | null
  planned_intersection_chapter: number | null
  expected_resolution_chapter: number | null
}

export interface SubplotCreate {
  name: string
  characters?: string[]
  current_status?: string
  raised_in_chapter?: number | null
  planned_intersection_chapter?: number | null
  expected_resolution_chapter?: number | null
}

export interface SubplotUpdate {
  name?: string
  characters?: string[]
  current_status?: string
  raised_in_chapter?: number | null
  planned_intersection_chapter?: number | null
  expected_resolution_chapter?: number | null
}

export interface Foreshadowing {
  id: number
  project_id: number
  content: string
  level: string
  appearance_count: number
  status: string
  planted_chapter: number | null
  expected_resolve_chapter: number | null
  resolved_chapter: number | null
  related_characters: string[]
}

export interface ForeshadowingUpdate {
  content?: string
  level?: string
  status?: string
  planted_chapter?: number | null
  expected_resolve_chapter?: number | null
  resolved_chapter?: number | null
  related_characters?: string[]
}

export interface TimelineEntry {
  id: number
  project_id: number
  chapter_number: number
  summary: string | null
  causal_chain: string | null
  rhythm_score: number
  tension_score: number
  emotion_score: number
  emotion_tag: string | null
}

export interface StyleSnapshot {
  id: number
  project_id: number
  chapter_number: number
  paragraph_count: number
  avg_paragraph_length: number
  dialogue_ratio: number
  avg_sentence_length: number
  ai_marker_density?: number
  sentence_variety?: number
}

export interface WorldSetting {
  id: number
  project_id: number
  core_concept: string | null
  tiered_settings: Record<string, string[]>
  key_locations: string[]
}

export interface StyleConstraints {
  id: number
  project_id: number
  taboo_words: string[]
  forbidden_patterns: string[]
  style_anchor: string | null
  abstract_rules: string[]
}
