# NovelAgent v0.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 NovelAgent 从 CLI 应用重构为 Web 应用，支持短/中篇小说创作。

**Architecture:** React 18 + Vite 前端 + FastAPI 后端 + PostgreSQL 数据库 + LangGraph Agent 框架，Docker 容器化部署。

**Tech Stack:** React, Vite, shadcn/ui, Tailwind CSS, Zustand, React Router, TipTap, FastAPI, SQLAlchemy, Alembic, PostgreSQL, LangGraph, Docker

---

## Phase 1: 项目基础设施

### Task 1: 创建项目目录结构

**Files:**
- Create: `backend/` 目录结构
- Create: `frontend/` 目录结构

- [ ] **Step 1: 创建后端目录结构**

```bash
mkdir -p backend/app/{models,schemas,api,agents/nodes,services,utils}
mkdir -p backend/alembic/versions
touch backend/app/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/api/__init__.py
touch backend/app/agents/__init__.py
touch backend/app/agents/nodes/__init__.py
touch backend/app/services/__init__.py
touch backend/app/utils/__init__.py
```

- [ ] **Step 2: 创建前端目录结构**

```bash
mkdir -p frontend/src/{components/{ui,layout,common},pages,hooks,stores,lib,types}
```

- [ ] **Step 3: 提交**

```bash
git add .
git commit -m "chore: create project directory structure"
```

---

### Task 2: Docker Compose 配置

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://novelagent:novelagent@db:5432/novelagent
      - SECRET_KEY=${SECRET_KEY:-your-secret-key-change-in-production}
      - DEFAULT_USERNAME=${DEFAULT_USERNAME:-admin}
      - DEFAULT_PASSWORD=${DEFAULT_PASSWORD:-admin123}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=novelagent
      - POSTGRES_USER=novelagent
      - POSTGRES_PASSWORD=novelagent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U novelagent"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 2: 创建 .env.example**

```bash
# .env.example
# Database
DATABASE_URL=postgresql://novelagent:novelagent@db:5432/novelagent

# Authentication
SECRET_KEY=your-secret-key-change-in-production
DEFAULT_USERNAME=admin
DEFAULT_PASSWORD=admin123

# Model (optional defaults)
DEFAULT_MODEL_PROVIDER=deepseek
DEFAULT_API_KEY=your-api-key
```

- [ ] **Step 3: 提交**

```bash
git add docker-compose.yml .env.example
git commit -m "feat: add docker compose configuration"
```

---

### Task 3: 后端依赖配置

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`

- [ ] **Step 1: 创建 requirements.txt**

```text
# backend/requirements.txt
# Web Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0
psycopg2-binary==2.9.9

# Authentication
passlib[bcrypt]==1.7.4
itsdangerous==2.1.2

# LLM & Agent
langgraph==0.0.40
langchain==0.1.6
langchain-openai==0.0.5
openai==1.10.0

# Utilities
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.0
cryptography==42.0.0
httpx==0.26.0
```

- [ ] **Step 2: 创建 Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/requirements.txt backend/Dockerfile
git commit -m "feat: add backend dependencies and Dockerfile"
```

---

### Task 4: 后端配置模块

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

- [ ] **Step 1: 创建配置模块**

