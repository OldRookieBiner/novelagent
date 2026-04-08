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
    from app.models.settings import UserSettings
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
            db.refresh(user)

            # Create default settings for user
            user_settings = UserSettings(
                user_id=user.id,
                model_provider=settings.default_model_provider,
                model_name="deepseek-chat",
                api_key_encrypted=None,
                review_enabled=True,
                review_strictness="standard"
            )
            db.add(user_settings)
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