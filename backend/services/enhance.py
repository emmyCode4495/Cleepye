"""
Cleepye Clarity — AI video enhancement (powered by Topaz Labs underneath).

Public product name: "Clarity"
Internal provider: Topaz Video API

Users never see the Topaz name. All options live under the Cleepye umbrella.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Literal

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, float, str], None]

# ---------------------------------------------------------------------------
# Video workflows (Cleepye names → Topaz model ids)
# ---------------------------------------------------------------------------
CLARITY_VIDEO_WORKFLOWS: dict[str, dict[str, Any]] = {
    "precise": {
        "id": "precise",
        "name": "Precise Upscale",
        "description": "Clean upscale that preserves the original look. Best for real camera footage.",
        "group": "upscale",
        "model": "prob-4",
        "kind": "upscale",
        "target_height": 1080,
    },
    "creative": {
        "id": "creative",
        "name": "Creative Upscale",
        "description": "Adds new detail and texture. Great for AI-generated or flat footage.",
        "group": "upscale",
        "model": "ast-2",
        "kind": "upscale",
        "target_height": 1080,
    },
    "sharp": {
        "id": "sharp",
        "name": "Sharp Restore",
        "description": "Strong generative recovery for soft, compressed, or low-res video.",
        "group": "upscale",
        "model": "slf-3",
        "kind": "upscale",
        "target_height": None,
    },
    "ultra": {
        "id": "ultra",
        "name": "Ultra Precise",
        "description": "Maximum detail recovery and upscale. Best for archival or very soft sources.",
        "group": "upscale",
        "model": "slp-2",
        "kind": "upscale",
        "target_height": 1080,
    },
    "smooth": {
        "id": "smooth",
        "name": "Smoother Motion",
        "description": "Raise frame rate with AI interpolation for smoother playback (e.g. 24→60).",
        "group": "motion",
        "model": "apo-8",
        "kind": "interpolate",
        "slowmo": 1,
        "target_fps": 60,
    },
    "slowmo_2x": {
        "id": "slowmo_2x",
        "name": "Slow Motion 2×",
        "description": "Smooth half-speed slow motion with interpolated frames.",
        "group": "motion",
        "model": "apo-8",
        "kind": "interpolate",
        "slowmo": 2,
        "target_fps": None,
    },
    "slowmo_4x": {
        "id": "slowmo_4x",
        "name": "Slow Motion 4×",
        "description": "Quarter-speed cinematic slow motion.",
        "group": "motion",
        "model": "apo-8",
        "kind": "interpolate",
        "slowmo": 4,
        "target_fps": None,
    },
    "slowmo_8x": {
        "id": "slowmo_8x",
        "name": "Slow Motion 8×",
        "description": "Extreme slow motion for dramatic moments.",
        "group": "motion",
        "model": "apo-8",
        "kind": "interpolate",
        "slowmo": 8,
        "target_fps": None,
    },
    "hdr": {
        "id": "hdr",
        "name": "SDR → HDR",
        "description": "Convert standard dynamic range footage to HDR with richer contrast.",
        "group": "color",
        "model": "hyp-2",
        "kind": "hdr",
        "target_height": None,
    },
}

# Backward-compatible aliases used by mine pipeline / older UI
CLARITY_PRESETS: dict[str, dict[str, Any]] = {
    "standard": {**CLARITY_VIDEO_WORKFLOWS["precise"], "id": "standard", "name": "Standard"},
    "sharp": CLARITY_VIDEO_WORKFLOWS["sharp"],
    "ultra": CLARITY_VIDEO_WORKFLOWS["ultra"],
    **{k: v for k, v in CLARITY_VIDEO_WORKFLOWS.items()},
}

# ---------------------------------------------------------------------------
# Image workflows
# ---------------------------------------------------------------------------
CLARITY_IMAGE_WORKFLOWS: dict[str, dict[str, Any]] = {
    "wonder": {
        "id": "wonder",
        "name": "Wonder",
        "description": "Latest all-in-one enhance — detail, texture, and patterns.",
        "group": "enhance",
        "model": "Wonder 3",
        "output_scale": 2,
    },
    "bloom": {
        "id": "bloom",
        "name": "Bloom",
        "description": "Creative detail for AI-generated images, with richer texture.",
        "group": "enhance",
        "model": "Bloom",
        "output_scale": 2,
    },
    "standard": {
        "id": "standard",
        "name": "Standard Upscale",
        "description": "Clean, reliable upscaling that stays true to the original.",
        "group": "upscale",
        "model": "Standard V2",
        "output_scale": 2,
    },
    "denoise": {
        "id": "denoise",
        "name": "Denoise Max",
        "description": "Remove heavy noise while recovering covered detail.",
        "group": "cleanup",
        "model": "Denoise Max",
        "output_scale": 1,
    },
    "portrait": {
        "id": "portrait",
        "name": "Portrait",
        "description": "Face-focused recovery for portraits and people shots.",
        "group": "enhance",
        "model": "Recover Faces",
        "output_scale": 2,
    },
    "restore": {
        "id": "restore",
        "name": "Photo Restore",
        "description": "Recover old or damaged photos.",
        "group": "cleanup",
        "model": "Recover 3",
        "output_scale": 2,
    },
    "high_fidelity": {
        "id": "high_fidelity",
        "name": "High Fidelity",
        "description": "Maximum source preservation with clean sharpening.",
        "group": "upscale",
        "model": "High Fidelity V2",
        "output_scale": 2,
    },
    "low_res": {
        "id": "low_res",
        "name": "Low-Res Boost",
        "description": "4× upscale for very small or heavily degraded images.",
        "group": "upscale",
        "model": "Low Resolution V2",
        "output_scale": 4,
    },
}

CLARITY_IMAGE_PRESETS = CLARITY_IMAGE_WORKFLOWS

EnhanceTarget = Literal["none", "source", "clips", "both"]


def list_clarity_presets(media: str = "video") -> list[dict[str, Any]]:
    """Public list for UI (no internal model ids)."""
    source = CLARITY_IMAGE_WORKFLOWS if media == "image" else CLARITY_VIDEO_WORKFLOWS
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "group": p.get("group", "upscale"),
        }
        for p in source.values()
    ]


def list_clarity_groups(media: str = "video") -> list[dict[str, str]]:
    if media == "image":
        return [
            {"id": "enhance", "name": "Enhance"},
            {"id": "upscale", "name": "Upscale"},
            {"id": "cleanup", "name": "Cleanup"},
        ]
    return [
        {"id": "upscale", "name": "Upscale & restore"},
        {"id": "motion", "name": "Motion"},
        {"id": "color", "name": "Color"},
    ]


def clarity_available() -> bool:
    key = (get_settings().topaz_api_key or "").strip()
    return bool(key)


class ClarityError(Exception):
    """User-facing enhancement failure."""


def _headers() -> dict[str, str]:
    key = (get_settings().topaz_api_key or "").strip()
    if not key:
        raise ClarityError("Clarity is not configured. Add TOPAZ_API_KEY in your server environment.")
    return {
        "X-API-Key": key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _probe_local(path: Path) -> dict[str, Any]:
    """Reuse ffprobe-style info without importing pipeline to avoid cycles."""
    import json
    import subprocess

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_raw = video.get("r_frame_rate", "30/1")
    try:
        n, d = fps_raw.split("/")
        fps = float(n) / float(d) if float(d) else 30.0
    except Exception:
        fps = 30.0
    duration = float(data["format"]["duration"])
    width = int(video["width"])
    height = int(video["height"])
    frame_count = int(round(duration * fps))
    size = path.stat().st_size
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "fps": fps,
        "frame_count": frame_count,
        "size": size,
        "container": path.suffix.lstrip(".").lower() or "mp4",
    }


def _resolve_video_workflow(preset_id: str) -> dict[str, Any]:
    pid = (preset_id or "precise").lower().strip()
    # aliases
    aliases = {
        "standard": "precise",
        "precise_upscale": "precise",
        "creative_upscale": "creative",
        "frame_interpolation": "smooth",
        "interpolate": "smooth",
        "slow_motion": "slowmo_2x",
        "slowmo": "slowmo_2x",
        "sdr_to_hdr": "hdr",
        "sdr-hdr": "hdr",
    }
    pid = aliases.get(pid, pid)
    return CLARITY_VIDEO_WORKFLOWS.get(pid) or CLARITY_VIDEO_WORKFLOWS["precise"]


def _build_filters(preset_id: str, src: dict[str, Any]) -> list[dict[str, Any]]:
    wf = _resolve_video_workflow(preset_id)
    kind = wf.get("kind", "upscale")
    model = wf["model"]

    if kind == "interpolate":
        slowmo = int(wf.get("slowmo") or 1)
        target_fps = wf.get("target_fps")
        src_fps = float(src.get("fps") or 30)
        fps = float(target_fps) if target_fps else max(src_fps, src_fps * slowmo)
        return [
            {
                "model": model,
                "slowmo": slowmo,
                "fps": fps,
                "duplicate": True,
                "duplicateThreshold": 0.1,
            }
        ]

    if kind == "hdr":
        return [
            {
                "model": model,
            }
        ]

    # upscale / enhance
    return [
        {
            "model": model,
            "videoType": "Progressive",
            "auto": "Auto",
        }
    ]


def _output_resolution(preset_id: str, src: dict[str, Any]) -> dict[str, int]:
    wf = _resolve_video_workflow(preset_id)
    # Motion / HDR keep source resolution
    if wf.get("kind") in ("interpolate", "hdr"):
        return {"width": src["width"], "height": src["height"]}
    target_h = wf.get("target_height")
    if not target_h or target_h <= src["height"]:
        return {"width": src["width"], "height": src["height"]}
    scale = target_h / src["height"]
    w = int(round(src["width"] * scale / 2) * 2)
    return {"width": w, "height": int(target_h)}


def _output_frame_rate(preset_id: str, src: dict[str, Any]) -> float:
    wf = _resolve_video_workflow(preset_id)
    src_fps = float(src.get("fps") or 30)
    if wf.get("kind") != "interpolate":
        return src_fps
    slowmo = int(wf.get("slowmo") or 1)
    target_fps = wf.get("target_fps")
    if target_fps:
        return float(target_fps)
    return max(src_fps, src_fps * slowmo)


async def enhance_video(
    input_path: Path,
    output_path: Path,
    *,
    preset: str = "standard",
    progress: ProgressCb | None = None,
    poll_interval: float = 4.0,
    timeout_sec: float = 1800.0,
) -> Path:
    """
    Enhance a single local video file via the Topaz Video API.
    Returns the path to the enhanced file (written to output_path).
    """
    if not input_path.exists():
        raise ClarityError(f"Input video not found: {input_path}")

    if not clarity_available():
        raise ClarityError("Clarity is not configured on this server.")

    src = _probe_local(input_path)
    headers = _headers()
    base = "https://api.topazlabs.com/video"

    def _p(stage: str, pct: float, msg: str) -> None:
        if progress:
            progress(stage, pct, msg)
        logger.info(f"Clarity [{preset}] {stage} {pct:.0f}% — {msg}")

    _p("clarity", 2, "Preparing Clarity request…")

    create_body = {
        "source": {
            "resolution": {"width": src["width"], "height": src["height"]},
            "container": src["container"] if src["container"] in ("mp4", "mov", "mkv") else "mp4",
            "size": src["size"],
            "duration": src["duration"],
            "frameRate": src["fps"],
            "frameCount": src["frame_count"],
        },
        "output": {
            "resolution": _output_resolution(preset, src),
            "audioCodec": "AAC",
            "audioTransfer": "Copy",
            "frameRate": _output_frame_rate(preset, src),
            "dynamicCompressionLevel": "High",
            "container": "mp4",
        },
        "filters": _build_filters(preset, src),
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        # 1) Create request (free estimate)
        r = await client.post(f"{base}/", headers=headers, json=create_body)
        if r.status_code >= 400:
            logger.error(f"Clarity create failed: {r.status_code} {r.text[:500]}")
            raise ClarityError(_friendly_api_error(r))
        created = r.json()
        request_id = (
            created.get("requestId")
            or created.get("id")
            or created.get("request_id")
        )
        if not request_id:
            logger.error(f"Clarity create response missing id: {created}")
            raise ClarityError("Clarity could not start the enhancement job.")

        _p("clarity", 8, "Reserving processing…")

        # 2) Accept → get upload URL(s)
        r = await client.patch(f"{base}/{request_id}/accept", headers=headers)
        if r.status_code >= 400:
            logger.error(f"Clarity accept failed: {r.status_code} {r.text[:500]}")
            raise ClarityError(_friendly_api_error(r))
        accepted = r.json()

        upload_urls = (
            accepted.get("uploadUrls")
            or accepted.get("urls")
            or accepted.get("upload_urls")
            or []
        )
        # Some responses return a single url field
        single = accepted.get("uploadUrl") or accepted.get("url")
        if single and not upload_urls:
            upload_urls = [single]
        if isinstance(upload_urls, dict):
            upload_urls = list(upload_urls.values())

        if not upload_urls:
            # Try nested locations common in S3-style responses
            for key in ("data", "result", "uploads"):
                nested = accepted.get(key)
                if isinstance(nested, list) and nested:
                    upload_urls = nested
                    break
                if isinstance(nested, dict):
                    u = nested.get("url") or nested.get("uploadUrl")
                    if u:
                        upload_urls = [u]
                        break

        if not upload_urls:
            logger.error(f"Clarity accept missing upload URL: {accepted}")
            raise ClarityError("Clarity could not prepare the upload.")

        upload_url = upload_urls[0] if isinstance(upload_urls[0], str) else (
            upload_urls[0].get("url") or upload_urls[0].get("uploadUrl")
        )
        if not upload_url:
            raise ClarityError("Clarity returned an invalid upload target.")

        _p("clarity", 15, "Uploading video for Clarity…")

        # 3) PUT the file
        file_bytes = input_path.read_bytes()
        put_headers = {"Content-Type": "video/mp4"}
        put = await client.put(upload_url, content=file_bytes, headers=put_headers)
        if put.status_code >= 400:
            logger.error(f"Clarity upload failed: {put.status_code} {put.text[:300]}")
            raise ClarityError("Clarity upload failed. Please try again.")

        etag = put.headers.get("ETag") or put.headers.get("etag") or "1"
        etag = etag.strip('"')

        _p("clarity", 35, "Starting Clarity processing…")

        # 4) Complete upload
        complete_body = {
            "uploadResults": [{"partNum": 1, "eTag": etag}],
        }
        r = await client.patch(
            f"{base}/{request_id}/complete-upload",
            headers=headers,
            json=complete_body,
        )
        if r.status_code >= 400:
            logger.error(f"Clarity complete-upload failed: {r.status_code} {r.text[:500]}")
            raise ClarityError(_friendly_api_error(r))

        # 5) Poll status
        started = time.monotonic()
        download_url: str | None = None
        last_pct = 40.0

        while True:
            if time.monotonic() - started > timeout_sec:
                raise ClarityError("Clarity timed out. Try a shorter clip or try again later.")

            await _async_sleep(poll_interval)
            r = await client.get(f"{base}/{request_id}/status", headers=headers)
            if r.status_code >= 400:
                logger.warning(f"Clarity status poll error: {r.status_code}")
                continue

            status_body = r.json()
            status = (
                (status_body.get("status") or status_body.get("state") or "")
                .lower()
            )
            # Progress hints if present
            prog = status_body.get("progress") or status_body.get("percent")
            if isinstance(prog, (int, float)):
                last_pct = 40 + min(55, float(prog) * 0.55)
            else:
                last_pct = min(94, last_pct + 2)

            _p("clarity", last_pct, f"Clarity processing… ({status or 'running'})")

            if status in ("completed", "complete", "done", "success", "succeeded"):
                download_url = (
                    status_body.get("downloadUrl")
                    or status_body.get("download_url")
                    or status_body.get("outputUrl")
                    or status_body.get("url")
                )
                # Nested
                if not download_url:
                    for key in ("result", "output", "data"):
                        nested = status_body.get(key) or {}
                        if isinstance(nested, dict):
                            download_url = (
                                nested.get("downloadUrl")
                                or nested.get("url")
                                or nested.get("download_url")
                            )
                            if download_url:
                                break
                break

            if status in ("failed", "error", "cancelled", "canceled"):
                msg = status_body.get("message") or status_body.get("error") or "Processing failed"
                raise ClarityError(f"Clarity failed: {msg}")

        if not download_url:
            raise ClarityError("Clarity finished but no download link was returned.")

        _p("clarity", 96, "Downloading enhanced video…")
        out = await client.get(download_url, follow_redirects=True)
        if out.status_code >= 400:
            raise ClarityError("Could not download the enhanced video.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(out.content)
        _p("clarity", 100, "Clarity complete")
        return output_path


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


def _friendly_api_error(r: httpx.Response) -> str:
    try:
        body = r.json()
        msg = body.get("message") or body.get("error") or body.get("detail")
        if msg:
            return f"Clarity error: {msg}"
    except Exception:
        pass
    if r.status_code == 401:
        return "Clarity API key is invalid or missing."
    if r.status_code == 402 or r.status_code == 403:
        return "Clarity credits are exhausted or access is denied."
    if r.status_code == 429:
        return "Clarity is busy. Please try again in a moment."
    return f"Clarity request failed (HTTP {r.status_code})."


# ---------------------------------------------------------------------------
# Standalone Clarity job (enhance only — no mining)
# ---------------------------------------------------------------------------

async def process_clarity_only(
    source: str | Path,
    *,
    is_url: bool = False,
    job_id: str | None = None,
    preset: str = "standard",
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Run Cleepye Clarity on a single video without mining.
    Produces one enhanced output under jobs/{id}/clips/.
    """
    import asyncio
    import json
    import uuid

    from backend.core.pipeline import download_video, get_video_info, JobCancelled, _ensure_not_cancelled, _progress
    from backend.models.database import create_job, save_job_result, mark_job_failed

    settings = get_settings()
    job_id = job_id or str(uuid.uuid4())[:8]
    job_dir = settings.storage_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    source_type = "clarity_url" if is_url else "clarity_upload"
    create_job(job_id, source_type, str(source), caption_style="clarity")

    try:
        if not clarity_available():
            raise ClarityError("Clarity is not configured on this server.")

        _progress(job_id, "download", 5, "Preparing video for Clarity…")

        if is_url:
            _progress(job_id, "download", 10, "Downloading video…")
            video_path = await asyncio.to_thread(download_video, str(source), job_dir / "source")
        else:
            video_path = Path(source)
            if not video_path.exists():
                raise FileNotFoundError(video_path)

        _ensure_not_cancelled(job_id)
        info = await asyncio.to_thread(get_video_info, video_path)
        _progress(
            job_id, "download", 20,
            f"Source ready ({info['width']}x{info['height']}, {info['duration']:.0f}s)",
        )

        # Optional credit charge (same as a mine for now — can be tuned later)
        if user_id:
            try:
                from backend.services.credits import (
                    assert_can_start_job,
                    charge_for_job,
                    InsufficientCredits,
                    PlanLimitExceeded,
                )
                await assert_can_start_job(user_id, duration_sec=info["duration"], max_clips=1)
                charge = await charge_for_job(user_id, duration_sec=info["duration"], job_id=job_id)
                _progress(
                    job_id, "download", 25,
                    f"Charged {charge['charged']} credits (balance {charge['balance']})",
                )
            except InsufficientCredits as e:
                mark_job_failed(job_id, f"Insufficient credits: need {e.needed}, have {e.balance}")
                raise
            except PlanLimitExceeded as e:
                mark_job_failed(job_id, str(e))
                raise

        out_path = clips_dir / f"clarity_{preset}.mp4"

        def _p(stage: str, pct: float, msg: str) -> None:
            # Map Clarity 0–100 into job bar 25–98
            mapped = 25 + (pct / 100.0) * 73
            _progress(job_id, "clarity", mapped, msg)

        _ensure_not_cancelled(job_id)
        await enhance_video(video_path, out_path, preset=preset, progress=_p)

        result = {
            "job_id": job_id,
            "source": str(video_path),
            "duration": info["duration"],
            "transcript_path": None,
            "candidates_found": 0,
            "clips_rendered": 1,
            "mode": "clarity",
            "clarity": {"target": "video", "preset": preset},
            "clips": [
                {
                    "index": 1,
                    "path": str(out_path),
                    "start": 0.0,
                    "end": info["duration"],
                    "score": 100,
                    "title": "Clarity enhanced",
                    "hook": f"Enhanced with Cleepye Clarity · {preset}",
                    "duration": round(info["duration"], 2),
                    "caption_style": "clarity",
                    "clarity": preset,
                }
            ],
        }
        (job_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        save_job_result(result, source_type=source_type, source=str(source), caption_style="clarity")
        _progress(job_id, "done", 100, "Clarity complete — video ready")
        return result

    except JobCancelled:
        logger.info(f"[{job_id}] Clarity job cancelled")
        return {"job_id": job_id, "status": "cancelled", "clips": [], "clips_rendered": 0, "candidates_found": 0}
    except Exception as e:
        logger.exception(f"[{job_id}] Clarity job failed")
        mark_job_failed(job_id, str(e))
        raise


async def enhance_image(
    input_path: Path,
    output_path: Path,
    *,
    preset: str = "standard",
    progress: ProgressCb | None = None,
    poll_interval: float = 2.0,
    timeout_sec: float = 600.0,
) -> Path:
    """Enhance a still image via Topaz Image API (async enhance + poll + download)."""
    if not input_path.exists():
        raise ClarityError(f"Input image not found: {input_path}")
    if not clarity_available():
        raise ClarityError("Clarity is not configured on this server.")

    preset_cfg = CLARITY_IMAGE_WORKFLOWS.get(preset) or CLARITY_IMAGE_WORKFLOWS.get("standard") or list(CLARITY_IMAGE_WORKFLOWS.values())[0]
    model = preset_cfg["model"]
    scale = int(preset_cfg.get("output_scale") or 2)

    def _p(stage: str, pct: float, msg: str) -> None:
        if progress:
            progress(stage, pct, msg)
        logger.info(f"Clarity image [{preset}] {stage} {pct:.0f}% — {msg}")

    _p("clarity", 5, "Uploading image for Clarity…")

    # Probe size for optional output dimensions
    try:
        from PIL import Image
        with Image.open(input_path) as im:
            w, h = im.size
    except Exception:
        w, h = 0, 0

    out_h = h * scale if h else None
    out_w = w * scale if w else None

    headers = {
        "X-API-Key": (get_settings().topaz_api_key or "").strip(),
        "Accept": "application/json",
    }
    base = "https://api.topazlabs.com/image/v1"

    import asyncio

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        # multipart upload
        files = {
            "image": (input_path.name, input_path.read_bytes(), _image_mime(input_path)),
        }
        data: dict[str, Any] = {
            "model": model,
            "output_format": "jpeg",
        }
        if out_h and out_w:
            data["output_height"] = str(out_h)
            data["output_width"] = str(out_w)

        r = await client.post(f"{base}/enhance/async", headers=headers, data=data, files=files)
        if r.status_code >= 400:
            logger.error(f"Clarity image create failed: {r.status_code} {r.text[:500]}")
            raise ClarityError(_friendly_api_error(r))
        body = r.json()
        process_id = body.get("process_id") or body.get("processId") or r.headers.get("X-Process-ID")
        if not process_id:
            logger.error(f"Clarity image missing process_id: {body}")
            raise ClarityError("Clarity could not start the image job.")

        _p("clarity", 25, "Clarity processing image…")
        started = time.monotonic()
        last = 30.0
        while True:
            if time.monotonic() - started > timeout_sec:
                raise ClarityError("Clarity image timed out.")
            await asyncio.sleep(poll_interval)
            st = await client.get(f"{base}/status/{process_id}", headers=headers)
            if st.status_code >= 400:
                continue
            sj = st.json()
            status = (sj.get("status") or "").lower()
            last = min(90, last + 3)
            _p("clarity", last, f"Clarity processing… ({status or 'running'})")
            if status in ("completed", "complete", "done", "success"):
                break
            if status in ("failed", "error", "cancelled", "canceled"):
                raise ClarityError(f"Clarity failed: {sj.get('message') or status}")

        _p("clarity", 92, "Downloading enhanced image…")
        dl = await client.get(f"{base}/download/{process_id}", headers=headers)
        if dl.status_code >= 400:
            # some APIs return the file directly on download; try output url
            raise ClarityError("Could not download the enhanced image.")
        try:
            dj = dl.json()
            url = dj.get("url") or dj.get("download_url") or dj.get("downloadUrl")
            if url:
                img = await client.get(url, follow_redirects=True)
                content = img.content
            else:
                content = dl.content
        except Exception:
            content = dl.content

        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Prefer jpeg extension
        if output_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            output_path = output_path.with_suffix(".jpg")
        output_path.write_bytes(content)
        _p("clarity", 100, "Clarity complete")
        return output_path


def _image_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")


async def process_clarity_image(
    source: Path,
    *,
    job_id: str | None = None,
    preset: str = "standard",
    user_id: str | None = None,
) -> dict[str, Any]:
    """Standalone Clarity for a still image (no mining)."""
    import asyncio
    import json
    import uuid

    from backend.models.database import create_job, save_job_result, mark_job_failed
    from backend.core.pipeline import _progress, JobCancelled, _ensure_not_cancelled

    settings = get_settings()
    job_id = job_id or str(uuid.uuid4())[:8]
    job_dir = settings.storage_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(exist_ok=True)

    create_job(job_id, "clarity_image", str(source), caption_style="clarity")

    try:
        if not clarity_available():
            raise ClarityError("Clarity is not configured on this server.")
        if not source.exists():
            raise FileNotFoundError(source)

        _progress(job_id, "download", 10, "Preparing image for Clarity…")
        _ensure_not_cancelled(job_id)

        if user_id:
            try:
                from backend.services.credits import assert_can_start_job, charge_for_job, InsufficientCredits, PlanLimitExceeded
                await assert_can_start_job(user_id, duration_sec=0, max_clips=1)
                charge = await charge_for_job(user_id, duration_sec=0, job_id=job_id)
                _progress(job_id, "download", 15, f"Charged {charge['charged']} credits (balance {charge['balance']})")
            except InsufficientCredits as e:
                mark_job_failed(job_id, f"Insufficient credits: need {e.needed}, have {e.balance}")
                raise
            except PlanLimitExceeded as e:
                mark_job_failed(job_id, str(e))
                raise

        out_path = clips_dir / f"clarity_{preset}.jpg"

        def _p(stage: str, pct: float, msg: str) -> None:
            mapped = 20 + (pct / 100.0) * 75
            _progress(job_id, "clarity", mapped, msg)

        await enhance_image(source, out_path, preset=preset, progress=_p)

        result = {
            "job_id": job_id,
            "source": str(source),
            "duration": 0,
            "transcript_path": None,
            "candidates_found": 0,
            "clips_rendered": 1,
            "mode": "clarity_image",
            "clarity": {"target": "image", "preset": preset},
            "clips": [
                {
                    "index": 1,
                    "path": str(out_path),
                    "start": 0.0,
                    "end": 0.0,
                    "score": 100,
                    "title": "Clarity enhanced image",
                    "hook": f"Enhanced with Cleepye Clarity · {preset}",
                    "duration": 0,
                    "caption_style": "clarity",
                    "clarity": preset,
                }
            ],
        }
        (job_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        save_job_result(result, source_type="clarity_image", source=str(source), caption_style="clarity")
        _progress(job_id, "done", 100, "Clarity complete — image ready")
        return result
    except JobCancelled:
        return {"job_id": job_id, "status": "cancelled", "clips": [], "clips_rendered": 0, "candidates_found": 0}
    except Exception as e:
        logger.exception(f"[{job_id}] Clarity image job failed")
        mark_job_failed(job_id, str(e))
        raise
