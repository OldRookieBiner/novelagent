"""知识库 API 路由

所有 KB 调用通过 Store 的 dict 返回值，不再接触 ORM 对象。
FastAPI response_model 自动将 dict 序列化为 JSON。
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.project import get_project_for_user
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.schemas.knowledge import (
    WorldSettingResponse,
    WorldSettingUpdate,
    StyleConstraintsResponse,
    StyleConstraintsUpdate,
    PlotBlockResponse,
    PlotBlockUpdate,
    SubplotResponse,
    SubplotCreate,
    SubplotUpdate,
    ForeshadowingResponse,
    ForeshadowingUpdate,
    TimelineEntryResponse,
    StyleSnapshotResponse,
)

router = APIRouter()


# ========== 常量定义 ==========

# 伏笔状态单向流转：active → pending_reclaim → reclaimed
FORESHADOWING_STATUS_TRANSITIONS = {
    "active": {"pending_reclaim"},
    "pending_reclaim": {"reclaimed"},
    "reclaimed": set(),  # 终态，不可流转
}
FORESHADOWING_VALID_STATUSES = {"active", "pending_reclaim", "reclaimed"}
FORESHADOWING_VALID_LEVELS = {"hint", "strengthened", "revealed"}
SUBPLOT_VALID_STATUSES = {"hint", "developing", "pending_intersection", "resolved"}


def _get_kb(project_id: int) -> KnowledgeBaseService:
    return KnowledgeBaseService(project_id)


def _check_busy(project) -> None:
    """检查项目 busy 状态，防止并发写入"""
    if project.is_busy:
        holder = project.busy_by or "未知"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"项目正在被{holder}使用，请稍后再试"
        )




# ========== 故事种子 ==========

class StorySeedUpdate(BaseModel):
    story_seed: str


@router.get("/projects/{project_id}/story-seed")
def get_story_seed(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目故事种子"""
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    story_seed = kb.get_story_seed()
    return {"story_seed": story_seed or ""}


