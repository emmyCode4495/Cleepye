"""
ClipMine API server
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import get_settings
from backend.core.pipeline import process_video
from backend.models.database import init_db, list_jobs, get_job

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("clipmine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    logger.info(f"ClipMine starting on {settings.host}:{settings.port}")
    logger.info(f"Data dir: {settings.data_dir.resolve()}")
    logger.info(f"AI provider: {settings.ai_provider}")
    yield
    logger.info("ClipMine shutting down")


app = FastAPI(
    title="ClipMine",
    description="Privacy-first AI video clipper – mine viral nuggets from long videos",
    version="0.1.0",
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
    max_clips: int = 8
    caption_style: str = "viral"


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str
    result: dict | None = None


@app.get("/")
async def root():
    return {
        "name": "ClipMine",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/styles")
async def get_styles():
    """List available caption styles."""
    from backend.core.captions import list_styles
    return {"styles": list_styles()}


@app.post("/api/process/url", response_model=JobResponse)
async def process_from_url(req: UrlRequest):
    """Process a video from a URL (YouTube, etc.)."""
    try:
        result = await process_video(
            source=req.url,
            is_url=True,
            max_clips=req.max_clips,
            caption_style=req.caption_style,
        )
        return JobResponse(
            job_id=result["job_id"],
            status="completed",
            message=f"Rendered {result['clips_rendered']} clips",
            result=result,
        )
    except Exception as e:
        logger.exception("URL processing failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process/upload", response_model=JobResponse)
async def process_from_upload(
    file: UploadFile = File(...),
    max_clips: int = Form(8),
    caption_style: str = Form("viral"),
):
    """Process an uploaded local video file."""
    settings = get_settings()
    temp_path = settings.storage_dir / "temp" / f"upload_{file.filename}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        result = await process_video(
            source=temp_path,
            is_url=False,
            max_clips=max_clips,
            caption_style=caption_style,
        )
        return JobResponse(
            job_id=result["job_id"],
            status="completed",
            message=f"Rendered {result['clips_rendered']} clips",
            result=result,
        )
    except Exception as e:
        logger.exception("Upload processing failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.get("/api/jobs")
async def api_list_jobs(limit: int = 50):
    """List recent mining jobs (history)."""
    return {"jobs": list_jobs(limit=limit)}


@app.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    """Get details + clips for a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/clips/{job_id}/{filename}")
async def get_clip(job_id: str, filename: str):
    """Download a generated clip."""
    settings = get_settings()
    path = settings.storage_dir / "jobs" / job_id / "clips" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
