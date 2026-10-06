"""
Cleepye API — async jobs, live progress, Supabase auth + credits.
"""

from __future__ import annotations

import asyncio

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.core.pipeline import process_video
from backend.core.captions import list_styles
from backend.core.fonts import list_fonts, save_font, delete_font
from backend.core.reframe import list_aspects
from backend.models.database import init_db, list_jobs, get_job, cancel_job
from backend.services.auth import AuthUser, optional_user, require_user
from backend.services.pricing import plans_public, packs_public, CREDIT_PACKS, credits_for_duration_seconds, credits_for_job, max_clips_for_plan
from backend.services.payments import (
    initiate_subscription_payment,
    PaymentError,
    verify_flutterwave_tx,
    flutterwave_hash_ok,
)
from backend.services.credits import activate_subscription
from backend.services.credits import get_profile, InsufficientCredits, PlanLimitExceeded
from backend.services.supabase_client import supabase_enabled

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("clipmine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    logger.info(f"Cleepye starting on {settings.host}:{settings.port}")
    logger.info(f"Data dir: {settings.data_dir.resolve()}")
    logger.info(f"AI provider: {settings.ai_provider}")
    logger.info(f"Supabase: {'enabled' if supabase_enabled() else 'disabled (local mode)'}")
    yield
    logger.info("Cleepye shutting down")


app = FastAPI(
    title="Cleepye",
    description="Privacy-first AI video clipper",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlRequest(BaseModel):
    url: str
    max_clips: int = Field(default=8, ge=1, le=20)
    caption_style: str = "viral"
    font_id: str | None = None
    min_clip_duration: float = Field(default=15, ge=5, le=120)
    max_clip_duration: float = Field(default=60, ge=10, le=180)
    aspect_ratio: str = "9:16"
    # Cleepye Clarity — none | source | clips | both
    clarity_target: str = "none"
    clarity_preset: str = "standard"


class EnhanceClipRequest(BaseModel):
    """Apply Clarity to an already-mined clip."""
    job_id: str
    clip_index: int = Field(ge=1)
    preset: str = "standard"


class ClarityUrlRequest(BaseModel):
    """Standalone Clarity — enhance a video from URL, no mining."""
    url: str
    preset: str = "standard"


class JobAccepted(BaseModel):
    job_id: str
    status: str
    message: str


_job_slots: asyncio.Semaphore | None = None


def _get_job_slots() -> asyncio.Semaphore:
    global _job_slots
    if _job_slots is None:
        _job_slots = asyncio.Semaphore(max(1, get_settings().max_concurrent_jobs))
    return _job_slots


async def _run_job(
    *,
    job_id: str,
    source: str | Path,
    is_url: bool,
    max_clips: int,
    caption_style: str,
    user_id: str | None,
    font_id: str | None = None,
    min_clip_duration: float = 15,
    max_clip_duration: float = 60,
    aspect_ratio: str = "9:16",
    clarity_target: str = "none",
    clarity_preset: str = "standard",
) -> None:
    try:
        async with _get_job_slots():  # honour MAX_CONCURRENT_JOBS
            await process_video(
                source=source,
                is_url=is_url,
                max_clips=max_clips,
                caption_style=caption_style,
                job_id=job_id,
                user_id=user_id,
                font_id=font_id,
                min_clip_duration=min_clip_duration,
                max_clip_duration=max_clip_duration,
                aspect_ratio=aspect_ratio,
                clarity_target=clarity_target,
                clarity_preset=clarity_preset,
            )
    except Exception:
        logger.exception(f"Background job {job_id} failed")


@app.get("/")
async def root():
    return {
        "name": "Cleepye",
        "version": "0.3.0",
        "status": "running",
        "supabase": supabase_enabled(),
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "supabase": supabase_enabled()}


@app.get("/api/styles")
async def get_styles():
    return {"styles": list_styles()}


@app.get("/api/aspects")
async def get_aspects():
    return {"aspects": list_aspects()}


@app.get("/api/clarity")
async def get_clarity_options():
    """Public Clarity options (Cleepye-branded). Available only when server has a key."""
    from backend.services.enhance import (
        clarity_available,
        list_clarity_presets,
        list_clarity_groups,
    )

    available = clarity_available()
    return {
        "available": available,
        "presets": list_clarity_presets("video") if available else [],
        "image_presets": list_clarity_presets("image") if available else [],
        "video_groups": list_clarity_groups("video") if available else [],
        "image_groups": list_clarity_groups("image") if available else [],
        "media_types": [
            {"id": "video", "name": "Video", "description": "Upscale, smooth motion, slow-mo, or SDR→HDR."},
            {"id": "image", "name": "Image", "description": "Upscale, denoise, restore, or portrait enhance."},
        ] if available else [],
        "targets": [
            {"id": "none", "name": "Off", "description": "No extra enhancement."},
            {"id": "source", "name": "Original video", "description": "Sharpen the full source before mining moments."},
            {"id": "clips", "name": "Mined clips", "description": "Enhance only the final short clips."},
            {"id": "both", "name": "Source + clips", "description": "Enhance the source and each mined clip."},
        ] if available else [],
        # Mine pipeline still uses standard|sharp|ultra aliases
        "default_preset": "precise" if available else None,
        "mine_presets": [
            {"id": "standard", "name": "Standard", "description": "Precise enhance (default)."},
            {"id": "sharp", "name": "Sharp", "description": "Stronger generative recovery."},
            {"id": "ultra", "name": "Ultra", "description": "Maximum detail + upscale."},
        ] if available else [],
    }


@app.get("/api/plans")
async def api_plans(request: Request, currency: str | None = None):
    from backend.services.geo import resolve_currency

    geo = await resolve_currency(request, override=currency)
    cur = geo["currency"]
    return {
        "plans": plans_public(cur),
        "packs": packs_public(cur),
        "currency": cur,
        "country": geo.get("country"),
        "currency_source": geo.get("source"),
        "supported_currencies": ["NGN", "USD"],
        "credit_rule": (
            "Mining credits: 1 credit = 1 source video mined. "
            "Clarity credits: used for enhance, upscale, slow-mo, HDR, and images. "
            "Free includes 1 mining credit only — no Clarity. "
            "Each paid plan includes both. "
            "Prices shown in your local currency (NGN in Nigeria, USD elsewhere)."
        ),
    }


@app.get("/api/me")
async def api_me(user: AuthUser = Depends(require_user)):
    if user.id == "local":
        return {
            "user": {"id": "local", "email": None},
            "profile": {
                "plan_id": "local",
                "credits_balance": None,
                "credits_monthly_allowance": None,
                "subscription_status": "local",
            },
            "plan_limits": {
                "plan_id": "local",
                "name": "Local",
                "max_clips_per_job": 20,
                "max_clips_ui": 20,
                "max_source_minutes": 240,
                "credits_per_month": None,
            },
            "auth_required": get_settings().auth_required,
            "supabase": False,
        }
    profile = await get_profile(user.id)
    from backend.services.pricing import get_plan, max_clips_for_plan
    plan_id = (profile or {}).get("plan_id") or "free"
    plan = get_plan(plan_id)
    return {
        "user": {"id": user.id, "email": user.email},
        "profile": profile,
        "plan_limits": {
            "plan_id": plan.id,
            "name": plan.name,
            "max_clips_per_job": plan.max_clips_per_job,
            "max_clips_ui": max_clips_for_plan(plan.id),
            "max_source_minutes": plan.max_source_minutes,
            "credits_per_month": plan.credits_per_month,
            "clarity_credits_per_month": getattr(plan, "clarity_credits_per_month", 0),
        },
        "auth_required": get_settings().auth_required,
        "supabase": True,
    }


@app.post("/api/process/url", response_model=JobAccepted)
async def process_from_url(
    req: UrlRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_user),
):
    settings = get_settings()
    if settings.auth_required and user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")

    if user.id != "local":
        try:
            from backend.services.credits import assert_can_start_job, get_profile
            profile = await get_profile(user.id)
            plan_id = (profile or {}).get("plan_id") or "free"
            req.max_clips = min(req.max_clips, max_clips_for_plan(plan_id))
            await assert_can_start_job(user.id, duration_sec=None, max_clips=req.max_clips)
        except InsufficientCredits as e:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits (need at least {e.needed}, have {e.balance}). Upgrade your plan or buy a pack.",
            )
        except PlanLimitExceeded as e:
            raise HTTPException(status_code=403, detail=str(e))

    job_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(
        _run_job,
        job_id=job_id,
        source=req.url,
        is_url=True,
        max_clips=req.max_clips,
        caption_style=req.caption_style,
        user_id=None if user.id == "local" else user.id,
        font_id=req.font_id,
        min_clip_duration=req.min_clip_duration,
        max_clip_duration=req.max_clip_duration,
        aspect_ratio=req.aspect_ratio,
        clarity_target=req.clarity_target,
        clarity_preset=req.clarity_preset,
    )
    return JobAccepted(
        job_id=job_id,
        status="running",
        message="Job started — poll /api/jobs/{job_id} for progress",
    )