@router.put("/projects/{project_id}/story-seed")
def update_story_seed(
    project_id: int,
    data: StorySeedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新项目故事种子"""
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    kb.update_story_seed(data.story_seed)
    return {"story_seed": data.story_seed}


# ========== 大纲 ==========

@router.get("/projects/{project_id}/outline-summary")
def get_outline_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取大纲摘要（知识库视图用）"""
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    outline = kb.outlines.get()
    if not outline:
        return {"outline": None}
    # 过滤空的世界观数据，避免前端显示全空 JSON
    ws = outline.get("world_setting")
    if isinstance(ws, dict):
        # 移除空字符串和空列表字段，如果全部为空则设为 None
        non_empty = {k: v for k, v in ws.items() if v not in ("", [], None)}
        ws = non_empty if non_empty else None

    return {
        "outline": {
            "title": outline.get("title"),
            "summary": outline.get("summary"),
            "plot_points": outline.get("plot_points"),
            "characters": outline.get("characters"),
            "world_setting": ws,
            "emotional_curve": outline.get("emotional_curve"),
            "chapter_count_suggested": outline.get("chapter_count_suggested"),
            "confirmed": outline.get("confirmed"),
        }
    }


# ========== 世界观 ==========

@router.get("/projects/{project_id}/world-setting", response_model=WorldSettingResponse)
def get_world_setting(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    setting = kb.world_setting.get()
    if not setting:
        raise HTTPException(status_code=404, detail="World setting not found")
    return setting


@router.put("/projects/{project_id}/world-setting", response_model=WorldSettingResponse)
def update_world_setting(
    project_id: int,
    data: WorldSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    setting = kb.world_setting.get()
    if not setting:
        raise HTTPException(status_code=404, detail="World setting not found")
    updated = kb.world_setting.update_by_id(setting["id"], data.model_dump(exclude_none=True))
    return updated


# ========== 风格约束 ==========

@router.get("/projects/{project_id}/style-constraints", response_model=StyleConstraintsResponse)
def get_style_constraints(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    constraints = kb.styles.get_constraints()
    if not constraints:
        raise HTTPException(status_code=404, detail="Style constraints not found")
    return constraints


@router.put("/projects/{project_id}/style-constraints", response_model=StyleConstraintsResponse)
def update_style_constraints(
    project_id: int,
    data: StyleConstraintsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    # 风格约束不存在则创建
    constraints = kb.styles.get_constraints()
    if constraints:
        updated = kb.styles.update_constraints_by_id(constraints["id"], data.model_dump(exclude_none=True))
    else:
        updated = kb.styles.create_constraints(data.model_dump(exclude_none=True))
    return updated


# ========== 情节块 ==========

@router.get("/projects/{project_id}/plot-blocks", response_model=list[PlotBlockResponse])
def get_plot_blocks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.plots.list_plot_blocks()


@router.post("/projects/{project_id}/plot-blocks/batch", status_code=201)
def create_plot_blocks_batch(
    project_id: int,
    items: list[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建情节块"""
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project_id)

    created = []
    for item in items:
        block = kb.plots.create_plot_block(item)
        created.append({
            "id": block["id"],
            "title": block.get("title"),
            "chapter_range": f"{block.get('chapter_start')}-{block.get('chapter_end')}",
        })

    return {"created": len(created), "plot_blocks": created}



@router.put("/projects/{project_id}/plot-blocks/{block_id}", response_model=PlotBlockResponse)
def update_plot_block(
    project_id: int,
    block_id: int,
    data: PlotBlockUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑情节块"""
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    try:
        return kb.plots.update_plot_block(block_id, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/projects/{project_id}/plot-blocks/{block_id}", status_code=204)
def delete_plot_block(
    project_id: int,
    block_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除情节块

    关联的 PlotQuestion.plot_block_id 会被 SET NULL（数据库 ondelete）
    """
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    try:
        kb.plots.delete_plot_block(block_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== 支线 ==========

@router.get("/projects/{project_id}/subplots", response_model=list[SubplotResponse])
def get_subplots(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目支线列表"""
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.plots.list_subplots()

@router.post("/projects/{project_id}/subplots", response_model=SubplotResponse, status_code=201)
def create_subplot(
    project_id: int,
    data: SubplotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增支线"""
    if data.current_status and data.current_status not in SUBPLOT_VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid current_status: {data.current_status}. Must be one of {SUBPLOT_VALID_STATUSES}"
        )
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    return kb.plots.create_subplot(data.model_dump())


@router.put("/projects/{project_id}/subplots/{subplot_id}", response_model=SubplotResponse)
def update_subplot(
    project_id: int,
    subplot_id: int,
    data: SubplotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑支线"""
    if data.current_status and data.current_status not in SUBPLOT_VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid current_status: {data.current_status}. Must be one of {SUBPLOT_VALID_STATUSES}"
        )
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    try:
        return kb.plots.update_subplot(subplot_id, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/projects/{project_id}/subplots/{subplot_id}", status_code=204)
def delete_subplot(
    project_id: int,
    subplot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除支线"""
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)
    try:
        kb.plots.delete_subplot(subplot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ========== 伏笔 ==========

@router.get("/projects/{project_id}/foreshadowings", response_model=list[ForeshadowingResponse])
def get_foreshadowings(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.foreshadowings.list_foreshadowings(status=status)


@router.post("/projects/{project_id}/foreshadowings/batch", status_code=201)
def create_foreshadowings_batch(
    project_id: int,
    items: list[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建伏笔

    在 KnowledgeBaseService 中逐个创建，部分失败不影响已创建条目。
    """
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project_id)

    created = []
    for item in items:
        f = kb.foreshadowings.create(item)
        created.append({"id": f["id"], "content": f.get("content", "")[:60], "level": f.get("level")})

    return {"created": len(created), "foreshadowings": created}

@router.put("/projects/{project_id}/foreshadowings/{foreshadowing_id}", response_model=ForeshadowingResponse)
def update_foreshadowing(
    project_id: int,
    foreshadowing_id: int,
    data: ForeshadowingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑伏笔（内容+状态流转）

    状态流转仅允许 active→pending_reclaim→reclaimed 单向转换
    level 合法值：hint / strengthened / revealed
    """
    project = get_project_for_user(project_id, current_user.id, db)
    _check_busy(project)
    kb = _get_kb(project.id)

    # 获取当前伏笔，用于状态流转校验
    current_foreshadowing = kb.foreshadowings.get(foreshadowing_id)
    if not current_foreshadowing:
        raise HTTPException(status_code=404, detail=f"Foreshadowing {foreshadowing_id} not found")

    update_data = data.model_dump(exclude_none=True)

    # 状态流转校验
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status not in FORESHADOWING_VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status: {new_status}. Must be one of {FORESHADOWING_VALID_STATUSES}"
            )
        current_status = current_foreshadowing.get("status", "")
        allowed = FORESHADOWING_STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot transition from '{current_status}' to '{new_status}'. "
                       f"Allowed transitions: {allowed or 'none (terminal state)'}"
            )

    # level 合法值校验
    if "level" in update_data and update_data["level"] not in FORESHADOWING_VALID_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid level: {update_data['level']}. Must be one of {FORESHADOWING_VALID_LEVELS}"
        )

    try:
        return kb.foreshadowings.update(foreshadowing_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== 时间线 ==========

@router.get("/projects/{project_id}/timeline", response_model=list[TimelineEntryResponse])
def get_timeline(
    project_id: int,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    if chapter_start is not None and chapter_end is not None:
        return kb.timelines.list_timeline(chapter_range=(chapter_start, chapter_end))
    return kb.timelines.list_timeline()


# ========== 风格统计 ==========

@router.get("/projects/{project_id}/style-snapshots", response_model=list[StyleSnapshotResponse])
def get_style_snapshots(
    project_id: int,
    last_n: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_for_user(project_id, current_user.id, db)
    kb = _get_kb(project.id)
    return kb.styles.list_snapshots(last_n=last_n)
