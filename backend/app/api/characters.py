"""Character API routes

人物设定模块的 API 路由，包含：
- Character CRUD 端点
- Relation CRUD 端点
- EvolutionPlan CRUD 端点
- EvolutionRecord 列表端点
- AI 生成端点（占位符，返回 501）
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.character import Character, Relation, EvolutionPlan, EvolutionRecord
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
    RelationCreate,
    RelationUpdate,
    RelationResponse,
    RelationWithCharactersResponse,
    RelationListResponse,
    CharacterBrief,
    EvolutionPlanCreate,
    EvolutionPlanUpdate,
    EvolutionPlanResponse,
    EvolutionPlanListResponse,
    EvolutionRecordResponse,
    EvolutionRecordListResponse,
    CharacterGenerateRequest,
    RelationGenerateRequest,
    CharacterOptimizeRequest,
)
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user

router = APIRouter()


# ==================== Character CRUD ====================

@router.get("/{project_id}/characters", response_model=CharacterListResponse)
async def list_characters(
    project_id: int,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目下的人物列表

    Args:
        project_id: 项目 ID
        role: 可选的角色过滤（主角/核心反派/重要配角/配角）
        db: 数据库会话
        current_user: 当前用户

    Returns:
        人物列表和总数
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 构建查询
    query = db.query(Character).filter(Character.project_id == project_id)

    # 可选过滤
    if role:
        query = query.filter(Character.role == role)

    # 按角色重要性排序（主角 > 核心反派 > 重要配角 > 配角）
    role_order = {
        "主角": 1,
        "核心反派": 2,
        "重要配角": 3,
        "配角": 4
    }
    characters = query.all()
    characters.sort(key=lambda c: role_order.get(c.role, 5))

    return CharacterListResponse(
        characters=[CharacterResponse.model_validate(c) for c in characters],
        total=len(characters)
    )


@router.post("/{project_id}/characters", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: int,
    request: CharacterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建人物

    Args:
        project_id: 项目 ID
        request: 人物创建请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        创建的人物信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 创建人物
    character = Character(
        project_id=project_id,
        name=request.name,
        role=request.role,
        personality=request.personality,
        catchphrase=request.catchphrase,
        habit_action=request.habit_action,
        deep_fear=request.deep_fear,
        core_motivation=request.core_motivation,
        growth_arc=request.growth_arc,
        appearance=request.appearance,
        backstory=request.backstory,
        signature_item=request.signature_item
    )

    db.add(character)
    db.commit()
    db.refresh(character)

    return CharacterResponse.model_validate(character)


@router.get("/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def get_character(
    project_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个人物详情

    Args:
        project_id: 项目 ID
        character_id: 人物 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        人物详情
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询人物
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )

    return CharacterResponse.model_validate(character)


@router.put("/{project_id}/characters/{character_id}", response_model=CharacterResponse)
async def update_character(
    project_id: int,
    character_id: int,
    request: CharacterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新人物

    Args:
        project_id: 项目 ID
        character_id: 人物 ID
        request: 人物更新请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        更新后的人物信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询人物
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(character, key, value)

    db.commit()
    db.refresh(character)

    return CharacterResponse.model_validate(character)


@router.delete("/{project_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    project_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除人物

    Args:
        project_id: 项目 ID
        character_id: 人物 ID
        db: 数据库会话
        current_user: 当前用户
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询人物
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )

    # 删除人物（级联删除相关关系）
    db.delete(character)
    db.commit()


# ==================== Relation CRUD ====================

@router.get("/{project_id}/relations", response_model=RelationListResponse)
async def list_relations(
    project_id: int,
    relation_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目下的人物关系列表

    Args:
        project_id: 项目 ID
        relation_type: 可选的关系类型过滤
        db: 数据库会话
        current_user: 当前用户

    Returns:
        关系列表和总数
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 构建查询
    query = db.query(Relation).filter(Relation.project_id == project_id)

    # 可选过滤
    if relation_type:
        query = query.filter(Relation.relation_type == relation_type)

    relations = query.all()

    # 构建带人物信息的响应
    relations_with_characters = []
    for relation in relations:
        rel_dict = RelationResponse.model_validate(relation).model_dump()
        rel_dict["character_a"] = CharacterBrief.model_validate(relation.character_a) if relation.character_a else None
        rel_dict["character_b"] = CharacterBrief.model_validate(relation.character_b) if relation.character_b else None
        relations_with_characters.append(RelationWithCharactersResponse(**rel_dict))

    return RelationListResponse(
        relations=relations_with_characters,
        total=len(relations_with_characters)
    )


@router.post("/{project_id}/relations", response_model=RelationResponse, status_code=status.HTTP_201_CREATED)
async def create_relation(
    project_id: int,
    request: RelationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建人物关系

    Args:
        project_id: 项目 ID
        request: 关系创建请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        创建的关系信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 验证人物存在且属于该项目
    char_a = db.query(Character).filter(
        Character.id == request.character_a_id,
        Character.project_id == project_id
    ).first()
    char_b = db.query(Character).filter(
        Character.id == request.character_b_id,
        Character.project_id == project_id
    ).first()

    if not char_a or not char_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both characters not found in this project"
        )

    # 检查是否已存在相同的关系
    existing = db.query(Relation).filter(
        Relation.project_id == project_id,
        Relation.character_a_id == request.character_a_id,
        Relation.character_b_id == request.character_b_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relation between these characters already exists"
        )

    # 创建关系
    relation = Relation(
        project_id=project_id,
        character_a_id=request.character_a_id,
        character_b_id=request.character_b_id,
        relation_type=request.relation_type,
        direction=request.direction,
        current_status=request.current_status,
        trust_level=request.trust_level
    )

    db.add(relation)
    db.commit()
    db.refresh(relation)

    return RelationResponse.model_validate(relation)


@router.get("/{project_id}/relations/{relation_id}", response_model=RelationWithCharactersResponse)
async def get_relation(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个关系详情

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        关系详情（包含人物信息）
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询关系
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 构建带人物信息的响应
    rel_dict = RelationResponse.model_validate(relation).model_dump()
    rel_dict["character_a"] = CharacterBrief.model_validate(relation.character_a) if relation.character_a else None
    rel_dict["character_b"] = CharacterBrief.model_validate(relation.character_b) if relation.character_b else None

    return RelationWithCharactersResponse(**rel_dict)


@router.put("/{project_id}/relations/{relation_id}", response_model=RelationResponse)
async def update_relation(
    project_id: int,
    relation_id: int,
    request: RelationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新人物关系

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        request: 关系更新请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        更新后的关系信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询关系
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 如果要更新人物 ID，验证新人物存在
    if request.character_a_id is not None or request.character_b_id is not None:
        char_a_id = request.character_a_id or relation.character_a_id
        char_b_id = request.character_b_id or relation.character_b_id

        char_a = db.query(Character).filter(
            Character.id == char_a_id,
            Character.project_id == project_id
        ).first()
        char_b = db.query(Character).filter(
            Character.id == char_b_id,
            Character.project_id == project_id
        ).first()

        if not char_a or not char_b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both characters not found in this project"
            )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(relation, key, value)

    db.commit()
    db.refresh(relation)

    return RelationResponse.model_validate(relation)


@router.delete("/{project_id}/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relation(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除人物关系

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        db: 数据库会话
        current_user: 当前用户
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询关系
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 删除关系（级联删除演变规划和记录）
    db.delete(relation)
    db.commit()


# ==================== EvolutionPlan CRUD ====================

@router.get("/{project_id}/relations/{relation_id}/evolution-plans", response_model=EvolutionPlanListResponse)
async def list_evolution_plans(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取关系的演变规划列表

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        演变规划列表和总数
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 验证关系存在
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 查询演变规划，按触发章节排序
    plans = db.query(EvolutionPlan).filter(
        EvolutionPlan.relation_id == relation_id
    ).order_by(EvolutionPlan.trigger_chapter).all()

    return EvolutionPlanListResponse(
        plans=[EvolutionPlanResponse.model_validate(p) for p in plans],
        total=len(plans)
    )


@router.post("/{project_id}/relations/{relation_id}/evolution-plans", response_model=EvolutionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_evolution_plan(
    project_id: int,
    relation_id: int,
    request: EvolutionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建关系演变规划

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        request: 演变规划创建请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        创建的演变规划信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 验证关系存在
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 创建演变规划
    plan = EvolutionPlan(
        relation_id=relation_id,
        trigger_chapter=request.trigger_chapter,
        event_description=request.event_description,
        status_before=request.status_before,
        status_after=request.status_after,
        trust_before=request.trust_before,
        trust_after=request.trust_after,
        is_triggered=request.is_triggered
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return EvolutionPlanResponse.model_validate(plan)


@router.get("/{project_id}/relations/{relation_id}/evolution-plans/{plan_id}", response_model=EvolutionPlanResponse)
async def get_evolution_plan(
    project_id: int,
    relation_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个演变规划详情

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        plan_id: 演变规划 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        演变规划详情
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询演变规划
    plan = db.query(EvolutionPlan).join(Relation).filter(
        EvolutionPlan.id == plan_id,
        EvolutionPlan.relation_id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolution plan not found"
        )

    return EvolutionPlanResponse.model_validate(plan)


@router.put("/{project_id}/relations/{relation_id}/evolution-plans/{plan_id}", response_model=EvolutionPlanResponse)
async def update_evolution_plan(
    project_id: int,
    relation_id: int,
    plan_id: int,
    request: EvolutionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新关系演变规划

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        plan_id: 演变规划 ID
        request: 演变规划更新请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        更新后的演变规划信息
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询演变规划
    plan = db.query(EvolutionPlan).join(Relation).filter(
        EvolutionPlan.id == plan_id,
        EvolutionPlan.relation_id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolution plan not found"
        )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)

    db.commit()
    db.refresh(plan)

    return EvolutionPlanResponse.model_validate(plan)


@router.delete("/{project_id}/relations/{relation_id}/evolution-plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evolution_plan(
    project_id: int,
    relation_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除关系演变规划

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        plan_id: 演变规划 ID
        db: 数据库会话
        current_user: 当前用户
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 查询演变规划
    plan = db.query(EvolutionPlan).join(Relation).filter(
        EvolutionPlan.id == plan_id,
        EvolutionPlan.relation_id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolution plan not found"
        )

    db.delete(plan)
    db.commit()


# ==================== EvolutionRecord CRUD ====================

@router.get("/{project_id}/relations/{relation_id}/evolution-records", response_model=EvolutionRecordListResponse)
async def list_evolution_records(
    project_id: int,
    relation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取关系的演变记录列表

    Args:
        project_id: 项目 ID
        relation_id: 关系 ID
        db: 数据库会话
        current_user: 当前用户

    Returns:
        演变记录列表和总数
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 验证关系存在
    relation = db.query(Relation).filter(
        Relation.id == relation_id,
        Relation.project_id == project_id
    ).first()

    if not relation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relation not found"
        )

    # 查询演变记录，按章节排序
    records = db.query(EvolutionRecord).filter(
        EvolutionRecord.relation_id == relation_id
    ).order_by(EvolutionRecord.chapter_number).all()

    return EvolutionRecordListResponse(
        records=[EvolutionRecordResponse.model_validate(r) for r in records],
        total=len(records)
    )


# ==================== AI 生成端点（占位符）====================

@router.post("/{project_id}/characters/generate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def generate_characters(
    project_id: int,
    request: CharacterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 批量生成人物（暂未实现）

    Args:
        project_id: 项目 ID
        request: 生成请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        501 NOT IMPLEMENTED
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI character generation is not implemented yet"
    )


@router.post("/{project_id}/relations/generate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def generate_relations(
    project_id: int,
    request: RelationGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 生成关系规划（暂未实现）

    Args:
        project_id: 项目 ID
        request: 生成请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        501 NOT IMPLEMENTED
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI relation generation is not implemented yet"
    )


@router.post("/{project_id}/characters/{character_id}/optimize", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def optimize_character(
    project_id: int,
    character_id: int,
    request: CharacterOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 优化单个人物（暂未实现）

    Args:
        project_id: 项目 ID
        character_id: 人物 ID
        request: 优化请求
        db: 数据库会话
        current_user: 当前用户

    Returns:
        501 NOT IMPLEMENTED
    """
    # 验证项目权限
    get_project_for_user(project_id, current_user.id, db)

    # 验证人物存在
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.project_id == project_id
    ).first()

    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI character optimization is not implemented yet"
    )