```python
# backend/app/config.py
"""Application configuration"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql://novelagent:novelagent@localhost:5432/novelagent"

    # Authentication
    secret_key: str = "your-secret-key-change-in-production"
    default_username: str = "admin"
    default_password: str = "admin123"
    session_expire_seconds: int = 86400 * 7  # 7 days

    # Model defaults
    default_model_provider: str = "deepseek"
    default_api_key: str = ""

    # App settings
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

- [ ] **Step 2: 创建数据库连接模块**

```python
# backend/app/database.py
"""Database connection and session management"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/config.py backend/app/database.py
git commit -m "feat: add backend config and database modules"
```

---

### Task 5: 数据库模型 - 用户和设置

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/settings.py`

- [ ] **Step 1: 创建用户模型**

```python
# backend/app/models/user.py
"""User model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"
```

- [ ] **Step 2: 创建用户设置模型**

```python
# backend/app/models/settings.py
"""User settings model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class UserSettings(Base):
    """User settings model"""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    model_provider = Column(String(50), default="deepseek")
    model_name = Column(String(100), default="deepseek-chat")
    api_key_encrypted = Column(Text, nullable=True)
    review_enabled = Column(Boolean, default=True)
    review_strictness = Column(String(20), default="standard")  # loose, standard, strict
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/user.py backend/app/models/settings.py
git commit -m "feat: add User and UserSettings models"
```

---

### Task 6: 数据库模型 - 项目和大纲

**Files:**
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/outline.py`

- [ ] **Step 1: 创建项目模型**

```python
# backend/app/models/project.py
"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """Project model"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    stage = Column(String(50), default="collecting_info")  # collecting_info, outlining, writing, completed, paused
    target_words = Column(Integer, default=100000)
    total_words = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="projects")
    outline = relationship("Outline", back_populates="project", uselist=False, cascade="all, delete-orphan")
    chapter_outlines = relationship("ChapterOutline", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"
```

- [ ] **Step 2: 创建大纲模型**

```python
# backend/app/models/outline.py
"""Outline models"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Outline(Base):
    """Novel outline model"""

    __tablename__ = "outlines"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    title = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    plot_points = Column(JSON, default=list)  # List of plot points
    collected_info = Column(JSON, default=dict)  # Collected information from user
    chapter_count_suggested = Column(Integer, default=0)
    chapter_count_confirmed = Column(Boolean, default=False)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="outline")

    def __repr__(self):
        return f"<Outline project_id={self.project_id}>"


class ChapterOutline(Base):
    """Chapter outline model"""

    __tablename__ = "chapter_outlines"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    scene = Column(String(500), nullable=True)
    characters = Column(Text, nullable=True)
    plot = Column(Text, nullable=True)
    conflict = Column(Text, nullable=True)
    ending = Column(Text, nullable=True)
    target_words = Column(Integer, default=3000)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="chapter_outlines")
    chapter = relationship("Chapter", back_populates="chapter_outline", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChapterOutline project_id={self.project_id} chapter={self.chapter_number}>"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/project.py backend/app/models/outline.py
git commit -m "feat: add Project, Outline, and ChapterOutline models"
```

---

### Task 7: 数据库模型 - 章节正文

**Files:**
- Create: `backend/app/models/chapter.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建章节模型**

```python
# backend/app/models/chapter.py
"""Chapter model"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Chapter(Base):
    """Chapter content model"""

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    chapter_outline_id = Column(Integer, ForeignKey("chapter_outlines.id", ondelete="CASCADE"), unique=True, nullable=False)
    content = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    review_passed = Column(Boolean, default=False)
    review_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chapter_outline = relationship("ChapterOutline", back_populates="chapter")

    def __repr__(self):
        return f"<Chapter id={self.id}>"
```

- [ ] **Step 2: 更新模型导出**

```python
# backend/app/models/__init__.py
"""Database models"""

from app.models.user import User
from app.models.settings import UserSettings
from app.models.project import Project
from app.models.outline import Outline, ChapterOutline
from app.models.chapter import Chapter

__all__ = ["User", "UserSettings", "Project", "Outline", "ChapterOutline", "Chapter"]
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/chapter.py backend/app/models/__init__.py
git commit -m "feat: add Chapter model and export all models"
```

---

### Task 8: Alembic 数据库迁移配置

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`

- [ ] **Step 1: 创建 alembic.ini**

```ini
# backend/alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = postgresql://novelagent:novelagent@localhost:5432/novelagent

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: 创建 alembic/env.py**

```python
# backend/alembic/env.py
"""Alembic environment configuration"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.config import settings
from app.database import Base
from app.models import *  # Import all models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: 创建迁移模板**

```python
# backend/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: 提交**

```bash
git add backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako
git commit -m "feat: add Alembic migration configuration"
```

---

### Task 9: 初始数据库迁移

**Files:**
- Create: `backend/alembic/versions/001_initial.py`

- [ ] **Step 1: 创建初始迁移文件**

```python
# backend/alembic/versions/001_initial.py
"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # User settings table
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('model_provider', sa.String(50), nullable=True, default='deepseek'),
        sa.Column('model_name', sa.String(100), nullable=True, default='deepseek-chat'),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('review_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('review_strictness', sa.String(20), nullable=True, default='standard'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # Projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('stage', sa.String(50), nullable=True, default='collecting_info'),
        sa.Column('target_words', sa.Integer(), nullable=True, default=100000),
        sa.Column('total_words', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # Outlines table
    op.create_table(
        'outlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('plot_points', sa.JSON(), nullable=True),
        sa.Column('collected_info', sa.JSON(), nullable=True),
        sa.Column('chapter_count_suggested', sa.Integer(), nullable=True, default=0),
        sa.Column('chapter_count_confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id')
    )

    # Chapter outlines table
    op.create_table(
        'chapter_outlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('scene', sa.String(500), nullable=True),
        sa.Column('characters', sa.Text(), nullable=True),
        sa.Column('plot', sa.Text(), nullable=True),
        sa.Column('conflict', sa.Text(), nullable=True),
        sa.Column('ending', sa.Text(), nullable=True),
        sa.Column('target_words', sa.Integer(), nullable=True, default=3000),
        sa.Column('confirmed', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chapter_outlines_project_id', 'chapter_outlines', ['project_id'])

    # Chapters table
    op.create_table(
        'chapters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_outline_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True, default=0),
        sa.Column('review_passed', sa.Boolean(), nullable=True, default=False),
        sa.Column('review_feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_outline_id'], ['chapter_outlines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chapter_outline_id')
    )


def downgrade() -> None:
    op.drop_table('chapters')
    op.drop_table('chapter_outlines')
    op.drop_table('outlines')
    op.drop_table('projects')
    op.drop_table('user_settings')
    op.drop_table('users')
```

- [ ] **Step 2: 提交**

```bash
git add backend/alembic/versions/001_initial.py
git commit -m "feat: add initial database migration"
```

---

### Task 10: FastAPI 主应用入口

**Files:**
- Create: `backend/app/main.py`

- [ ] **Step 1: 创建 FastAPI 主应用**

```python
# backend/app/main.py
"""FastAPI application entry point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import auth, projects, outline, chapters, settings as settings_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup: Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Create default user if not exists
    from app.utils.auth import create_default_user
    create_default_user()

    yield

    # Shutdown
    pass


app = FastAPI(
    title="NovelAgent API",
    description="AI Novel Creation Assistant API",
    version="0.2.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(outline.router, prefix="/api/projects", tags=["outline"])
app.include_router(chapters.router, prefix="/api/projects", tags=["chapters"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "NovelAgent API", "version": "0.2.0"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
```

- [ ] **Step 2: 创建占位路由文件**

```python
# backend/app/api/auth.py
"""Authentication API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Login endpoint - to be implemented"""
    pass


@router.post("/logout")
async def logout():
    """Logout endpoint - to be implemented"""
    pass


@router.get("/me")
async def get_current_user():
    """Get current user - to be implemented"""
    pass
```

```python
# backend/app/api/projects.py
"""Projects API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_projects():
    """List projects - to be implemented"""
    pass


@router.post("/")
async def create_project():
    """Create project - to be implemented"""
    pass


@router.get("/{project_id}")
async def get_project(project_id: int):
    """Get project - to be implemented"""
    pass


@router.put("/{project_id}")
async def update_project(project_id: int):
    """Update project - to be implemented"""
    pass


@router.delete("/{project_id}")
async def delete_project(project_id: int):
    """Delete project - to be implemented"""
    pass
```

```python
# backend/app/api/outline.py
"""Outline API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{project_id}/outline")
async def get_outline(project_id: int):
    """Get outline - to be implemented"""
    pass


@router.post("/{project_id}/outline")
async def create_outline(project_id: int):
    """Create outline - to be implemented"""
    pass


@router.put("/{project_id}/outline")
async def update_outline(project_id: int):
    """Update outline - to be implemented"""
    pass


@router.post("/{project_id}/outline/confirm")
async def confirm_outline(project_id: int):
    """Confirm outline - to be implemented"""
    pass
```

```python
# backend/app/api/chapters.py
"""Chapters API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{project_id}/chapter-outlines")
async def list_chapter_outlines(project_id: int):
    """List chapter outlines - to be implemented"""
    pass


@router.post("/{project_id}/chapter-outlines")
async def create_chapter_outlines(project_id: int):
    """Create chapter outlines - to be implemented"""
    pass


@router.get("/{project_id}/chapters/{chapter_num}")
async def get_chapter(project_id: int, chapter_num: int):
    """Get chapter - to be implemented"""
    pass


@router.post("/{project_id}/chapters/{chapter_num}")
async def create_chapter(project_id: int, chapter_num: int):
    """Create chapter - to be implemented"""
    pass


@router.put("/{project_id}/chapters/{chapter_num}")
async def update_chapter(project_id: int, chapter_num: int):
    """Update chapter - to be implemented"""
    pass


@router.post("/{project_id}/chapters/{chapter_num}/review")
async def review_chapter(project_id: int, chapter_num: int):
    """Review chapter - to be implemented"""
    pass
```

```python
# backend/app/api/settings.py
"""Settings API routes"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_settings():
    """Get settings - to be implemented"""
    pass


@router.put("/")
async def update_settings():
    """Update settings - to be implemented"""
    pass
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/main.py backend/app/api/*.py
git commit -m "feat: add FastAPI main application and placeholder routes"
```

---

## Phase 1 自检

**Spec 覆盖检查：**

| 设计文档要求 | 对应任务 |
|-------------|---------|
| PostgreSQL 数据库 | Task 2, 3, 5-9 |
| Docker + Docker Compose | Task 2 |
| SQLAlchemy ORM | Task 5-7 |
| Alembic 迁移 | Task 8-9 |
| FastAPI 框架 | Task 10 |
| 数据库表结构 | Task 5-9 |

**占位符检查：** ✅ 无 TBD、TODO

**类型一致性检查：** ✅ 模型字段与设计文档一致

---

Phase 1 完成。基础设施已就绪，可以继续 Phase 2: 后端核心功能实现。

是否继续编写 Phase 2-5 的详细计划？