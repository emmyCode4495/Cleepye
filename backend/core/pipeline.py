"""
Main ClipMine pipeline:
1. Ingest (local file or URL)
2. Transcribe
3. Score viral moments
4. Reframe + cut + caption each selected clip
5. Export
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any

import yt_dlp

from backend.config import get_settings
from backend.core.transcription import transcribe
from backend.core.scoring import score_moments
from backend.core.reframe import compute_crop_boxes, build_ffmpeg_crop_filter
from backend.core.captions import write_ass_file
from backend.models.database import save_job_result

logger = logging.getLogger(__name__)


def download_video(url: str, output_dir: Path) -> Path:
    """Download a video with yt-dlp and return the local path."""
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
        # Ensure .mp4
        path = Path(filename)
        if path.suffix != ".mp4":
            mp4_path = path.with_suffix(".mp4")
            if mp4_path.exists():
                path = mp4_path
        return path


def get_video_info(path: Path) -> dict[str, Any]:
    """Get basic video metadata via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
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
) -> Path:
    """Cut a segment, reframe it, optionally burn captions."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = [crop_filter]
    if caption_ass and caption_ass.exists():
        # Escape path for FFmpeg
        ass_path = str(caption_ass).replace("\\", "/").replace(":", "\\:")
        filters.append(f"ass='{ass_path}'")

    vf = ",".join(filters)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info(f"Rendering clip: {output_path.name}")
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


async def process_video(
    source: str | Path,
    is_url: bool = False,
    max_clips: int = 8,
    caption_style: str = "viral",
) -> dict[str, Any]:
    """
    Full pipeline entry point.
    Returns a job result with paths to generated clips.
    """
    settings = get_settings()
    job_id = str(uuid.uuid4())[:8]
    job_dir = settings.storage_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[{job_id}] Starting job")

    # 1. Ingest
    if is_url:
        logger.info(f"[{job_id}] Downloading {source}")
        video_path = download_video(str(source), job_dir / "source")
    else:
        video_path = Path(source)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

    info = get_video_info(video_path)
    logger.info(f"[{job_id}] Video: {info['width']}x{info['height']}, {info['duration']:.1f}s")

    # 2. Transcribe
    transcript = transcribe(video_path)
    transcript_path = job_dir / "transcript.json"
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

    # 3. Score moments
    candidates = await score_moments(transcript["text"])
    logger.info(f"[{job_id}] Found {len(candidates)} candidate clips")

    # Limit
    selected = candidates[:max_clips]

    # 4. Compute reframe data (once for the whole video)
    crop_data = compute_crop_boxes(video_path)

    # 5. Render clips (with captions + per-clip crop)
    clips = []
    clips_dir = job_dir / "clips"
    captions_dir = job_dir / "captions"
    clips_dir.mkdir(exist_ok=True)
    captions_dir.mkdir(exist_ok=True)

    for i, cand in enumerate(selected, 1):
        out_name = f"clip_{i:02d}_{cand['score']}.mp4"
        out_path = clips_dir / out_name
        ass_path = captions_dir / f"clip_{i:02d}.ass"

        try:
            # Per-clip crop using only keyframes inside this window
            crop_filter = build_ffmpeg_crop_filter(
                crop_data,
                input_width=info["width"],
                input_height=info["height"],
                clip_start=cand["start"],
                clip_end=cand["end"],
            )

            # Generate word-level ASS captions for this clip window
            write_ass_file(
                segments=transcript["segments"],
                clip_start=cand["start"],
                clip_end=cand["end"],
                output_path=ass_path,
                style_name=caption_style,
            )

            cut_and_reframe(
                source=video_path,
                start=cand["start"],
                end=cand["end"],
                crop_filter=crop_filter,
                output_path=out_path,
                caption_ass=ass_path,
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

    # Save job summary to disk + database
    (job_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    try:
        source_type = "url" if is_url else "upload"
        save_job_result(result, source_type=source_type, source=str(source), caption_style=caption_style)
    except Exception as e:
        logger.warning(f"[{job_id}] Failed to save job to database: {e}")

    logger.info(f"[{job_id}] Done – {len(clips)} clips ready")
    return result
