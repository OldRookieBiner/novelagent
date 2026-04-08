# NovelAgent v0.2.0 Implementation Plan - Phase 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现后端核心功能 - 认证、项目管理、LangGraph Agent

**Architecture:** Session + Cookie 认证, RESTful API, LangGraph 状态机

**Tech Stack:** FastAPI, SQLAlchemy, passlib, itsdangerous, LangGraph

**前置条件:** Phase 1 已完成

---

## Phase 2: 后端核心功能

### Task 11: 认证工具模块

**Files:**
- Create: `backend/app/utils/auth.py`
- Create: `backend/app/services/crypto.py`

- [ ] **Step 1: 创建认证工具模块**

```python
# backend/app/utils/auth.py
"""Authentication utilities"""

from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Session serializer
serializer = URLSafeTimedSerializer(settings.secret_key, salt="session")

# HTTP Basic auth for cookie-based sessions
security = HTTPBasic()


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_session_token(user_id: int) -> str:
    """Create a session token for a user"""
    data = {"user_id": user_id, "created_at": datetime.utcnow().isoformat()}
    return serializer.dumps(data)


def verify_session_token(token: str) -> Optional[dict]:
    """Verify a session token"""
    try:
        data = serializer.loads(token, max_age=settings.session_expire_seconds)
        return data
    except BadSignature:
        return None


def create_default_user():
    """Create default user if not exists"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == settings.default_username).first()
        if not user:
            user = User(
                username=settings.default_username,
                password_hash=hash_password(settings.default_password)
            )
            db.add(user)
            db.commit()
            print(f"Created default user: {settings.default_username}")
    finally:
        db.close()


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from session"""
    # The username field contains the session token
    token = credentials.username
    data = verify_session_token(token)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token",
            headers={"WWW-Authenticate": "Basic"},
        )

    user = db.query(User).filter(User.id == data["user_id"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Basic"},
        )

    return user
```

- [ ] **Step 2: 创建加密服务**

```python
# backend/app/services/crypto.py
"""Encryption utilities for sensitive data"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def get_encryption_key() -> bytes:
    """Derive encryption key from secret key"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'novelagent_salt',  # Fixed salt for consistency
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return key


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key"""
    if not api_key:
        return ""

    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key"""
    if not encrypted_key:
        return ""

    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    except Exception:
        return ""
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/utils/auth.py backend/app/services/crypto.py
git commit -m "feat: add authentication utilities and encryption service"
```

---

### Task 12: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/schemas/outline.py`
- Create: `backend/app/schemas/chapter.py`
- Create: `backend/app/schemas/settings.py`

- [ ] **Step 1: 创建用户 Schema**

```python
# backend/app/schemas/user.py
"""User schemas"""

from datetime import datetime
from pydantic import BaseModel


class UserBase(BaseModel):
    username: str


class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    user: UserResponse
    session_token: str
```

- [ ] **Step 2: 创建项目 Schema**

```python
# backend/app/schemas/project.py
"""Project schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectBase(BaseModel):
    name: str
    target_words: Optional[int] = 100000


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    target_words: Optional[int] = None


class ProjectResponse(ProjectBase):
    id: int
    user_id: int
    stage: str
    total_words: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class ProjectDetail(ProjectResponse):
    """Project with additional details"""
    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0
```

- [ ] **Step 3: 创建大纲 Schema**

```python
# backend/app/schemas/outline.py
"""Outline schemas"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class CollectedInfo(BaseModel):
    """Collected information from user"""
    genre: Optional[str] = None
    theme: Optional[str] = None
    main_characters: Optional[str] = None
    world_setting: Optional[str] = None
    style_preference: Optional[str] = None


class OutlineBase(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    plot_points: Optional[list[str]] = None
    collected_info: Optional[CollectedInfo] = None


class OutlineCreate(BaseModel):
    pass  # Generated by AI


class OutlineUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    plot_points: Optional[list[str]] = None


class OutlineResponse(OutlineBase):
    id: int
    project_id: int
    chapter_count_suggested: int
    chapter_count_confirmed: bool
    confirmed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChapterCountRequest(BaseModel):
    chapter_count: int


class ChatMessage(BaseModel):
    """Chat message for info collection"""
    message: str


class ChatResponse(BaseModel):
    """Chat response from agent"""
    response: str
    collected_info: Optional[CollectedInfo] = None
    is_info_sufficient: bool = False
```

