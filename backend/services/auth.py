"""FastAPI auth dependencies (Supabase JWT)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Header, HTTPException

from backend.config import get_settings
from backend.services.supabase_client import get_user_from_jwt, supabase_enabled


@dataclass
class AuthUser:
    id: str
    email: str | None
    raw: dict[str, Any]


async def optional_user(authorization: Optional[str] = Header(default=None)) -> AuthUser | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token or not supabase_enabled():
        return None
    try:
        data = await get_user_from_jwt(token)
        return AuthUser(id=data["id"], email=data.get("email"), raw=data)
    except PermissionError:
        return None
    except Exception:
        return None


async def require_user(authorization: Optional[str] = Header(default=None)) -> AuthUser:
    settings = get_settings()
    user = await optional_user(authorization)
    if user:
        return user
    if not settings.auth_required and not supabase_enabled():
        # Pure local mode — synthetic user (credits disabled)
        return AuthUser(id="local", email=None, raw={})
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in required")
    raise HTTPException(status_code=401, detail="Invalid or expired session")