@app.post("/api/process/upload", response_model=JobAccepted)
async def process_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_clips: int = Form(8),
    caption_style: str = Form("viral"),
    font_id: str | None = Form(None),
    min_clip_duration: float = Form(15),
    max_clip_duration: float = Form(60),
    aspect_ratio: str = Form("9:16"),
    clarity_target: str = Form("none"),
    clarity_preset: str = Form("standard"),
    user: AuthUser = Depends(require_user),
):
    settings = get_settings()
    if settings.auth_required and user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")

    if user.id != "local":
        try:
            from backend.services.credits import assert_can_start_job, get_profile
            profile = await get_profile(user.id)
            plan_id = (profile or {}).get("plan_id") or "free"
            max_clips = min(max_clips, max_clips_for_plan(plan_id))
            await assert_can_start_job(user.id, duration_sec=None, max_clips=max_clips)
        except InsufficientCredits as e:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits (need at least {e.needed}, have {e.balance}).",
            )
        except PlanLimitExceeded as e:
            raise HTTPException(status_code=403, detail=str(e))

    job_id = str(uuid.uuid4())[:8]
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    dest = settings.storage_dir / "temp" / f"{job_id}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())

    background_tasks.add_task(
        _run_job,
        job_id=job_id,
        source=dest,
        is_url=False,
        max_clips=max_clips,
        caption_style=caption_style,
        user_id=None if user.id == "local" else user.id,
        font_id=font_id,
        min_clip_duration=min_clip_duration,
        max_clip_duration=max_clip_duration,
        aspect_ratio=aspect_ratio,
        clarity_target=clarity_target,
        clarity_preset=clarity_preset,
    )
    return JobAccepted(
        job_id=job_id,
        status="running",
        message="Job started — poll /api/jobs/{job_id} for progress",
    )


