"""Pydantic schemas"""

from app.schemas.user import UserBase, UserResponse, LoginRequest, LoginResponse
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectDetailResponse
)
from app.schemas.outline import (
    OutlineBase, OutlineCreate, OutlineUpdate, OutlineResponse,
    CollectedInfo, ChapterCountRequest, ChatMessage, ChatResponse
)
from app.schemas.chapter import (
    ChapterOutlineBase, ChapterOutlineUpdate, ChapterOutlineResponse,
    ChapterContentUpdate, ChapterResponse, ReviewRequest, ReviewResponse
)
from app.schemas.settings import SettingsBase, SettingsUpdate, SettingsResponse
from app.schemas.system_prompt import (
    AGENT_TYPES, AgentTypeKey, AgentTypeMeta,
    SystemPromptResponse, SystemPromptListResponse, SystemPromptUpdate
)
from app.schemas.character import (
    CharacterBase, CharacterCreate, CharacterUpdate, CharacterResponse, CharacterListResponse,
    RelationBase, RelationCreate, RelationUpdate, RelationResponse,
    RelationWithCharactersResponse, RelationListResponse, CharacterBrief,
    EvolutionPlanBase, EvolutionPlanCreate, EvolutionPlanUpdate, EvolutionPlanResponse, EvolutionPlanListResponse,
    EvolutionRecordBase, EvolutionRecordCreate, EvolutionRecordResponse, EvolutionRecordListResponse,
    CharacterGenerateRequest, RelationGenerateRequest, CharacterOptimizeRequest
)

__all__ = [
    "UserBase", "UserResponse", "LoginRequest", "LoginResponse",
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectListResponse", "ProjectDetailResponse",
    "OutlineBase", "OutlineCreate", "OutlineUpdate", "OutlineResponse",
    "CollectedInfo", "ChapterCountRequest", "ChatMessage", "ChatResponse",
    "ChapterOutlineBase", "ChapterOutlineUpdate", "ChapterOutlineResponse",
    "ChapterContentUpdate", "ChapterResponse", "ReviewRequest", "ReviewResponse",
    "SettingsBase", "SettingsUpdate", "SettingsResponse",
    "AGENT_TYPES", "AgentTypeKey", "AgentTypeMeta",
    "SystemPromptResponse", "SystemPromptListResponse", "SystemPromptUpdate",
    # Character schemas
    "CharacterBase", "CharacterCreate", "CharacterUpdate", "CharacterResponse", "CharacterListResponse",
    "RelationBase", "RelationCreate", "RelationUpdate", "RelationResponse",
    "RelationWithCharactersResponse", "RelationListResponse", "CharacterBrief",
    "EvolutionPlanBase", "EvolutionPlanCreate", "EvolutionPlanUpdate", "EvolutionPlanResponse", "EvolutionPlanListResponse",
    "EvolutionRecordBase", "EvolutionRecordCreate", "EvolutionRecordResponse", "EvolutionRecordListResponse",
    "CharacterGenerateRequest", "RelationGenerateRequest", "CharacterOptimizeRequest",
]