"""
Local transcription using faster-whisper.

Speed notes:
- Uses BatchedInferencePipeline when available (several x faster, esp. on GPU).
- Greedy decoding (beam_size=1) by default; barely affects caption/scoring quality.
- condition_on_previous_text=False avoids slow repetition loops on long videos.
- Transcripts are cached on disk, so re-mining the same video skips this stage.
- Reports progress while running so the UI never looks frozen.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from faster_whisper import WhisperModel

try:  # faster-whisper >= 1.1.0
    from faster_whisper import BatchedInferencePipeline
except Exception:  # pragma: no cover
    BatchedInferencePipeline = None  # type: ignore

from backend.config import get_settings

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None
_batched: Any = None
_device: str = "cpu"

# progress_cb(fraction 0..1)
TranscribeProgress = Callable[[float], None]


def _resolve_device() -> tuple[str, str]:
    settings = get_settings()
    device = settings.whisper_device
    compute_type = settings.whisper_compute_type

    if device == "auto":
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"

    if device == "cuda" and compute_type == "int8":
        compute_type = "float16"  # fastest on GPU
    if device == "cpu" and compute_type in ("float16", "int8_float16"):
        compute_type = "int8"
    return device, compute_type


def get_whisper_model() -> WhisperModel:
    global _model, _batched, _device
    if _model is None:
        settings = get_settings()
        device, compute_type = _resolve_device()
        _device = device
        logger.info(
            f"Loading Whisper model '{settings.whisper_model}' "
            f"(device={device}, compute_type={compute_type})"
        )
        _model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
            cpu_threads=os.cpu_count() or 4 if device == "cpu" else 0,
        )
        if BatchedInferencePipeline is not None:
            _batched = BatchedInferencePipeline(model=_model)
    return _model


# ---------------------------------------------------------------- cache ----

def _cache_path(path: Path, language: str | None) -> Path:
    settings = get_settings()
    st = path.stat()
    key = f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}|{settings.whisper_model}|{language}"
    digest = hashlib.sha1(key.encode()).hexdigest()[:20]
    return settings.storage_dir / "transcripts" / f"{digest}.json"


def _load_cache(path: Path, language: str | None) -> dict[str, Any] | None:
    if not get_settings().cache_transcripts:
        return None
    try:
        cp = _cache_path(path, language)
        if cp.exists():
            return json.loads(cp.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"Transcript cache read failed: {e}")
    return None


def _save_cache(path: Path, language: str | None, result: dict[str, Any]) -> None:
    if not get_settings().cache_transcripts:
        return
    try:
        _cache_path(path, language).write_text(json.dumps(result), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Transcript cache write failed: {e}")



def _extract_audio(path: Path) -> Path:
    """Decode to 16 kHz mono WAV with ffmpeg so faster-whisper never has to
    open the video through PyAV (avoids PyAV/faster-whisper version clashes)."""
    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    out = Path(name)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(path),
         "-vn", "-ac", "1", "-ar", "16000", str(out)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        out.unlink(missing_ok=True)
        raise RuntimeError(f"Audio extraction failed: {r.stderr[-300:]}")
    return out


# ------------------------------------------------------------ transcribe ----

def transcribe(
    audio_or_video_path: str | Path,
    language: str | None = None,
    on_progress: TranscribeProgress | None = None,
) -> dict[str, Any]:
    path = Path(audio_or_video_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    cached = _load_cache(path, language)
    if cached:
        logger.info(f"Transcript cache hit for {path.name}")
        if on_progress:
            on_progress(1.0)
        return cached

    settings = get_settings()
    model = get_whisper_model()
    logger.info(f"Transcribing: {path.name}")

    kwargs: dict[str, Any] = dict(
        language=language,
        word_timestamps=True,  # needed for animated captions
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=max(1, settings.whisper_beam_size),
        condition_on_previous_text=False,
    )

    audio_path = _extract_audio(path)
    try:
        if _batched is not None:
            segments_gen, info = _batched.transcribe(
                str(audio_path), batch_size=settings.whisper_batch_size, **kwargs
            )
        else:
            segments_gen, info = model.transcribe(str(audio_path), **kwargs)

        total = max(float(info.duration or 0.0), 1.0)
        segments: list[dict[str, Any]] = []
        full_text_parts: list[str] = []
        last_report = 0.0

        for seg in segments_gen:
            words = [
                {
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": round(w.probability, 3),
                }
                for w in (seg.words or [])
            ]
            text = seg.text.strip()
            segments.append(
                {
                    "id": len(segments),
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "text": text,
                    "words": words,
                }
            )
            full_text_parts.append(text)

            frac = min(seg.end / total, 1.0)
            if on_progress and frac - last_report >= 0.02:  # throttle to ~50 updates
                last_report = frac
                on_progress(frac)
    finally:
        audio_path.unlink(missing_ok=True)

    result = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(info.duration, 3),
        "text": " ".join(full_text_parts),
        "segments": segments,
    }
    logger.info(
        f"Transcription complete: {len(segments)} segments, "
        f"language={result['language']}, duration={result['duration']}s"
    )
    _save_cache(path, language, result)
    if on_progress:
        on_progress(1.0)
    return result