@app.post("/api/clarity/url", response_model=JobAccepted)
async def clarity_from_url(
    req: ClarityUrlRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_user),
):
    """Enhance a video from URL with Cleepye Clarity only (no mining)."""
    from backend.services.enhance import clarity_available, process_clarity_only

    if not clarity_available():
        raise HTTPException(status_code=503, detail="Clarity is not configured on this server.")

    settings = get_settings()
    if settings.auth_required and user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")

    if user.id != "local":
        try:
            from backend.services.credits import assert_can_start_job
            await assert_can_start_job(user.id, duration_sec=None, max_clips=1)
        except InsufficientCredits as e:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits (need at least {e.needed}, have {e.balance}).",
            )
        except PlanLimitExceeded as e:
            raise HTTPException(status_code=403, detail=str(e))

    job_id = str(uuid.uuid4())[:8]

    async def _run() -> None:
        try:
            async with _get_job_slots():
                await process_clarity_only(
                    source=req.url,
                    is_url=True,
                    job_id=job_id,
                    preset=req.preset or "standard",
                    user_id=None if user.id == "local" else user.id,
                )
        except Exception:
            logger.exception(f"Clarity job {job_id} failed")

    background_tasks.add_task(_run)
    return JobAccepted(
        job_id=job_id,
        status="running",
        message="Clarity started — poll /api/jobs/{job_id} for progress",
    )


