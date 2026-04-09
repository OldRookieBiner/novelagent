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
    clear_api_key: Optional[bool] = None  # Set to True to delete existing API key


class SettingsResponse(BaseModel):
    model_provider: str
    model_name: str
    has_api_key: bool  # Don't expose actual key
    review_enabled: bool
    review_strictness: str

    class Config:
        from_attributes = True