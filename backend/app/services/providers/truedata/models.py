"""TrueData Pydantic Data Models."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TrueDataCredentialCreate(BaseModel):
    label: str = Field(default="My TrueData Feed", description="Human readable label")
    username: str = Field(..., description="TrueData Login ID")
    password: str = Field(..., description="TrueData Account Password")
    realtime_port: int = Field(default=8082, description="Target WebSocket realtime port")


class TrueDataCredentialUpdate(BaseModel):
    label: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    realtime_port: Optional[int] = None


class TrueDataCredentialResponse(BaseModel):
    id: str
    user_id: str
    label: str
    username_hint: str
    has_credentials: bool
    connected: bool
    is_active: bool
    realtime_port: int
    token_expires_at: Optional[float] = None
    last_login_at_ms: Optional[int] = None
    created_at_ms: int
    updated_at_ms: int


class TrueDataStatus(BaseModel):
    connected: bool
    is_active: bool
    account_id: Optional[str] = None
    username_hint: Optional[str] = None
    message: str