@app.post("/api/clarity/upload", response_model=JobAccepted)
async def clarity_from_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    preset: str = Form("standard"),
    media: str = Form("video"),  # video | image
    user: AuthUser = Depends(require_user),
):
    """Enhance an uploaded video or image with Cleepye Clarity only (no mining)."""
    from backend.services.enhance import clarity_available, process_clarity_only, process_clarity_image

    if not clarity_available():
        raise HTTPException(status_code=503, detail="Clarity is not configured on this server.")

    settings = get_settings()
    if settings.auth_required and user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")

    if user.id != "local":
        try:
            from backend.services.credits import assert_can_start_job
            await assert_can_start_job(user.id, duration_sec=None, max_clips=1)
        except InsufficientCredits as e:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits (need at least {e.needed}, have {e.balance}).",
            )
        except PlanLimitExceeded as e:
            raise HTTPException(status_code=403, detail=str(e))

    media_type = (media or "video").lower().strip()
    if media_type not in ("video", "image"):
        media_type = "video"

    job_id = str(uuid.uuid4())[:8]
    name = file.filename or ("image.jpg" if media_type == "image" else "video.mp4")
    suffix = Path(name).suffix or (".jpg" if media_type == "image" else ".mp4")
    dest = settings.storage_dir / "temp" / f"{job_id}_clarity{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())

    async def _run() -> None:
        try:
            async with _get_job_slots():
                uid = None if user.id == "local" else user.id
                if media_type == "image":
                    await process_clarity_image(
                        source=dest,
                        job_id=job_id,
                        preset=preset or "standard",
                        user_id=uid,
                    )
                else:
                    await process_clarity_only(
                        source=dest,
                        is_url=False,
                        job_id=job_id,
                        preset=preset or "standard",
                        user_id=uid,
                    )
        except Exception:
            logger.exception(f"Clarity job {job_id} failed")

    background_tasks.add_task(_run)
    return JobAccepted(
        job_id=job_id,
        status="running",
        message="Clarity started — poll /api/jobs/{job_id} for progress",
    )


