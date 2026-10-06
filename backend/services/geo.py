"""
Country / currency detection for Cleepye pricing.

Rule:
  - Nigeria (NG) → NGN
  - Everywhere else → USD

Detection order:
  1. Explicit override (?currency= or X-Cleepye-Currency)
  2. Cloudflare / proxy country headers
  3. IP geolocation via ipapi.co (free, no key)
  4. Accept-Language hint (weak)
  5. Default USD (safer for Topaz cost alignment outside NG)
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from fastapi import Request

logger = logging.getLogger(__name__)

SUPPORTED = ("NGN", "USD")


def normalize_currency(value: str | None) -> str | None:
    if not value:
        return None
    c = value.strip().upper()
    if c in SUPPORTED:
        return c
    if c in ("NAIRA", "₦", "NG"):
        return "NGN"
    if c in ("DOLLAR", "DOLLARS", "$", "US"):
        return "USD"
    return None


def country_from_headers(request: Request) -> str | None:
    """Trusted edge headers first (Cloudflare, Vercel, etc.)."""
    headers = request.headers
    for key in (
        "cf-ipcountry",
        "cloudfront-viewer-country",
        "x-vercel-ip-country",
        "x-country-code",
        "x-geo-country",
    ):
        raw = headers.get(key)
        if raw and len(raw.strip()) == 2 and raw.strip().isalpha():
            return raw.strip().upper()
    return None


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # first hop is original client
        part = forwarded.split(",")[0].strip()
        if part:
            return part
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    if request.client:
        return request.client.host
    return None


async def country_from_ip(ip: str | None) -> str | None:
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return None
    # Private ranges — skip lookup
    if ip.startswith(("10.", "192.168.", "172.")) or ip.startswith("fc") or ip.startswith("fe80"):
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # ipapi.co free tier — no key required for light use
            resp = await client.get(f"https://ipapi.co/{ip}/country_code/")
            if resp.status_code == 200:
                code = resp.text.strip().upper()
                if len(code) == 2 and code.isalpha():
                    return code
    except Exception as e:
        logger.debug(f"IP geo failed for {ip}: {e}")
    return None


def country_from_accept_language(request: Request) -> str | None:
    """Weak signal only — e.g. en-NG → NG."""
    al = request.headers.get("accept-language") or ""
    m = re.search(r"(?:^|,)\s*[a-zA-Z]{2,3}[-_]([A-Za-z]{2})", al)
    if m:
        return m.group(1).upper()
    return None


def currency_for_country(country_code: str | None) -> str:
    if (country_code or "").upper() == "NG":
        return "NGN"
    return "USD"


async def resolve_currency(request: Request, override: str | None = None) -> dict[str, Any]:
    """
    Returns { currency, country, source }.
    """
    forced = normalize_currency(override) or normalize_currency(
        request.headers.get("x-cleepye-currency")
    ) or normalize_currency(request.query_params.get("currency"))
    if forced:
        return {
            "currency": forced,
            "country": "NG" if forced == "NGN" else None,
            "source": "override",
        }

    country = country_from_headers(request)
    source = "header" if country else None

    if not country:
        ip = client_ip(request)
        country = await country_from_ip(ip)
        if country:
            source = "ip"

    if not country:
        country = country_from_accept_language(request)
        if country:
            source = "accept-language"

    currency = currency_for_country(country)
    return {
        "currency": currency,
        "country": country,
        "source": source or "default",
    }
