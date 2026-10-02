"""
Viral moment scoring with Ollama / OpenRouter / offline heuristic fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an expert short-form video editor for TikTok, YouTube Shorts, and Instagram Reels.

Given a transcript where every line starts with its start time like [123s], identify the best 30-60 second moments that work as standalone viral clips.

Return ONLY a JSON array. Each item:
- start (float seconds, taken from the [Ns] markers)
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


def score_heuristic(
    transcript: str,
    segments: list[dict] | None = None,
    min_duration: float = 25.0,
    max_duration: float = 60.0,
) -> list[dict[str, Any]]:
    """Sliding window over segments. O(n) windows, each scored by regex only."""
    if segments:
        candidates = []
        n = len(segments)
        j = 0
        for i in range(n):
            start = float(segments[i]["start"])
            j = max(j, i)
            # grow window right while it still fits max_duration
            while j < n and float(segments[j]["end"]) - start <= max_duration:
                j += 1
            if j == i:  # single segment longer than max_duration
                continue
            end = float(segments[j - 1]["end"])
            duration = end - start
            if duration < min_duration:
                continue
            text = " ".join(seg.get("text", "") for seg in segments[i:j]).strip()
            candidates.append(
                {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "score": _heuristic_score(text),
                    "hook": text[:80].replace("\n", " "),
                    "title": (text[:40] + "…") if len(text) > 40 else text or "Clip",
                }
            )
        return select_non_overlapping(candidates, limit=40)

    words = transcript.split()
    if len(words) < 40:
        return []
    win = (min_duration + max_duration) / 2
    total_secs = len(words) / 2.5
    candidates = []
    t = 0.0
    while t + min_duration < total_secs:
        chunk = " ".join(words[int(t * 2.5): int((t + win) * 2.5)])
        candidates.append(
            {
                "start": round(t, 2),
                "end": round(t + win, 2),
                "score": _heuristic_score(chunk),
                "hook": chunk[:80],
                "title": (chunk[:40] + "…") if len(chunk) > 40 else chunk,
            }
        )
        t += win * 0.6
    return select_non_overlapping(candidates, limit=40)


def select_non_overlapping(
    candidates: list[dict[str, Any]], limit: int, max_overlap: float = 0.25
) -> list[dict[str, Any]]:
    """Greedy best-score-first pick that drops near-duplicate / overlapping windows."""
    picked: list[dict[str, Any]] = []
    for c in sorted(candidates, key=lambda x: x["score"], reverse=True):
        dur = max(c["end"] - c["start"], 0.001)
        ok = True
        for p in picked:
            overlap = min(c["end"], p["end"]) - max(c["start"], p["start"])
            if overlap > 0 and overlap / dur > max_overlap:
                ok = False
                break
        if ok:
            picked.append(c)
            if len(picked) >= limit:
                break
    return picked


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
            raw = resp.json().get("response", "[]")
        return _parse_scores(raw)
    except Exception as e:
        logger.warning(f"Ollama unavailable ({e})")
        return []


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


def _normalize(items: list, lo: float = 15.0, hi: float = 75.0) -> list[dict[str, Any]]:
    result = []
    for item in items:
        try:
            start = float(item.get("start", 0))
            end = float(item.get("end", 0))
            if end - start < lo or end - start > hi:
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
        except (TypeError, ValueError, AttributeError):
            continue
    return result


def _timestamped_chunks(segments: list[dict], max_chars: int = 11000) -> list[str]:
    """
    Turn segments into '[123s] text' lines and split into LLM-sized chunks so a
    long video is fully covered (the old code only ever sent the first ~12k chars,
    and without timestamps the model could not return real start/end times).
    """
    chunks: list[str] = []
    cur: list[str] = []
    size = 0
    for seg in segments:
        line = f"[{int(float(seg['start']))}s] {seg.get('text', '').strip()}"
        if size + len(line) > max_chars and cur:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


async def _score_chunks(fn, chunks: list[str], concurrency: int) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(concurrency)

    async def one(chunk: str) -> list[dict[str, Any]]:
        async with sem:
            try:
                return await fn(chunk)
            except Exception as e:
                logger.warning(f"Chunk scoring failed ({e})")
                return []

    results = await asyncio.gather(*(one(c) for c in chunks))
    return [item for sub in results for item in sub]


async def score_moments(
    transcript: str,
    segments: list[dict] | None = None,
    min_duration: float = 25.0,
    max_duration: float = 60.0,
    limit: int = 10,
) -> list[dict[str, Any]]:
    settings = get_settings()
    provider = settings.ai_provider.lower()
    logger.info(f"Scoring moments with provider: {provider}")

    def heuristic() -> list[dict[str, Any]]:
        return score_heuristic(transcript, segments, min_duration, max_duration)

    if provider in ("local", "openrouter") and segments:
        chunks = _timestamped_chunks(segments)
        fn = score_with_ollama if provider == "local" else score_with_openrouter
        # Local LLMs are GPU/CPU bound -> 1 at a time; hosted APIs -> parallel
        found = await _score_chunks(fn, chunks, concurrency=1 if provider == "local" else 4)
        found = [
            c for c in found
            if min_duration * 0.8 <= c["end"] - c["start"] <= max_duration * 1.2
        ]
        picked = select_non_overlapping(found, limit)
        return picked or select_non_overlapping(heuristic(), limit)

    if provider not in ("heuristic", "local", "openrouter"):
        logger.warning(f"Unknown provider '{provider}', using heuristic")

    return select_non_overlapping(heuristic(), limit)