@app.post("/api/clarity/enhance-clip")
async def api_enhance_clip(
    req: EnhanceClipRequest,
    user: AuthUser = Depends(require_user),
):
    """
    Apply Cleepye Clarity to one already-mined clip.
    Replaces the clip file in place (keeps a .orig backup).
    """
    from backend.services.enhance import clarity_available, enhance_video, ClarityError

    if not clarity_available():
        raise HTTPException(status_code=503, detail="Clarity is not configured on this server.")

    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = job.get("result") or {}
    clips = result.get("clips") or []
    clip = next((c for c in clips if int(c.get("index", -1)) == req.clip_index), None)
    if not clip:
        raise HTTPException(status_code=404, detail=f"Clip {req.clip_index} not found on this job")

    path = Path(clip["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file missing on disk")

    backup = path.with_suffix(path.suffix + ".orig")
    if not backup.exists():
        backup.write_bytes(path.read_bytes())

    out_tmp = path.with_name(path.stem + "_clarity_tmp.mp4")
    try:
        await enhance_video(path if not backup.exists() else backup, out_tmp, preset=req.preset)
        out_tmp.replace(path)
    except ClarityError as e:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
        logger.exception("Clarity enhance-clip failed")
        raise HTTPException(status_code=502, detail=f"Clarity failed: {e}")

    # Update stored result so UI picks up the enhanced path metadata
    clip["clarity"] = req.preset
    clip["path"] = str(path)
    for i, c in enumerate(clips):
        if int(c.get("index", -1)) == req.clip_index:
            clips[i] = clip
            break
    result["clips"] = clips
    job_dir = get_settings().storage_dir / "jobs" / req.job_id
    (job_dir / "result.json").write_text(
        __import__("json").dumps(result, indent=2), encoding="utf-8"
    )
    try:
        from backend.models.database import save_job_result
        save_job_result(
            {**result, "job_id": req.job_id},
            source_type=job.get("source_type") or "upload",
            source=job.get("source") or "",
            caption_style=job.get("caption_style") or "viral",
        )
    except Exception:
        logger.warning("Could not persist clarity result to DB", exc_info=True)

    return {"ok": True, "clip_index": req.clip_index, "preset": req.preset, "path": str(path)}


@app.get("/api/fonts")
async def api_list_fonts():
    return {"fonts": list_fonts()}


@app.post("/api/fonts")
async def api_upload_font(file: UploadFile = File(...)):
    data = await file.read()
    try:
        meta = save_font(file.filename or "font.ttf", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return meta


@app.delete("/api/fonts/{font_id}")
async def api_delete_font(font_id: str):
    if not delete_font(font_id):
        raise HTTPException(status_code=404, detail="Font not found")
    return {"ok": True, "id": font_id}


@app.get("/api/jobs")
async def api_list_jobs(limit: int = 50):
    return {"jobs": list_jobs(limit=limit)}


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        return {
            "id": job_id,
            "status": "running",
            "stage": "queued",
            "progress": 0,
            "message": "Starting…",
            "clips": [],
            "candidates_found": 0,
            "clips_rendered": 0,
            "source": "",
            "duration": None,
            "caption_style": "viral",
        }
    return job


@app.post("/api/jobs/{job_id}/cancel")
async def api_cancel_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") in ("completed", "failed", "cancelled"):
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "message": f"Job already {job.get('status')}",
        }
    if not cancel_job(job_id):
        raise HTTPException(status_code=400, detail="Could not cancel job")
    return {"job_id": job_id, "status": "cancelled", "message": "Cancel requested"}


@app.get("/api/clips/{job_id}/{filename}")
async def get_clip(job_id: str, filename: str):
    settings = get_settings()
    path = settings.storage_dir / "jobs" / job_id / "clips" / filename
    if not path.exists():
        # also allow clips_clarity folder
        alt = settings.storage_dir / "jobs" / job_id / "clips_clarity" / filename
        if alt.exists():
            path = alt
        else:
            raise HTTPException(status_code=404, detail="Clip not found")
    suffix = path.suffix.lower()
    media = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=filename)


@app.get("/api/credits/estimate")
async def estimate_credits(duration_sec: float = 0):
    return {
        "duration_sec": duration_sec,
        "credits": credits_for_job(),
        "rule": "1 credit per mining job",
    }


class SubscribeRequest(BaseModel):
    plan_id: str
    redirect_url: str | None = None
    currency: str | None = None


@app.post("/api/billing/subscribe")
async def api_subscribe(
    req: SubscribeRequest,
    request: Request,
    user: AuthUser = Depends(require_user),
):
    """Start subscription checkout (Flutterwave → Paystack → Korapay)."""
    if user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required to subscribe")
    settings = get_settings()
    redirect = req.redirect_url or settings.payment_redirect_url
    email = user.email or "user@cleepye.local"
    from backend.services.geo import resolve_currency
    geo = await resolve_currency(request, override=req.currency)
    try:
        result = await initiate_subscription_payment(
            plan_id=req.plan_id,
            email=email,
            user_id=user.id,
            redirect_url=redirect,
            currency=geo["currency"],
        )
        return result
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))




