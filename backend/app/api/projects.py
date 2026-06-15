"""Projects API routes"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectDetailResponse,
    WorkflowStateResponse,
)
from app.utils.auth import get_current_user
from app.utils.workflow import get_or_create_workflow_state

# 模块日志
logger = logging.getLogger(__name__)

router = APIRouter()


def get_project_detail(project: Project, db: Session) -> ProjectDetailResponse:
    """构建项目详情，包含工作流状态和章节进度（优化查询）"""
    from sqlalchemy.orm import joinedload

    # 单次查询带关联加载，避免 N+1 问题
    chapter_outlines = (
        db.query(ChapterOutline)
        .options(joinedload(ChapterOutline.chapter))
        .filter(ChapterOutline.project_id == project.id)
        .order_by(ChapterOutline.chapter_number)
        .all()
    )

    chapter_count = len(chapter_outlines)
    completed_chapters = sum(
        1 for co in chapter_outlines if co.chapter and co.chapter.review_passed
    )

    progress_percentage = (
        (completed_chapters / chapter_count * 100) if chapter_count > 0 else 0
    )

    # 获取工作流状态
    workflow_state = get_or_create_workflow_state(db, project.id)

    return ProjectDetailResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(workflow_state),
        chapter_count=chapter_count,
        completed_chapters=completed_chapters,
        progress_percentage=round(progress_percentage, 1),
    )


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    limit: Optional[int] = None,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    列出当前用户的所有项目
    直接返回包含进度详情的项目列表，避免前端 N+1 请求
    支持可选分页参数 limit 和 offset
    """
    projects = db.query(Project).filter(Project.user_id == current_user.id).order_by(Project.updated_at.desc())
    total = projects.count()
    if limit is not None:
        projects = projects.offset(offset).limit(limit).all()
    else:
        projects = projects.all()
    # 直接返回 ProjectDetailResponse 而不是 ProjectResponse，避免前端额外请求
    project_details = [get_project_detail(p, db) for p in projects]
    return ProjectListResponse(projects=project_details, total=total)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新项目，同时创建关联的大纲和工作流状态"""
    try:
        project = Project(
            user_id=current_user.id,
            name=request.name,
            target_words=request.target_words,
        )
        db.add(project)
        db.flush()  # 获取 ID 但不提交

        # 创建空大纲
        outline = Outline(project_id=project.id)
        db.add(outline)

        # 创建工作流状态（使用 upsert 保证唯一性）
        workflow_state = get_or_create_workflow_state(db, project.id)

        db.commit()
        db.refresh(project)

        return ProjectResponse(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            target_words=project.target_words,
            total_words=project.total_words,
            created_at=project.created_at,
            updated_at=project.updated_at,
            workflow_state=WorkflowStateResponse.model_validate(workflow_state),
        )
    except Exception as e:
        db.rollback()
        # 记录详细错误日志，便于调试
        logger.error(f"创建项目失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建项目失败: {str(e)}",
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目详情"""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    return get_project_detail(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新项目"""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if request.name is not None:
        project.name = request.name
    if request.target_words is not None:
        project.target_words = request.target_words

    db.commit()
    db.refresh(project)

    # 获取工作流状态
    workflow_state = get_or_create_workflow_state(db, project.id)

    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(workflow_state),
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除项目（级联删除关联数据）"""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == current_user.id)
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    db.delete(project)
    db.commit()

    return {"success": True, "message": "Project deleted"}




# 项目初始化端点
@router.post("/initialize")
async def initialize_project(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """初始化项目：创建项目 + 生成基础知识库（SSE 流）

    根据用户输入的概念描述，自动生成故事种子、小说名、世界观、大纲、角色、风格约束。
    返回 SSE 事件流，前端可实时展示初始化进度。
    """
    from fastapi.responses import StreamingResponse

    concept = body.get("concept", "").strip() if body.get("concept") else ""
    target_words = body.get("target_words", 100000)
    model_config_id = body.get("model_config_id")
    model_id = body.get("model_id")

    if not concept:
        raise HTTPException(status_code=400, detail="概念描述不能为空")

    try:
        project = Project(
            user_id=current_user.id,
            name=concept[:50] if concept else "新建项目",
            target_words=target_words,
        )
        db.add(project)
        db.flush()

        outline = Outline(project_id=project.id)
        db.add(outline)

        workflow_state = get_or_create_workflow_state(db, project.id)

        db.commit()
        db.refresh(project)

        project_id = project.id
        user_id = current_user.id

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建项目失败: {str(e)}")

    from app.agents.initialization import stream_initialization

    async def event_generator():
        completed = False
        try:
            async for event in stream_initialization(
                concept=concept,
                target_words=target_words,
                project_id=project_id,
                user_id=user_id,
                model_config_id=model_config_id,
                model_id=model_id,
                request=request,
            ):
                yield event
                if '"status": "complete"' in event:
                    completed = True
            if not completed:
                pass
        except Exception as e:
            logger.error(f"初始化流程异常: {str(e)}")
            err_msg = str(e).replace('"', '\\"').replace("'", "\'")
            yield f'event: init:error\ndata: {{"error": "{err_msg}"}}\n\n'
            yield f'event: init:done\ndata: {{"project_id": {project_id}, "status": "partial"}}\n\n'
        finally:
            # 如果项目未完成（取消/超时/异常），删除项目及关联数据
            if not completed:
                try:
                    cleanup_db = SessionLocal()
                    try:
                        project = cleanup_db.query(Project).filter(Project.id == project_id).first()
                        if project:
                            cleanup_db.delete(project)
                            cleanup_db.commit()
                    finally:
                        cleanup_db.close()
                except Exception as cleanup_err:
                    logger.error(f"清理失败项目时出错: {cleanup_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
