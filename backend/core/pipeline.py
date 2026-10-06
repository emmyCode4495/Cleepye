"""
Main pipeline with progress callbacks for real-time UI updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from backend.config import get_settings
from backend.core.transcription import transcribe
from backend.core.scoring import score_moments
from backend.core.reframe import compute_crop_boxes_for_range, build_ffmpeg_crop_filter, resolve_aspect
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
    h = get_settings().max_download_height
    outtmpl = str(output_dir / "%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        # Clips top out at 1080 wide, so never pull 4K: much faster downloads.
        "format": (
            f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]/b"
        ),
        "merge_output_format": "mp4",
        "concurrent_fragment_downloads": 8,
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


def _parse_fps(raw: str) -> float:
    try:
        num, den = raw.split("/")
        return float(num) / float(den) if float(den) else 30.0
    except Exception:
        return 30.0


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
        "fps": _parse_fps(video_stream.get("r_frame_rate", "30/1")),
    }


@lru_cache(maxsize=1)
def pick_encoder() -> str:
    """Use a hardware H.264 encoder if one actually works, else libx264."""
    want = get_settings().video_encoder.strip()
    if want and want != "auto":
        return want
    for enc in ("h264_nvenc", "h264_videotoolbox"):
        try:
            r = subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
                 "-c:v", enc, "-f", "null", "-"],
                capture_output=True, timeout=15,
            )
            if r.returncode == 0:
                logger.info(f"Using hardware encoder: {enc}")
                return enc
        except Exception:
            continue
    return "libx264"


def render_worker_count() -> int:
    configured = get_settings().render_workers
    if configured > 0:
        return configured
    if pick_encoder() != "libx264":
        return 2  # GPUs allow a few concurrent encode sessions
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def _encoder_args(threads_per_job: int) -> list[str]:
    s = get_settings()
    enc = pick_encoder()
    if enc == "h264_nvenc":
        return ["-c:v", enc, "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-b:v", "8M"]
    if enc == "libx264":
        return ["-c:v", enc, "-preset", s.render_preset, "-crf", str(s.render_crf),
                "-threads", str(threads_per_job)]
    return ["-c:v", enc]


def cut_and_reframe(
    source: Path,
    start: float,
    end: float,
    crop_filter: str,
    output_path: Path,
    caption_ass: Path | None = None,
    fonts_dir: Path | None = None,
    threads: int = 0,
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
        "ffmpeg", "-y", "-v", "error", "-nostdin",
        "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",  # fast input seek
        "-i", str(source),
        "-vf", vf,
        *_encoder_args(threads or max(1, (os.cpu_count() or 2) // render_worker_count())),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    logger.info(f"Rendering clip: {output_path.name}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-500:]}")
    return output_path


_progress_lock = threading.Lock()


def _progress(job_id: str, stage: str, pct: float, message: str) -> None:
    with _progress_lock:
        _progress_unlocked(job_id, stage, pct, message)


def _progress_unlocked(job_id: str, stage: str, pct: float, message: str) -> None:
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
    min_clip_duration: float = 15,
    max_clip_duration: float = 60,
    aspect_ratio: str = "9:16",
    # Cleepye Clarity (optional AI enhancement)
    clarity_target: str = "none",  # none | source | clips | both
    clarity_preset: str = "standard",  # standard | sharp | ultra
) -> dict[str, Any]:
    settings = get_settings()
    job_id = job_id or str(uuid.uuid4())[:8]
    job_dir = settings.storage_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    source_type = "url" if is_url else "upload"
    create_job(job_id, source_type, str(source), caption_style)

    clarity_target = (clarity_target or "none").lower().strip()
    if clarity_target not in ("none", "source", "clips", "both"):
        clarity_target = "none"
    clarity_preset = (clarity_preset or settings.clarity_default_preset or "standard").lower().strip()

    try:
        # 1. Ingest
        _progress(job_id, "download", 5, "Preparing source video…")
        if is_url:
            _progress(job_id, "download", 8, "Downloading video…")
            video_path = await asyncio.to_thread(download_video, str(source), job_dir / "source")
        else:
            video_path = Path(source)
            if not video_path.exists():
                raise FileNotFoundError(video_path)

        info = await asyncio.to_thread(get_video_info, video_path)

        # Optional: enhance the full source before mining
        if clarity_target in ("source", "both"):
            from backend.services.enhance import clarity_available, enhance_video, ClarityError

            if not clarity_available():
                logger.warning(f"[{job_id}] Clarity requested but not configured — skipping source enhance")
            else:
                _ensure_not_cancelled(job_id)
                enhanced_src = job_dir / "source_clarity.mp4"

                def _src_progress(stage: str, pct: float, msg: str) -> None:
                    # Map 0–100 Clarity progress into ~16–22% of the job bar
                    mapped = 16 + (pct / 100.0) * 6
                    _progress(job_id, "clarity", mapped, msg)

                try:
                    video_path = await enhance_video(
                        video_path,
                        enhanced_src,
                        preset=clarity_preset,
                        progress=_src_progress,
                    )
                    info = await asyncio.to_thread(get_video_info, video_path)
                    _progress(
                        job_id, "clarity", 22,
                        f"Source enhanced with Clarity ({info['width']}x{info['height']})",
                    )
                except ClarityError as e:
                    logger.warning(f"[{job_id}] Source Clarity failed: {e} — continuing with original")
                    _progress(job_id, "download", 18, f"Clarity skipped: {e}")

        # Charge credits once duration is known (Supabase users only)
        if user_id:
            from backend.services.credits import (
                assert_can_start_job,
                charge_for_job,
                InsufficientCredits,
                PlanLimitExceeded,
            )
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
        def _tx_progress(frac: float) -> None:
            _progress(job_id, "transcribe", 20 + frac * 25, f"Transcribing audio… {frac * 100:.0f}%")

        transcript = await asyncio.to_thread(transcribe, video_path, None, _tx_progress)
        transcript_path = job_dir / "transcript.json"
        transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        _progress(job_id, "transcribe", 45, f"Transcript ready ({len(transcript['segments'])} segments)")

        # 3. Score
        _ensure_not_cancelled(job_id)
        _progress(job_id, "score", 50, "Finding viral moments…")
        min_d = max(5.0, float(min_clip_duration))
        max_d = max(min_d + 1.0, float(max_clip_duration))
        candidates = await score_moments(
            transcript["text"],
            segments=transcript.get("segments"),
            min_duration=min_d,
            max_duration=max_d,
            limit=max(max_clips * 2, max_clips),
        )
        selected = candidates[:max_clips]
        _progress(job_id, "score", 58, f"Found {len(candidates)} candidates, rendering top {len(selected)}")

        # 4. Face tracking — only for the selected clips, in parallel
        workers = render_worker_count()
        out_w, out_h = resolve_aspect(aspect_ratio)
        settings_ = get_settings()
        sem = asyncio.Semaphore(workers)
        cancelled = False
        done_count = 0

        _progress(job_id, "reframe", 62, f"Tracking faces in {len(selected)} clips…")

        async def track(cand: dict) -> list[dict]:
            async with sem:
                return await asyncio.to_thread(
                    compute_crop_boxes_for_range,
                    video_path, cand["start"], cand["end"],
                    info["width"], info["height"],
                    settings_.face_sample_fps, settings_.face_analysis_width,
                )

        crop_sets = await asyncio.gather(*(track(c) for c in selected))
        _ensure_not_cancelled(job_id)
        _progress(job_id, "reframe", 68, "Crop analysis complete")

        # 5. Render clips in parallel
        clips: list[dict] = []
        clips_dir = job_dir / "clips"
        captions_dir = job_dir / "captions"
        clips_dir.mkdir(exist_ok=True)
        captions_dir.mkdir(exist_ok=True)

        font_override = None
        fonts_dir_path = None
        if font_id:
            from backend.core.fonts import get_font_path, font_family_name, fonts_dir
            fp = get_font_path(font_id)
            if fp:
                font_override = font_family_name(fp)
                fonts_dir_path = fonts_dir()

        total = max(len(selected), 1)
        threads_per_job = max(1, (os.cpu_count() or 2) // workers)
        _progress(job_id, "render", 68, f"Rendering {len(selected)} clips ({workers} at a time)…")

        def render_sync(i: int, cand: dict, crop_data: list[dict]) -> dict:
            out_path = clips_dir / f"clip_{i:02d}_{cand['score']}.mp4"
            ass_path = captions_dir / f"clip_{i:02d}.ass"
            crop_filter = build_ffmpeg_crop_filter(
                crop_data,
                input_width=info["width"], input_height=info["height"],
                output_width=out_w, output_height=out_h,
                clip_start=cand["start"], clip_end=cand["end"],
            )
            write_ass_file(
                segments=transcript["segments"],
                clip_start=cand["start"], clip_end=cand["end"],
                output_path=ass_path, style_name=caption_style,
                font_override=font_override,
            )
            cut_and_reframe(
                source=video_path, start=cand["start"], end=cand["end"],
                crop_filter=crop_filter, output_path=out_path,
                caption_ass=ass_path, fonts_dir=fonts_dir_path,
                threads=threads_per_job,
            )
            return {
                "index": i, "path": str(out_path),
                "start": cand["start"], "end": cand["end"],
                "score": cand["score"], "title": cand["title"], "hook": cand["hook"],
                "duration": round(cand["end"] - cand["start"], 2),
                "caption_style": caption_style,
            }

        async def render(i: int, cand: dict, crop_data: list[dict]) -> None:
            nonlocal done_count, cancelled
            async with sem:
                if cancelled or is_job_cancelled(job_id):
                    cancelled = True
                    return
                try:
                    clip = await asyncio.to_thread(render_sync, i, cand, crop_data)
                    clips.append(clip)
                except Exception as e:
                    logger.error(f"[{job_id}] Failed to render clip {i}: {e}")
                done_count += 1
                _progress(job_id, "render", 68 + (done_count / total) * 28,
                          f"Rendered {done_count}/{len(selected)} clips…")

        await asyncio.gather(*(render(i, c, cs) for i, (c, cs) in enumerate(zip(selected, crop_sets), 1)))
        if cancelled:
            raise JobCancelled("Cancelled by user")
        clips.sort(key=lambda c: c["index"])

        # Optional: enhance each mined clip with Clarity
        if clarity_target in ("clips", "both") and clips:
            from backend.services.enhance import clarity_available, enhance_video, ClarityError

            if not clarity_available():
                logger.warning(f"[{job_id}] Clarity requested but not configured — skipping clip enhance")
            else:
                _ensure_not_cancelled(job_id)
                clarity_dir = job_dir / "clips_clarity"
                clarity_dir.mkdir(exist_ok=True)
                enhanced_clips: list[dict] = []
                n = len(clips)
                for idx, clip in enumerate(clips):
                    _ensure_not_cancelled(job_id)
                    src_clip = Path(clip["path"])
                    out_clip = clarity_dir / f"clip_{clip['index']:02d}_clarity.mp4"
                    base_pct = 96 + (idx / max(n, 1)) * 3

                    def _clip_progress(stage: str, pct: float, msg: str, _base=base_pct) -> None:
                        mapped = _base + (pct / 100.0) * (3 / max(n, 1))
                        _progress(job_id, "clarity", mapped, f"Clip {idx + 1}/{n}: {msg}")

                    try:
                        await enhance_video(
                            src_clip,
                            out_clip,
                            preset=clarity_preset,
                            progress=_clip_progress,
                        )
                        clip = {**clip, "path": str(out_clip), "clarity": clarity_preset}
                    except ClarityError as e:
                        logger.warning(f"[{job_id}] Clip {clip['index']} Clarity failed: {e}")
                        clip = {**clip, "clarity_error": str(e)}
                    enhanced_clips.append(clip)
                clips = enhanced_clips
                _progress(job_id, "clarity", 99, f"Clarity applied to {len(clips)} clips")

        result = {
            "job_id": job_id,
            "source": str(video_path),
            "duration": info["duration"],
            "transcript_path": str(transcript_path),
            "candidates_found": len(candidates),
            "clips_rendered": len(clips),
            "clips": clips,
            "clarity": {
                "target": clarity_target,
                "preset": clarity_preset if clarity_target != "none" else None,
            },
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
