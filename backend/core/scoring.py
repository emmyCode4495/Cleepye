"""
Viral moment scoring.

Supports:
- Fully local via Ollama
- BYOK via OpenRouter / OpenAI / Anthropic
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


SCORING_PROMPT = """You are an expert short-form video editor specializing in viral clips for TikTok, YouTube Shorts, and Instagram Reels.

Given a transcript of a long video, identify the best 30-60 second moments that would work as standalone viral clips.

For each candidate clip return:
- start: start time in seconds (float)
- end: end time in seconds (float)
- score: 0-100 viral potential
- hook: a short description of why this moment is strong (max 15 words)
- title: a catchy short title for the clip (max 8 words)

Rules:
- Prefer complete thoughts / emotional peaks / strong advice / surprising statements
- Clips must be between 25 and 65 seconds
- Avoid starting or ending mid-sentence when possible
- Return 5 to 12 high-quality candidates maximum
- Rank by score descending
- Output ONLY valid JSON array, no markdown, no explanation

Transcript:
{transcript}
"""


async def score_with_ollama(transcript: str) -> list[dict[str, Any]]:
    settings = get_settings()
    prompt = SCORING_PROMPT.format(transcript=transcript[:12000])  # safety limit

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "[]")

    return _parse_scores(raw)


async def score_with_openrouter(transcript: str) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter")

    prompt = SCORING_PROMPT.format(transcript=transcript[:14000])

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",  # good balance
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]

    return _parse_scores(raw)


def _parse_scores(raw: str) -> list[dict[str, Any]]:
    """Extract JSON array from model output, with fallbacks."""
    raw = raw.strip()

    # Try direct parse
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return _normalize(data)
        if isinstance(data, dict) and "clips" in data:
            return _normalize(data["clips"])
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            data = json.loads(match.group(0))
            return _normalize(data)
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse scoring output, returning empty list")
    return []


def _normalize(items: list) -> list[dict[str, Any]]:
    result = []
    for item in items:
        try:
            start = float(item.get("start", 0))
            end = float(item.get("end", 0))
            if end - start < 20 or end - start > 70:
                continue
            result.append(
                {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "score": int(item.get("score", 50)),
                    "hook": str(item.get("hook", ""))[:80],
                    "title": str(item.get("title", "Untitled Clip"))[:60],
                }
            )
        except (TypeError, ValueError):
            continue

    # Sort by score descending
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:12]


async def score_moments(transcript: str) -> list[dict[str, Any]]:
    """Main entry point – routes to the configured provider."""
    settings = get_settings()
    provider = settings.ai_provider.lower()

    logger.info(f"Scoring moments with provider: {provider}")

    if provider == "local":
        return await score_with_ollama(transcript)
    elif provider == "openrouter":
        return await score_with_openrouter(transcript)
    else:
        # Fallback to local
        logger.warning(f"Unknown provider '{provider}', falling back to local")
        return await score_with_ollama(transcript)