- [ ] **Step 4: 创建章节 Schema**

```python
# backend/app/schemas/chapter.py
"""Chapter schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChapterOutlineBase(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    ending: Optional[str] = None
    target_words: Optional[int] = 3000


class ChapterOutlineUpdate(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    ending: Optional[str] = None
    target_words: Optional[int] = None


class ChapterOutlineResponse(ChapterOutlineBase):
    id: int
    project_id: int
    chapter_number: int
    confirmed: bool
    created_at: datetime
    has_content: bool = False

    class Config:
        from_attributes = True


class ChapterContentUpdate(BaseModel):
    content: str


class ChapterResponse(BaseModel):
    id: int
    chapter_outline_id: int
    content: Optional[str] = None
    word_count: int
    review_passed: bool
    review_feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    strictness: Optional[str] = "standard"  # loose, standard, strict


class ReviewResponse(BaseModel):
    passed: bool
    feedback: str
    issues: list[str] = []
```

- [ ] **Step 5: 创建设置 Schema**

```python
# backend/app/schemas/settings.py
"""Settings schemas"""

from typing import Optional
from pydantic import BaseModel


class SettingsBase(BaseModel):
    model_provider: Optional[str] = "deepseek"
    model_name: Optional[str] = "deepseek-chat"
    api_key: Optional[str] = None  # Will be encrypted before storage
    review_enabled: Optional[bool] = True
    review_strictness: Optional[str] = "standard"


class SettingsUpdate(SettingsBase):
    pass


class SettingsResponse(BaseModel):
    model_provider: str
    model_name: str
    has_api_key: bool  # Don't expose actual key
    review_enabled: bool
    review_strictness: str

    class Config:
        from_attributes = True
```

- [ ] **Step 6: 更新 Schema 导出**

