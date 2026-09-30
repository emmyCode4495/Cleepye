"""
Viral moment scoring with Ollama / OpenRouter / offline heuristic fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an expert short-form video editor for TikTok, YouTube Shorts, and Instagram Reels.

Given a transcript, identify the best 30-60 second moments that work as standalone viral clips.

Return ONLY a JSON array. Each item:
- start (float seconds)
- end (float seconds)
- score (0-100)
- hook (max 15 words)
- title (max 8 words)

Rules:
- Prefer emotional peaks, strong advice, surprises, clear hooks
- Clips between 25 and 65 seconds
- Avoid mid-sentence starts/ends when possible
- Return 5-12 candidates, ranked by score descending

Transcript:
{transcript}
"""

_HOOK_PATTERNS = [
    r"\b(secret|truth|nobody|never|always|must|should|stop|start|why|how to|what if)\b",
    r"\b(amazing|incredible|shocking|unbelievable|crazy|insane|powerful|important)\b",
    r"\b(lesson|advice|tip|hack|mistake|regret|learned|remember)\b",
    r"[?!]",
]


def score_heuristic(transcript: str, segments: list[dict] | None = None) -> list[dict[str, Any]]:
    if segments:
        candidates = []
        i = 0
        n = len(segments)
        while i < n:
            start = float(segments[i]["start"])
            text_parts = []
            j = i
            while j < n and float(segments[j]["end"]) - start < 55:
                text_parts.append(segments[j].get("text", ""))
                j += 1
            if j == i:
                j = i + 1
            end = float(segments[min(j - 1, n - 1)]["end"])
            duration = end - start
            if 25 <= duration <= 70:
                text = " ".join(text_parts).strip()
                candidates.append(
                    {
                        "start": round(start, 2),
                        "end": round(end, 2),
                        "score": _heuristic_score(text),
                        "hook": text[:80].replace("\n", " "),
                        "title": (text[:40] + "…") if len(text) > 40 else text or "Clip",
                    }
                )
            i = max(i + 1, j - 1)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:10]

    words = transcript.split()
    if len(words) < 40:
        return []
    total_secs = len(words) / 2.5
    candidates = []
    t = 0.0
    while t + 25 < total_secs:
        start_w = int(t * 2.5)
        end_w = int((t + 40) * 2.5)
        chunk = " ".join(words[start_w:end_w])
        candidates.append(
            {
                "start": round(t, 2),
                "end": round(t + 40, 2),
                "score": _heuristic_score(chunk),
                "hook": chunk[:80],
                "title": (chunk[:40] + "…") if len(chunk) > 40 else chunk,
            }
        )
        t += 25
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:10]


def _heuristic_score(text: str) -> int:
    if not text:
        return 30
    score = 40
    lower = text.lower()
    for pat in _HOOK_PATTERNS:
        score += len(re.findall(pat, lower, re.I)) * 6
    if len(text) < 220:
        score += 5
    if "?" in text or "!" in text:
        score += 8
    return min(95, max(25, score))


async def score_with_ollama(transcript: str) -> list[dict[str, Any]]:
    settings = get_settings()
    prompt = SCORING_PROMPT.format(transcript=transcript[:12000])
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
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
            raw = resp.json().get("response", "[]")
        parsed = _parse_scores(raw)
        if parsed:
            return parsed
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e}); using heuristic scoring")
    return score_heuristic(transcript)


async def score_with_openrouter(transcript: str) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY required when AI_PROVIDER=openrouter")
    prompt = SCORING_PROMPT.format(transcript=transcript[:14000])
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
    return _parse_scores(raw)


def _parse_scores(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return _normalize(data)
        if isinstance(data, dict) and "clips" in data:
            return _normalize(data["clips"])
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            return _normalize(json.loads(match.group(0)))
        except json.JSONDecodeError:
            pass
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
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:12]


async def score_moments(
    transcript: str,
    segments: list[dict] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    provider = settings.ai_provider.lower()
    logger.info(f"Scoring moments with provider: {provider}")

    if provider == "heuristic":
        return score_heuristic(transcript, segments)
    if provider == "local":
        return await score_with_ollama(transcript)
    if provider == "openrouter":
        try:
            out = await score_with_openrouter(transcript)
            return out or score_heuristic(transcript, segments)
        except Exception as e:
            logger.warning(f"OpenRouter failed ({e}); heuristic fallback")
            return score_heuristic(transcript, segments)
    logger.warning(f"Unknown provider '{provider}', using heuristic")
    return score_heuristic(transcript, segments)