@app.post("/api/billing/webhook/flutterwave")
async def flutterwave_webhook(request: Request):
    """
    Flutterwave sends charge events here.
    Dashboard → Settings → Webhooks → URL:
      https://YOUR_API/api/billing/webhook/flutterwave
    Secret hash → FLUTTERWAVE_SECRET_HASH env.
    """
    verif = request.headers.get("verif-hash") or request.headers.get("Verif-Hash")
    if not flutterwave_hash_ok(verif):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    body = await request.json()
    event = (body.get("event") or body.get("type") or "").lower()
    data = body.get("data") or {}
    status = (data.get("status") or "").lower()

    # Accept successful charges
    if status not in ("successful", "success") and "success" not in event:
        return {"ok": True, "ignored": True, "reason": f"status={status} event={event}"}

    tx_ref = data.get("tx_ref") or data.get("txRef") or ""
    if not tx_ref:
        raise HTTPException(status_code=400, detail="Missing tx_ref")

    # Prefer live verify
    try:
        verified = await verify_flutterwave_tx(tx_ref)
    except PaymentError as e:
        logger.warning(f"Flutterwave verify failed for {tx_ref}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    v_status = (verified.get("status") or "").lower()
    if v_status not in ("successful", "success"):
        return {"ok": True, "ignored": True, "reason": f"verify status={v_status}"}

    meta = verified.get("meta") or data.get("meta") or {}
    if isinstance(meta, str):
        import json as _json
        try:
            meta = _json.loads(meta)
        except Exception:
            meta = {}

    user_id = meta.get("user_id") or meta.get("userId")
    plan_id = meta.get("plan_id") or meta.get("planId")
    if not user_id or not plan_id:
        # Fallback: parse tx_ref cleepye_{plan}_{user8}_{rand}
        parts = tx_ref.split("_")
        if len(parts) >= 3 and parts[0] == "cleepye":
            plan_id = plan_id or parts[1]
        logger.error(f"Webhook missing meta user/plan tx_ref={tx_ref} meta={meta}")
        raise HTTPException(status_code=400, detail="Missing user_id or plan_id in payment meta")

    amount = verified.get("amount")
    try:
        amount_i = int(float(amount)) if amount is not None else None
    except (TypeError, ValueError):
        amount_i = None

    try:
        result = await activate_subscription(
            str(user_id),
            plan_id=str(plan_id),
            tx_ref=tx_ref,
            provider="flutterwave",
            amount_ngn=amount_i,
        )
    except PermissionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("activate_subscription failed")
        raise HTTPException(status_code=500, detail="Could not grant credits")

    return {"ok": True, **result}


@app.get("/api/billing/confirm")
async def billing_confirm(tx_ref: str, user: AuthUser = Depends(require_user)):
    """
    Optional: after redirect from Flutterwave (?tx_ref=...), frontend can call this
    to confirm and grant credits if webhook was delayed.
    """
    if user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        verified = await verify_flutterwave_tx(tx_ref)
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if (verified.get("status") or "").lower() not in ("successful", "success"):
        raise HTTPException(status_code=400, detail="Payment not successful yet")
    meta = verified.get("meta") or {}
    if isinstance(meta, str):
        import json as _json
        try:
            meta = _json.loads(meta)
        except Exception:
            meta = {}
    plan_id = meta.get("plan_id") or "starter"
    user_id = meta.get("user_id") or user.id
    if str(user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="Payment does not belong to this user")
    amount = verified.get("amount")
    try:
        amount_i = int(float(amount)) if amount is not None else None
    except (TypeError, ValueError):
        amount_i = None
    result = await activate_subscription(
        user.id,
        plan_id=str(plan_id),
        tx_ref=tx_ref,
        provider="flutterwave",
        amount_ngn=amount_i,
    )
    return result


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)
