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