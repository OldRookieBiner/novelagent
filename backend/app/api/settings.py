"""Settings API routes"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.settings import UserSettings
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.utils.auth import get_current_user
from app.services.crypto import encrypt_api_key

router = APIRouter()

# Default model name mapping for each provider
DEFAULT_MODEL_NAMES = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o",
    "deepseek-official": "deepseek-chat",
}


def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    """Get existing settings or create default settings for user."""
    settings = db.query(UserSettings).filter(
        UserSettings.user_id == user_id
    ).first()

    if not settings:
        # Create default settings
        settings = UserSettings(
            user_id=user_id,
            model_provider="deepseek",
            model_name="deepseek-chat",
            review_enabled=True,
            review_strictness="standard"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user settings.

    Returns model_provider, model_name, has_api_key (boolean), review_enabled, review_strictness.
    Creates default settings if user doesn't have any.
    """
    settings = get_or_create_settings(db, current_user.id)

    return SettingsResponse(
        model_provider=settings.model_provider,
        model_name=settings.model_name,
        has_api_key=bool(settings.api_key_encrypted),
        review_enabled=settings.review_enabled,
        review_strictness=settings.review_strictness
    )


@router.put("/", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user settings.

    Updates model_provider, model_name, review_enabled, review_strictness.
    If api_key is provided, encrypts it before saving.
    Returns updated settings.
    """
    settings = get_or_create_settings(db, current_user.id)

    # Update model_provider and model_name together
    if request.model_provider is not None:
        settings.model_provider = request.model_provider
        # Update model_name based on provider
        settings.model_name = DEFAULT_MODEL_NAMES.get(
            request.model_provider,
            request.model_name or settings.model_name
        )
    elif request.model_name is not None:
        settings.model_name = request.model_name

    # Encrypt and save API key if provided
    if request.api_key is not None:
        settings.api_key_encrypted = encrypt_api_key(request.api_key)
    # Clear API key if requested
    elif request.clear_api_key is True:
        settings.api_key_encrypted = None

    # Update review settings if provided
    if request.review_enabled is not None:
        settings.review_enabled = request.review_enabled

    if request.review_strictness is not None:
        settings.review_strictness = request.review_strictness

    db.commit()
    db.refresh(settings)

    return SettingsResponse(
        model_provider=settings.model_provider,
        model_name=settings.model_name,
        has_api_key=bool(settings.api_key_encrypted),
        review_enabled=settings.review_enabled,
        review_strictness=settings.review_strictness
    )