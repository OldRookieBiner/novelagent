"""知识库 Pydantic schemas"""

from pydantic import BaseModel
from typing import Optional


class WorldSettingResponse(BaseModel):
    id: int
    project_id: int
    core_concept: Optional[str] = None
    tiered_settings: dict = {}
    key_locations: list = []

    class Config:
        from_attributes = True


class WorldSettingUpdate(BaseModel):
    core_concept: Optional[str] = None
    tiered_settings: Optional[dict] = None
    key_locations: Optional[list] = None


class StyleConstraintsResponse(BaseModel):
    id: int
    project_id: int
    taboo_words: list = []
    forbidden_patterns: list = []
    style_anchor: Optional[str] = None
    abstract_rules: list = []

    class Config:
        from_attributes = True


class StyleConstraintsUpdate(BaseModel):
    taboo_words: Optional[list] = None
    forbidden_patterns: Optional[list] = None
    style_anchor: Optional[str] = None
    abstract_rules: Optional[list] = None


class PlotBlockResponse(BaseModel):
    id: int
    project_id: int
    title: str
    questions_to_answer: list = []
    questions_to_raise: list = []
    must_happen: list = []
    expected_mood: Optional[str] = None
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None
    completion_summary: Optional[str] = None

    class Config:
        from_attributes = True


class ForeshadowingResponse(BaseModel):
    id: int
    project_id: int
    content: str
    level: str = "hint"
    appearance_count: int = 1
    status: str = "active"
    planted_chapter: Optional[int] = None
    expected_resolve_chapter: Optional[int] = None
    resolved_chapter: Optional[int] = None
    related_characters: list = []

    class Config:
        from_attributes = True


class TimelineEntryResponse(BaseModel):
    id: int
    project_id: int
    chapter_number: int
    summary: Optional[str] = None
    causal_chain: Optional[str] = None
    rhythm_score: int = 3
    tension_score: int = 3
    emotion_score: int = 3
    emotion_tag: Optional[str] = None

    class Config:
        from_attributes = True


class StyleSnapshotResponse(BaseModel):
    id: int
    project_id: int
    chapter_number: int
    paragraph_count: int = 0
    avg_paragraph_length: float = 0.0
    dialogue_ratio: float = 0.0
    avg_sentence_length: float = 0.0

    class Config:
        from_attributes = True
