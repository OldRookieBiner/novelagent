"""Authentication utilities"""
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.models.settings import UserSettings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_default_user() -> None:
    """Create default user if not exists"""
    db: Session = SessionLocal()
    try:
        # Check if default user exists
        user = db.query(User).filter(User.username == settings.default_username).first()
        if not user:
            # Create default user
            user = User(
                username=settings.default_username,
                password_hash=get_password_hash(settings.default_password),
                is_active=True
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
    finally:
        db.close()