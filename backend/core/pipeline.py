"""
Main pipeline with progress callbacks for real-time UI updates.
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from backend.config import get_settings
from backend.core.transcription import transcribe
from backend.core.scoring import score_moments
from backend.core.reframe import compute_crop_boxes, build_ffmpeg_crop_filter
from backend.core.captions import write_ass_file
from backend.models.database import (
    create_job,
    update_job_progress,
    save_job_result,
    mark_job_failed,
    is_job_cancelled,
)

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, float, str], None]


class JobCancelled(Exception):
    """Raised when the user cancels a running job."""


def _ensure_not_cancelled(job_id: str) -> None:
    if is_job_cancelled(job_id):
        raise JobCancelled("Cancelled by user")




def download_video(url: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        path = Path(filename)
        if path.suffix != ".mp4":
            mp4_path = path.with_suffix(".mp4")
            if mp4_path.exists():
                path = mp4_path
        return path


def get_video_info(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "duration": float(data["format"]["duration"]),
        "fps": eval(video_stream.get("r_frame_rate", "30/1")),
    }


def cut_and_reframe(
    source: Path,
    start: float,
    end: float,
    crop_filter: str,
    output_path: Path,
    caption_ass: Path | None = None,
    fonts_dir: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filters = [crop_filter]
    if caption_ass and caption_ass.exists():
        ass_path = str(caption_ass).replace("\\", "/").replace(":", "\\:")
        if fonts_dir and fonts_dir.is_dir():
            fd = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
            filters.append(f"ass='{ass_path}:fontsdir={fd}'")
        else:
            filters.append(f"ass='{ass_path}'")
    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-to", str(end),
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info(f"Rendering clip: {output_path.name}")
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _progress(job_id: str, stage: str, pct: float, message: str) -> None:
    update_job_progress(job_id, stage=stage, progress=pct, message=message, status="running")
    logger.info(f"[{job_id}] {stage} {pct:.0f}% — {message}")


async def process_video(
    source: str | Path,
    is_url: bool = False,
    max_clips: int = 8,
    caption_style: str = "viral",
    job_id: str | None = None,
    user_id: str | None = None,
    font_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    job_id = job_id or str(uuid.uuid4())[:8]
    job_dir = settings.storage_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    source_type = "url" if is_url else "upload"
    create_job(job_id, source_type, str(source), caption_style)

    try:
        # 1. Ingest
        _progress(job_id, "download", 5, "Preparing source video…")
        if is_url:
            _progress(job_id, "download", 8, "Downloading video…")
            video_path = download_video(str(source), job_dir / "source")
        else:
            video_path = Path(source)
            if not video_path.exists():
                raise FileNotFoundError(video_path)

        info = get_video_info(video_path)

        # Charge credits once duration is known (Supabase users only)
        if user_id:
            from backend.services.credits import (
                assert_can_start_job,
                charge_for_job,
                InsufficientCredits,
                PlanLimitExceeded,
            )
            from backend.models.database import mark_job_failed
            try:
                await assert_can_start_job(
                    user_id, duration_sec=info["duration"], max_clips=max_clips
                )
                charge = await charge_for_job(
                    user_id, duration_sec=info["duration"], job_id=job_id
                )
                _progress(
                    job_id,
                    "download",
                    18,
                    f"Charged {charge['charged']} credits (balance {charge['balance']})",
                )
            except InsufficientCredits as e:
                mark_job_failed(job_id, f"Insufficient credits: need {e.needed}, have {e.balance}")
                raise
            except PlanLimitExceeded as e:
                mark_job_failed(job_id, str(e))
                raise

        _progress(
            job_id, "download", 15,
            f"Source ready ({info['width']}x{info['height']}, {info['duration']:.0f}s)",
        )

        # 2. Transcribe
        _ensure_not_cancelled(job_id)
        _progress(job_id, "transcribe", 20, "Transcribing audio (this can take a while)…")
        transcript = transcribe(video_path)
        transcript_path = job_dir / "transcript.json"
        transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        _progress(job_id, "transcribe", 45, f"Transcript ready ({len(transcript['segments'])} segments)")

        # 3. Score
        _ensure_not_cancelled(job_id)
        _progress(job_id, "score", 50, "Finding viral moments…")
        candidates = await score_moments(
            transcript["text"],
            segments=transcript.get("segments"),
        )
        selected = candidates[:max_clips]
        _progress(job_id, "score", 58, f"Found {len(candidates)} candidates, rendering top {len(selected)}")

        # 4. Face tracking
        _progress(job_id, "reframe", 62, "Analyzing faces for vertical crop…")
        crop_data = compute_crop_boxes(video_path)
        _progress(job_id, "reframe", 68, "Crop analysis complete")

        # 5. Render clips
        clips = []
        clips_dir = job_dir / "clips"
        captions_dir = job_dir / "captions"
        clips_dir.mkdir(exist_ok=True)
        captions_dir.mkdir(exist_ok=True)

        total = max(len(selected), 1)
        for i, cand in enumerate(selected, 1):
            _ensure_not_cancelled(job_id)
            pct = 68 + (i / total) * 28
            _progress(job_id, "render", pct, f"Rendering clip {i}/{len(selected)}…")

            out_name = f"clip_{i:02d}_{cand['score']}.mp4"
            out_path = clips_dir / out_name
            ass_path = captions_dir / f"clip_{i:02d}.ass"

            try:
                crop_filter = build_ffmpeg_crop_filter(
                    crop_data,
                    input_width=info["width"],
                    input_height=info["height"],
                    clip_start=cand["start"],
                    clip_end=cand["end"],
                )
                font_override = None
                fonts_dir_path = None
                if font_id:
                    from backend.core.fonts import get_font_path, font_family_name, fonts_dir
                    fp = get_font_path(font_id)
                    if fp:
                        font_override = font_family_name(fp)
                        fonts_dir_path = fonts_dir()
                write_ass_file(
                    segments=transcript["segments"],
                    clip_start=cand["start"],
                    clip_end=cand["end"],
                    output_path=ass_path,
                    style_name=caption_style,
                    font_override=font_override,
                )
                cut_and_reframe(
                    source=video_path,
                    start=cand["start"],
                    end=cand["end"],
                    crop_filter=crop_filter,
                    output_path=out_path,
                    caption_ass=ass_path,
                    fonts_dir=fonts_dir_path,
                )
                clips.append(
                    {
                        "index": i,
                        "path": str(out_path),
                        "start": cand["start"],
                        "end": cand["end"],
                        "score": cand["score"],
                        "title": cand["title"],
                        "hook": cand["hook"],
                        "duration": round(cand["end"] - cand["start"], 2),
                        "caption_style": caption_style,
                    }
                )
            except Exception as e:
                logger.error(f"[{job_id}] Failed to render clip {i}: {e}")

        result = {
            "job_id": job_id,
            "source": str(video_path),
            "duration": info["duration"],
            "transcript_path": str(transcript_path),
            "candidates_found": len(candidates),
            "clips_rendered": len(clips),
            "clips": clips,
        }
        (job_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        save_job_result(result, source_type=source_type, source=str(source), caption_style=caption_style)
        _progress(job_id, "done", 100, f"Done — {len(clips)} clips ready")
        return result

    except JobCancelled:
        logger.info(f"[{job_id}] Job cancelled by user")
        return {"job_id": job_id, "status": "cancelled", "clips": [], "clips_rendered": 0, "candidates_found": 0}
    except Exception as e:
        logger.exception(f"[{job_id}] Job failed")
        mark_job_failed(job_id, str(e))
        raise
