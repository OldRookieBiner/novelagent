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
        user=UserResponse.model_validate(user),
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
    return UserResponse.model_validate(current_user)