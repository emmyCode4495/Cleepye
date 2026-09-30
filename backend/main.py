"""
Cleepye API — async jobs, live progress, Supabase auth + credits.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.core.pipeline import process_video
from backend.core.captions import list_styles
from backend.core.fonts import list_fonts, save_font, delete_font
from backend.models.database import init_db, list_jobs, get_job, cancel_job
from backend.services.auth import AuthUser, optional_user, require_user
from backend.services.pricing import plans_public, CREDIT_PACKS, credits_for_duration_seconds, credits_for_job
from backend.services.payments import initiate_subscription_payment, PaymentError
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


class JobAccepted(BaseModel):
    job_id: str
    status: str
    message: str


async def _run_job(
    *,
    job_id: str,
    source: str | Path,
    is_url: bool,
    max_clips: int,
    caption_style: str,
    user_id: str | None,
    font_id: str | None = None,
) -> None:
    try:
        await process_video(
            source=source,
            is_url=is_url,
            max_clips=max_clips,
            caption_style=caption_style,
            job_id=job_id,
            user_id=user_id,
            font_id=font_id,
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


@app.get("/api/plans")
async def api_plans():
    return {"plans": plans_public(), "packs": CREDIT_PACKS, "currency": "NGN", "credit_rule": "1 credit = 1 mining job (one source video). Retries may be free per plan."}


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
            "auth_required": get_settings().auth_required,
            "supabase": False,
        }
    profile = await get_profile(user.id)
    return {
        "user": {"id": user.id, "email": user.email},
        "profile": profile,
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
            from backend.services.credits import assert_can_start_job
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
    user: AuthUser = Depends(require_user),
):
    settings = get_settings()
    if settings.auth_required and user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required")

    if user.id != "local":
        try:
            from backend.services.credits import assert_can_start_job
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
    )
    return JobAccepted(
        job_id=job_id,
        status="running",
        message="Job started — poll /api/jobs/{job_id} for progress",
    )


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
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)


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


@app.post("/api/billing/subscribe")
async def api_subscribe(req: SubscribeRequest, user: AuthUser = Depends(require_user)):
    """Start subscription checkout (Flutterwave → Paystack → Korapay)."""
    if user.id == "local":
        raise HTTPException(status_code=401, detail="Sign in required to subscribe")
    settings = get_settings()
    redirect = req.redirect_url or settings.payment_redirect_url
    email = user.email or "user@cleepye.local"
    try:
        result = await initiate_subscription_payment(
            plan_id=req.plan_id,
            email=email,
            user_id=user.id,
            redirect_url=redirect,
        )
        return result
    except PaymentError as e:
        raise HTTPException(status_code=502, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)