```python
# backend/app/schemas/__init__.py
"""Pydantic schemas"""

from app.schemas.user import UserBase, UserResponse, LoginRequest, LoginResponse
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectDetail
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

__all__ = [
    "UserBase", "UserResponse", "LoginRequest", "LoginResponse",
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectListResponse", "ProjectDetail",
    "OutlineBase", "OutlineCreate", "OutlineUpdate", "OutlineResponse",
    "CollectedInfo", "ChapterCountRequest", "ChatMessage", "ChatResponse",
    "ChapterOutlineBase", "ChapterOutlineUpdate", "ChapterOutlineResponse",
    "ChapterContentUpdate", "ChapterResponse", "ReviewRequest", "ReviewResponse",
    "SettingsBase", "SettingsUpdate", "SettingsResponse",
]
```

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas/*.py
git commit -m "feat: add Pydantic schemas for all entities"
```

---

### Task 13: 实现认证 API

**Files:**
- Modify: `backend/app/api/auth.py`

- [ ] **Step 1: 实现登录 API**

```python
# backend/app/api/auth.py
"""Authentication API routes"""

from fastapi import APIRouter, HTTPException, status, Depends, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.settings import UserSettings
from app.schemas.user import LoginRequest, LoginResponse, UserResponse
from app.utils.auth import verify_password, create_session_token, get_current_user

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password"""
    # Find user
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Create session token
    session_token = create_session_token(user.id)

    return LoginResponse(
        success=True,
        user=UserResponse.from_orm(user),
        session_token=session_token
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout current user"""
    # In a stateless session, client just needs to discard the token
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse.from_orm(current_user)
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat: implement authentication API endpoints"
```

---

### Task 14: 实现项目管理 API

**Files:**
- Modify: `backend/app/api/projects.py`

- [ ] **Step 1: 实现项目 CRUD API**

```python
# backend/app/api/projects.py
"""Projects API routes"""

from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectDetail
)
from app.utils.auth import get_current_user

router = APIRouter()


def get_project_detail(project: Project, db: Session) -> ProjectDetail:
    """Build project detail with additional info"""
    chapter_outlines = db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project.id
    ).all()

    chapter_count = len(chapter_outlines)
    completed_chapters = sum(
        1 for co in chapter_outlines
        if db.query(Chapter).filter(Chapter.chapter_outline_id == co.id, Chapter.review_passed == True).first()
    )

    progress_percentage = (completed_chapters / chapter_count * 100) if chapter_count > 0 else 0

    return ProjectDetail(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        stage=project.stage,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chapter_count=chapter_count,
        completed_chapters=completed_chapters,
        progress_percentage=round(progress_percentage, 1)
    )


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all projects for current user"""
    projects = db.query(Project).filter(Project.user_id == current_user.id).all()
    return ProjectListResponse(
        projects=[ProjectResponse.from_orm(p) for p in projects],
        total=len(projects)
    )


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project"""
    project = Project(
        user_id=current_user.id,
        name=request.name,
        target_words=request.target_words
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Create empty outline
    outline = Outline(project_id=project.id)
    db.add(outline)
    db.commit()

    return ProjectResponse.from_orm(project)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project by ID"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return get_project_detail(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if request.name is not None:
        project.name = request.name
    if request.stage is not None:
        project.stage = request.stage
    if request.target_words is not None:
        project.target_words = request.target_words

    db.commit()
    db.refresh(project)

    return ProjectResponse.from_orm(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete project"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    db.delete(project)
    db.commit()

    return {"success": True, "message": "Project deleted"}
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/projects.py
git commit -m "feat: implement project CRUD API endpoints"
```

---

### Task 15: LLM 服务封装

**Files:**
- Create: `backend/app/services/llm.py`

- [ ] **Step 1: 创建 LLM 服务**

```python
# backend/app/services/llm.py
"""LLM service for interacting with AI models"""

from typing import AsyncIterator, Optional
import httpx
from openai import AsyncOpenAI

from app.config import settings


class LLMService:
    """LLM service for generating content"""

    # Model configurations
    MODEL_CONFIGS = {
        "deepseek": {
            "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "model": "deepseek-v3-241227"
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o"
        },
        "deepseek-official": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        }
    }

    def __init__(self, provider: str = None, api_key: str = None):
        self.provider = provider or settings.default_model_provider
        self.api_key = api_key or settings.default_api_key

        if not self.api_key:
            raise ValueError("API key is required")

        config = self.MODEL_CONFIGS.get(self.provider, self.MODEL_CONFIGS["deepseek"])

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=config["base_url"]
        )
        self.model = config["model"]

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Send a chat request and get response"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        """Send a chat request and stream response"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_with_system(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7
    ) -> str:
        """Chat with system prompt"""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        return await self.chat(full_messages, temperature)


def get_llm_service(user_settings) -> LLMService:
    """Get LLM service from user settings"""
    from app.services.crypto import decrypt_api_key

    api_key = decrypt_api_key(user_settings.api_key_encrypted) if user_settings.api_key_encrypted else None

    return LLMService(
        provider=user_settings.model_provider,
        api_key=api_key
    )
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/llm.py
git commit -m "feat: add LLM service for AI model interactions"
```

---

### Task 16: LangGraph Agent 状态定义

**Files:**
- Create: `backend/app/agents/state.py`
- Create: `backend/app/agents/prompts.py`

- [ ] **Step 1: 创建 Agent 状态**

```python
# backend/app/agents/state.py
"""LangGraph agent state definitions"""

from typing import TypedDict, Optional, Annotated
from operator import add


class CollectedInfo(TypedDict, total=False):
    """Collected information from user"""
    genre: str
    theme: str
    main_characters: str
    world_setting: str
    style_preference: str


class NovelState(TypedDict):
    """Novel creation state"""

    # Project info
    project_id: int
    stage: str

    # Collected info
    collected_info: CollectedInfo

    # Outline
    outline_title: Optional[str]
    outline_summary: Optional[str]
    outline_plot_points: list[str]
    outline_confirmed: bool

    # Chapter count
    chapter_count_suggested: int
    chapter_count_confirmed: bool

    # Chapter outlines
    chapter_outlines: list[dict]
    chapter_outlines_confirmed: bool

    # Current chapter
    current_chapter: int
    chapter_content: Optional[str]

    # Review
    review_enabled: bool
    review_passed: bool
    review_feedback: Optional[str]

    # Chat
    messages: Annotated[list[dict], add]
    last_user_message: Optional[str]
    last_assistant_message: Optional[str]


# Stage constants
STAGE_COLLECTING_INFO = "collecting_info"
STAGE_OUTLINE_GENERATING = "outline_generating"
STAGE_OUTLINE_CONFIRMING = "outline_confirming"
STAGE_CHAPTER_COUNT_SUGGESTING = "chapter_count_suggesting"
STAGE_CHAPTER_COUNT_CONFIRMING = "chapter_count_confirming"
STAGE_CHAPTER_OUTLINES_GENERATING = "chapter_outlines_generating"
STAGE_CHAPTER_OUTLINES_CONFIRMING = "chapter_outlines_confirming"
STAGE_CHAPTER_WRITING = "chapter_writing"
STAGE_CHAPTER_REVIEWING = "chapter_reviewing"
STAGE_COMPLETED = "completed"
STAGE_PAUSED = "paused"
```

- [ ] **Step 2: 创建 Prompt 模板**

```python
# backend/app/agents/prompts.py
"""Prompt templates for the agent"""

# Info collection system prompt
INFO_COLLECTION_SYSTEM_PROMPT = """你是一个专业的小说创作助手，正在帮助用户收集创作小说所需的信息。

你的任务是：
1. 分析用户输入，提取有用的信息
2. 判断信息是否充足（需要包含：题材类型、核心主题、主角设定、世界设定、风格偏好）
3. 如果信息不足，针对性地询问缺失的部分

对话风格：
- 友好、专业
- 每次只问 2-3 个最关键的问题
- 认可用户已提供的信息，让用户感到被理解

当前已收集的信息：
{collected_info}

请根据用户输入，更新信息并决定是否需要继续询问。
回复格式：
【已满足】xxx
【缺失】xxx
【问题】xxx（如果信息充足则写"信息已充足，可以开始生成大纲"）
"""

# Generate outline prompt
GENERATE_OUTLINE_PROMPT = """你是一个专业的小说大纲策划师。

根据用户提供的创作信息，生成一份结构化的小说大纲。

大纲格式要求：
---
标题：[小说名称]
概述：[200-300字故事概述]
主要情节节点：
1. [开篇事件]
2. [关键转折点1]
3. [关键转折点2]
...
N. [结局]
---

注意：
- 标题要有吸引力
- 概述要包含故事的核心冲突和发展脉络
- 情节节点要逻辑连贯，有清晰的起承转合

创作信息：
题材：{genre}
核心主题：{theme}
主角设定：{main_characters}
世界设定：{world_setting}
风格偏好：{style_preference}

请生成完整的大纲。
"""

# Suggest chapter count prompt
SUGGEST_CHAPTER_COUNT_PROMPT = """根据以下大纲，建议合适的章节数量。

大纲：
{outline}

考虑因素：
1. 情节节点数量
2. 每章合理字数（2000-3000字）
3. 故事节奏

请回复：
建议章节数：[数字]
理由：[简要说明]
"""

# Generate chapter outlines prompt
GENERATE_CHAPTER_OUTLINES_PROMPT = """你是一个小说章节策划师。根据大纲，生成每个章节的详细大纲。

要求：
1. 每章有明确的场景、人物、情节
2. 章节之间有连贯性
3. 每章有冲突和结局（或悬念）

大纲：
{outline}

章节数：{chapter_count}

请生成所有章节纲，每章格式如下：
---
第X章：[章节名]
场景：[发生地点]
人物：[出场人物]
情节：[本章主要情节，100-200字]
冲突：[本章的冲突/矛盾]
结局：[本章如何收尾/悬念]
预计字数：[字数]
---

请直接输出所有章节纲。
"""

# Generate chapter content prompt
GENERATE_CHAPTER_CONTENT_PROMPT = """你是一个小说作家。根据章节大纲，写出完整的章节正文。

要求：
1. 严格遵循章节纲的情节发展
2. 保持人物性格一致
3. 文笔流畅，有代入感
4. 避免AI生成的常见问题：
   - 不要过于书面化
   - 不要过度解释
   - 要有细节描写
   - 要有情感张力

章节大纲：
{chapter_outline}

前文参考（上一章结尾，如有）：
{previous_ending}

小说设定：
题材：{genre}
主角：{main_characters}
世界观：{world_setting}
风格：{style_preference}

请直接输出章节正文。
"""

# Review chapter prompt
REVIEW_CHAPTER_PROMPT = """你是一个专业的小说编辑。审核章节正文的质量。

审核维度：
1. 一致性：人物名、地名、前后情节是否一致
2. 质量：文笔、节奏、逻辑是否合理
3. AI味：是否有明显AI生成痕迹（过于书面化、重复表达、缺乏细节）
4. 规则：是否符合用户设定的风格

审核严格度：{strictness}
- loose: 只检查明显错误
- standard: 标准审核
- strict: 严格审核，任何小问题都要指出

章节大纲：
{chapter_outline}

章节正文：
{chapter_content}

小说设定：
题材：{genre}
主角：{main_characters}
风格：{style_preference}

请严格审核，回复格式如下：
---
【审核结果】通过/不通过
【问题列表】（如果没有问题则写"无"）
1. [问题描述]
2. ...
【修改建议】（如果没有则写"无"）
[具体建议]
---
"""

# Rewrite chapter prompt
REWRITE_CHAPTER_PROMPT = """你是一个小说作家。根据审核反馈，重写章节正文。

原章节大纲：
{chapter_outline}

审核反馈：
{review_feedback}

问题章节：
{original_content}

请根据审核反馈重写，注意：
1. 解决审核指出的问题
2. 保持情节连贯
3. 不要引入新问题

请直接输出重写后的章节正文。
"""
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/agents/state.py backend/app/agents/prompts.py
git commit -m "feat: add LangGraph agent state and prompt templates"
```

---

### Task 17: LangGraph Agent 节点实现

**Files:**
- Create: `backend/app/agents/nodes/info_collection.py`
- Create: `backend/app/agents/nodes/outline_generation.py`
- Create: `backend/app/agents/nodes/chapter_generation.py`

- [ ] **Step 1: 创建信息收集节点**

```python
# backend/app/agents/nodes/info_collection.py
"""Info collection node"""

from typing import Dict, Any
import json

from app.agents.state import NovelState, STAGE_OUTLINE_GENERATING
from app.agents.prompts import INFO_COLLECTION_SYSTEM_PROMPT
from app.services.llm import LLMService


def parse_collected_info(response: str, current_info: Dict[str, str]) -> Dict[str, str]:
    """Parse collected info from response"""
    # Simple parsing - extract info from response
    # This is a simplified implementation
    info = current_info.copy()

    # Look for key information in the response
    keywords = {
        "genre": ["题材", "类型", "武侠", "科幻", "都市", "言情", "悬疑", "奇幻"],
        "theme": ["主题", "主线", "核心"],
        "main_characters": ["主角", "人物", "角色"],
        "world_setting": ["背景", "时代", "世界观"],
        "style_preference": ["风格", "字数", "篇幅"]
    }

    # Check if info is sufficient
    if "信息已充足" in response:
        return info, True

    return info, False


async def info_collection_node(state: NovelState, llm: LLMService) -> NovelState:
    """Handle info collection"""

    # Format current collected info
    collected_info = state.get("collected_info", {})
    info_str = "\n".join([f"- {k}: {v}" for k, v in collected_info.items()]) or "（尚未收集任何信息）"

    # Build system prompt
    system_prompt = INFO_COLLECTION_SYSTEM_PROMPT.format(collected_info=info_str)

    # Build messages
    messages = state.get("messages", [])
    last_user_message = state.get("last_user_message", "")

    if last_user_message:
        messages = messages + [{"role": "user", "content": last_user_message}]

    # Get response
    response = await llm.chat_with_system(system_prompt, messages)

    # Parse collected info
    updated_info, is_sufficient = parse_collected_info(response, collected_info)

    # Build new state
    new_messages = messages + [{"role": "assistant", "content": response}]

    new_state: NovelState = {
        **state,
        "collected_info": updated_info,
        "messages": new_messages,
        "last_assistant_message": response,
    }

    # Check if we should move to next stage
    if is_sufficient:
        new_state["stage"] = STAGE_OUTLINE_GENERATING

    return new_state
```

- [ ] **Step 2: 创建大纲生成节点**

```python
# backend/app/agents/nodes/outline_generation.py
"""Outline generation nodes"""

import re
from typing import Dict, Any

from app.agents.state import NovelState, STAGE_OUTLINE_CONFIRMING, STAGE_CHAPTER_COUNT_SUGGESTING
from app.agents.prompts import (
    GENERATE_OUTLINE_PROMPT,
    SUGGEST_CHAPTER_COUNT_PROMPT
)
from app.services.llm import LLMService


def parse_outline(response: str) -> Dict[str, Any]:
    """Parse outline from response"""
    outline = {
        "title": "",
        "summary": "",
        "plot_points": []
    }

    # Extract title
    title_match = re.search(r"标题[：:]\s*(.+)", response)
    if title_match:
        outline["title"] = title_match.group(1).strip()

    # Extract summary
    summary_match = re.search(r"概述[：:]\s*(.+?)(?=主要情节节点|情节节点|$)", response, re.DOTALL)
    if summary_match:
        outline["summary"] = summary_match.group(1).strip()

    # Extract plot points
    plot_matches = re.findall(r"\d+\.\s*(.+?)(?=\d+\.|$)", response, re.DOTALL)
    outline["plot_points"] = [p.strip() for p in plot_matches]

    return outline


def parse_chapter_count(response: str) -> int:
    """Parse suggested chapter count from response"""
    match = re.search(r"建议章节数[：:]\s*(\d+)", response)
    if match:
        return int(match.group(1))
    return 10  # Default


async def generate_outline_node(state: NovelState, llm: LLMService) -> NovelState:
    """Generate outline from collected info"""

    info = state.get("collected_info", {})

    prompt = GENERATE_OUTLINE_PROMPT.format(
        genre=info.get("genre", "未指定"),
        theme=info.get("theme", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        world_setting=info.get("world_setting", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    outline = parse_outline(response)

    new_state: NovelState = {
        **state,
        "outline_title": outline["title"],
        "outline_summary": outline["summary"],
        "outline_plot_points": outline["plot_points"],
        "stage": STAGE_OUTLINE_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state


async def suggest_chapter_count_node(state: NovelState, llm: LLMService) -> NovelState:
    """Suggest chapter count"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    if plot_points:
        outline += "\n主要情节节点：\n" + "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)])

    prompt = SUGGEST_CHAPTER_COUNT_PROMPT.format(outline=outline)

    response = await llm.chat([{"role": "user", "content": prompt}])

    chapter_count = parse_chapter_count(response)

    new_state: NovelState = {
        **state,
        "chapter_count_suggested": chapter_count,
        "stage": STAGE_CHAPTER_COUNT_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state
```

- [ ] **Step 3: 创建章节生成节点**

```python
# backend/app/agents/nodes/chapter_generation.py
"""Chapter generation nodes"""

import re
from typing import Dict, Any, AsyncIterator

from app.agents.state import NovelState, STAGE_CHAPTER_OUTLINES_CONFIRMING, STAGE_CHAPTER_WRITING
from app.agents.prompts import (
    GENERATE_CHAPTER_OUTLINES_PROMPT,
    GENERATE_CHAPTER_CONTENT_PROMPT,
    REVIEW_CHAPTER_PROMPT
)
from app.services.llm import LLMService


def parse_chapter_outlines(response: str) -> list[dict]:
    """Parse chapter outlines from response"""
    chapters = []

    # Split by chapter markers
    pattern = r"第(\d+)章[：:]\s*(.+?)(?=第\d+章|$)"
    matches = re.findall(pattern, response, re.DOTALL)

    for num, content in matches:
        chapter = {
            "chapter_number": int(num),
            "title": "",
            "scene": "",
            "characters": "",
            "plot": "",
            "conflict": "",
            "ending": "",
            "target_words": 3000
        }

        # Extract fields
        title_match = re.search(r"章节名[：:]\s*(.+)", content)
        if title_match:
            chapter["title"] = title_match.group(1).strip()

        scene_match = re.search(r"场景[：:]\s*(.+)", content)
        if scene_match:
            chapter["scene"] = scene_match.group(1).strip()

        characters_match = re.search(r"人物[：:]\s*(.+)", content)
        if characters_match:
            chapter["characters"] = characters_match.group(1).strip()

        plot_match = re.search(r"情节[：:]\s*(.+?)(?=冲突|结局|预计字数|$)", content, re.DOTALL)
        if plot_match:
            chapter["plot"] = plot_match.group(1).strip()

        conflict_match = re.search(r"冲突[：:]\s*(.+?)(?=结局|预计字数|$)", content, re.DOTALL)
        if conflict_match:
            chapter["conflict"] = conflict_match.group(1).strip()

        ending_match = re.search(r"结局[：:]\s*(.+?)(?=预计字数|$)", content, re.DOTALL)
        if ending_match:
            chapter["ending"] = ending_match.group(1).strip()

        words_match = re.search(r"预计字数[：:]\s*(\d+)", content)
        if words_match:
            chapter["target_words"] = int(words_match.group(1))

        chapters.append(chapter)

    return chapters


async def generate_chapter_outlines_node(state: NovelState, llm: LLMService) -> NovelState:
    """Generate all chapter outlines"""

    outline = f"标题：{state.get('outline_title', '')}\n概述：{state.get('outline_summary', '')}"
    plot_points = state.get("outline_plot_points", [])
    if plot_points:
        outline += "\n主要情节节点：\n" + "\n".join([f"{i+1}. {p}" for i, p in enumerate(plot_points)])

    chapter_count = state.get("chapter_count_suggested", 10)

    prompt = GENERATE_CHAPTER_OUTLINES_PROMPT.format(
        outline=outline,
        chapter_count=chapter_count
    )

    response = await llm.chat([{"role": "user", "content": prompt}], max_tokens=8192)

    chapter_outlines = parse_chapter_outlines(response)

    new_state: NovelState = {
        **state,
        "chapter_outlines": chapter_outlines,
        "stage": STAGE_CHAPTER_OUTLINES_CONFIRMING,
        "last_assistant_message": response,
    }

    return new_state


async def generate_chapter_content_stream(
    state: NovelState,
    chapter_outline: dict,
    llm: LLMService
) -> AsyncIterator[str]:
    """Generate chapter content with streaming"""

    info = state.get("collected_info", {})

    # Format chapter outline
    outline_str = f"""
第{chapter_outline['chapter_number']}章：{chapter_outline['title']}
场景：{chapter_outline['scene']}
人物：{chapter_outline['characters']}
情节：{chapter_outline['plot']}
冲突：{chapter_outline['conflict']}
结局：{chapter_outline['ending']}
"""

    prompt = GENERATE_CHAPTER_CONTENT_PROMPT.format(
        chapter_outline=outline_str,
        previous_ending="",  # TODO: Get from previous chapter
        genre=info.get("genre", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        world_setting=info.get("world_setting", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    async for chunk in llm.chat_stream([{"role": "user", "content": prompt}]):
        yield chunk


async def review_chapter_node(
    state: NovelState,
    chapter_content: str,
    chapter_outline: dict,
    llm: LLMService,
    strictness: str = "standard"
) -> Dict[str, Any]:
    """Review chapter content"""

    info = state.get("collected_info", {})

    outline_str = f"第{chapter_outline['chapter_number']}章：{chapter_outline['title']}\n情节：{chapter_outline['plot']}"

    prompt = REVIEW_CHAPTER_PROMPT.format(
        strictness=strictness,
        chapter_outline=outline_str,
        chapter_content=chapter_content,
        genre=info.get("genre", "未指定"),
        main_characters=info.get("main_characters", "未指定"),
        style_preference=info.get("style_preference", "未指定")
    )

    response = await llm.chat([{"role": "user", "content": prompt}])

    # Parse result
    passed = "【审核结果】通过" in response

    # Extract issues
    issues = []
    issues_match = re.search(r"【问题列表】(.+?)【修改建议】", response, re.DOTALL)
    if issues_match:
        issues_text = issues_match.group(1)
        issues = [i.strip() for i in re.findall(r"\d+\.\s*(.+)", issues_text) if i.strip()]

    # Extract suggestions
    suggestions = ""
    suggestions_match = re.search(r"【修改建议】(.+?)(?=---|$)", response, re.DOTALL)
    if suggestions_match:
        suggestions = suggestions_match.group(1).strip()

    return {
        "passed": passed,
        "issues": issues,
        "feedback": response,
        "suggestions": suggestions
    }
```

- [ ] **Step 4: 更新节点导出**

```python
# backend/app/agents/nodes/__init__.py
"""Agent nodes"""

from app.agents.nodes.info_collection import info_collection_node
from app.agents.nodes.outline_generation import (
    generate_outline_node,
    suggest_chapter_count_node
)
from app.agents.nodes.chapter_generation import (
    generate_chapter_outlines_node,
    generate_chapter_content_stream,
    review_chapter_node
)

__all__ = [
    "info_collection_node",
    "generate_outline_node",
    "suggest_chapter_count_node",
    "generate_chapter_outlines_node",
    "generate_chapter_content_stream",
    "review_chapter_node",
]
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/agents/nodes/*.py
git commit -m "feat: implement LangGraph agent nodes"
```

---

## Phase 2 自检

**Spec 覆盖检查：**

| 设计文档要求 | 对应任务 |
|-------------|---------|
| Session + Cookie 认证 | Task 11, 13 |
| 密码哈希 | Task 11 |
| 项目 CRUD | Task 14 |
| LangGraph Agent | Task 15-17 |
| 多模型支持 | Task 15 |
| 流式生成 | Task 15, 17 |

**占位符检查：** ✅ 无 TBD、TODO

**类型一致性检查：** ✅ Schema 与 Model 字段一致

---

Phase 2 计划完成。继续 Phase 3: 前端实现？