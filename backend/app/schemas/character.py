"""Character and relation schemas

人物设定模块的 Pydantic schemas，包含：
- Character: 人物设定相关 schemas
- Relation: 人物关系相关 schemas
- EvolutionPlan: 关系演变规划相关 schemas
- EvolutionRecord: 关系演变追溯记录相关 schemas
- AI 生成请求相关 schemas
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


# ==================== 枚举定义 ====================


class CharacterRole(str, Enum):
    """角色定位枚举"""

    PROTAGONIST = "主角"
    ANTAGONIST = "核心反派"
    SUPPORTING = "重要配角"
    MINOR = "配角"


class RelationType(str, Enum):
    """关系类型枚举"""

    TRUST = "信任"
    HOSTILE = "敌对"
    ROMANCE = "感情"
    COOPERATION = "合作"
    EXPLOITATION = "利用"
    STRANGER = "陌生"


class RelationDirection(str, Enum):
    """关系方向枚举"""

    BIDIRECTIONAL = "双向"
    A_TO_B = "单向A->B"
    B_TO_A = "单向B->A"


# ==================== Character Schemas ====================


class CharacterBase(BaseModel):
    """人物设定基础 Schema"""

    name: str = Field(..., max_length=100, description="人物姓名")
    role: CharacterRole = Field(
        ..., description="角色定位：主角/核心反派/重要配角/配角"
    )
    personality: Optional[str] = Field(None, description="性格特征")
    catchphrase: Optional[str] = Field(None, max_length=200, description="口头禅")
    habit_action: Optional[str] = Field(None, max_length=200, description="习惯动作")
    deep_fear: Optional[str] = Field(None, description="深层恐惧/弱点")
    core_motivation: Optional[str] = Field(None, description="核心动机")
    growth_arc: Optional[str] = Field(None, description="成长弧线")
    appearance: Optional[str] = Field(None, description="外貌描写")
    backstory: Optional[str] = Field(None, description="背景故事")
    signature_item: Optional[str] = Field(None, description="标志性物品/装备")


class CharacterCreate(CharacterBase):
    """人物设定创建 Schema"""

    pass


class CharacterUpdate(BaseModel):
    """人物设定更新 Schema"""

    name: Optional[str] = Field(None, max_length=100, description="人物姓名")
    role: Optional[CharacterRole] = Field(None, description="角色定位")
    personality: Optional[str] = Field(None, description="性格特征")
    catchphrase: Optional[str] = Field(None, max_length=200, description="口头禅")
    habit_action: Optional[str] = Field(None, max_length=200, description="习惯动作")
    deep_fear: Optional[str] = Field(None, description="深层恐惧/弱点")
    core_motivation: Optional[str] = Field(None, description="核心动机")
    growth_arc: Optional[str] = Field(None, description="成长弧线")
    appearance: Optional[str] = Field(None, description="外貌描写")
    backstory: Optional[str] = Field(None, description="背景故事")
    signature_item: Optional[str] = Field(None, description="标志性物品/装备")


class CharacterResponse(CharacterBase):
    """人物设定响应 Schema"""

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharacterListResponse(BaseModel):
    """人物设定列表响应 Schema"""

    characters: List[CharacterResponse]
    total: int


# ==================== Relation Schemas ====================


class RelationBase(BaseModel):
    """人物关系基础 Schema"""

    character_a_id: int = Field(..., description="人物A ID")
    character_b_id: int = Field(..., description="人物B ID")
    relation_type: RelationType = Field(
        ..., description="关系类型：信任/敌对/感情/合作/利用/陌生"
    )
    direction: RelationDirection = Field(
        RelationDirection.BIDIRECTIONAL, description="方向：双向/单向A->B/单向B->A"
    )
    current_status: Optional[str] = Field(None, description="当前状态描述")
    trust_level: int = Field(50, ge=0, le=100, description="信任度 0-100")


class RelationCreate(RelationBase):
    """人物关系创建 Schema"""

    pass


class RelationUpdate(BaseModel):
    """人物关系更新 Schema"""

    character_a_id: Optional[int] = Field(None, description="人物A ID")
    character_b_id: Optional[int] = Field(None, description="人物B ID")
    relation_type: Optional[RelationType] = Field(None, description="关系类型")
    direction: Optional[RelationDirection] = Field(None, description="方向")
    current_status: Optional[str] = Field(None, description="当前状态描述")
    trust_level: Optional[int] = Field(None, ge=0, le=100, description="信任度 0-100")


class RelationResponse(RelationBase):
    """人物关系响应 Schema"""

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharacterBrief(BaseModel):
    """人物简要信息 Schema（用于关系响应中的人物信息）"""

    id: int
    name: str
    role: str

    class Config:
        from_attributes = True


class RelationWithCharactersResponse(RelationResponse):
    """人物关系响应 Schema（包含人物详情）"""

    character_a: Optional[CharacterBrief] = None
    character_b: Optional[CharacterBrief] = None


class RelationListResponse(BaseModel):
    """人物关系列表响应 Schema"""

    relations: List[RelationWithCharactersResponse]
    total: int


# ==================== EvolutionPlan Schemas ====================


class EvolutionPlanBase(BaseModel):
    """关系演变规划基础 Schema"""

    trigger_chapter: int = Field(..., description="触发章节（大约）")
    event_description: str = Field(..., description="事件描述")
    status_before: Optional[str] = Field(None, description="变化前状态")
    status_after: str = Field(..., description="变化后状态")
    trust_before: Optional[int] = Field(None, ge=0, le=100, description="变化前信任度")
    trust_after: Optional[int] = Field(None, ge=0, le=100, description="变化后信任度")
    is_triggered: bool = Field(False, description="是否已触发")


class EvolutionPlanCreate(EvolutionPlanBase):
    """关系演变规划创建 Schema"""

    pass


class EvolutionPlanUpdate(BaseModel):
    """关系演变规划更新 Schema"""

    trigger_chapter: Optional[int] = Field(None, description="触发章节")
    event_description: Optional[str] = Field(None, description="事件描述")
    status_before: Optional[str] = Field(None, description="变化前状态")
    status_after: Optional[str] = Field(None, description="变化后状态")
    trust_before: Optional[int] = Field(None, ge=0, le=100, description="变化前信任度")
    trust_after: Optional[int] = Field(None, ge=0, le=100, description="变化后信任度")
    is_triggered: Optional[bool] = Field(None, description="是否已触发")


class EvolutionPlanResponse(EvolutionPlanBase):
    """关系演变规划响应 Schema"""

    id: int
    relation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvolutionPlanListResponse(BaseModel):
    """关系演变规划列表响应 Schema"""

    plans: List[EvolutionPlanResponse]
    total: int


# ==================== EvolutionRecord Schemas ====================


class EvolutionRecordBase(BaseModel):
    """关系演变追溯记录基础 Schema"""

    chapter_number: int = Field(..., description="章节号")
    content: str = Field(..., description="发生了什么")
    status_change: Optional[str] = Field(None, description="状态变化")
    trust_change: Optional[int] = Field(None, description="信任度变化（正负值）")
    triggered_plan_id: Optional[int] = Field(None, description="触发的规划节点 ID")


class EvolutionRecordCreate(EvolutionRecordBase):
    """关系演变追溯记录创建 Schema"""

    pass


class EvolutionRecordResponse(EvolutionRecordBase):
    """关系演变追溯记录响应 Schema"""

    id: int
    relation_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EvolutionRecordListResponse(BaseModel):
    """关系演变追溯记录列表响应 Schema"""

    records: List[EvolutionRecordResponse]
    total: int


# ==================== AI 生成请求 Schemas ====================


class CharacterGenerateRequest(BaseModel):
    """AI 批量生成人物请求 Schema"""

    count: int = Field(3, ge=1, le=20, description="生成数量")
    roles: Optional[List[str]] = Field(
        None, description="指定角色类型列表，如 ['主角', '反派']"
    )
    additional_context: Optional[str] = Field(None, description="额外上下文信息")


class RelationGenerateRequest(BaseModel):
    """AI 生成关系规划请求 Schema"""

    character_ids: Optional[List[int]] = Field(
        None, description="指定人物 ID 列表，为空则生成所有人物间的关系"
    )
    relation_types: Optional[List[str]] = Field(None, description="指定关系类型列表")
    additional_context: Optional[str] = Field(None, description="额外上下文信息")


class CharacterOptimizeRequest(BaseModel):
    """AI 优化单个人物请求 Schema"""

    fields: Optional[List[str]] = Field(
        None, description="需要优化的字段列表，为空则优化所有可空字段"
    )
    additional_context: Optional[str] = Field(
        None, description="额外上下文信息，如特定的优化方向"
    )
