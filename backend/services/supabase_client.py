"""Supabase clients for auth verification and service-role credit ops."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


class SupabaseNotConfigured(RuntimeError):
    pass


def supabase_enabled() -> bool:
    s = get_settings()
    return bool(s.supabase_url and (s.supabase_service_role_key or s.supabase_anon_key))


@lru_cache
def _headers_service() -> dict[str, str]:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise SupabaseNotConfigured("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def get_user_from_jwt(access_token: str) -> dict[str, Any]:
    """Validate a Supabase user access token and return the user payload."""
    s = get_settings()
    if not s.supabase_url or not s.supabase_anon_key:
        raise SupabaseNotConfigured("Supabase is not configured")

    url = f"{s.supabase_url.rstrip('/')}/auth/v1/user"
    headers = {
        "apikey": s.supabase_anon_key,
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 401:
            raise PermissionError("Invalid or expired session")
        resp.raise_for_status()
        return resp.json()


async def rest_select(table: str, *, query: str = "", single: bool = False) -> Any:
    s = get_settings()
    url = f"{s.supabase_url.rstrip('/')}/rest/v1/{table}?{query}"
    headers = _headers_service()
    if single:
        headers = {**headers, "Accept": "application/vnd.pgrst.object+json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 406 and single:
            return None
        resp.raise_for_status()
        if not resp.content:
            return None if single else []
        return resp.json()


async def rest_patch(table: str, *, query: str, body: dict) -> Any:
    s = get_settings()
    url = f"{s.supabase_url.rstrip('/')}/rest/v1/{table}?{query}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.patch(url, headers=_headers_service(), json=body)
        resp.raise_for_status()
        return resp.json() if resp.content else None


async def rest_insert(table: str, body: dict | list) -> Any:
    s = get_settings()
    url = f"{s.supabase_url.rstrip('/')}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=_headers_service(), json=body)
        resp.raise_for_status()
        return resp.json() if resp.content else None
