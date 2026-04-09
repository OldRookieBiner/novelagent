"""Test configuration and fixtures"""

import os
import sys
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.settings import UserSettings
from app.utils.auth import hash_password, create_session_token


# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator:
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db) -> TestClient:
    """Create a test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(db) -> User:
    """Create a test user"""
    user = User(
        username="testuser",
        password_hash=hash_password("testpassword123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create user settings
    settings = UserSettings(user_id=user.id)
    db.add(settings)
    db.commit()

    return user


@pytest.fixture(scope="function")
def test_user_token(test_user) -> str:
    """Get session token for test user"""
    return create_session_token(test_user.id)


@pytest.fixture(scope="function")
def auth_headers(test_user_token) -> dict:
    """Get authorization headers for test user"""
    import base64
    credentials = base64.b64encode(f"{test_user_token}:".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}