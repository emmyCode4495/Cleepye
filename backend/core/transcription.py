"""
Local transcription using faster-whisper.
Produces word-level timestamps essential for good captions and clip boundaries.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from backend.config import get_settings

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None


def get_whisper_model() -> WhisperModel:
    global _model
    if _model is None:
        settings = get_settings()
        device = settings.whisper_device
        compute_type = settings.whisper_compute_type

        if device == "auto":
            # Prefer CUDA only if the installed CTranslate2 actually supports it
            try:
                import ctranslate2
                if "cuda" in ctranslate2.get_supported_compute_types("cuda"):
                    device = "cuda"
                else:
                    device = "cpu"
            except Exception:
                device = "cpu"

        # On CPU, int8 is the best default. float16 is mainly for GPU.
        if device == "cpu" and compute_type in ("float16", "int8_float16"):
            compute_type = "int8"

        logger.info(
            f"Loading Whisper model '{settings.whisper_model}' "
            f"(device={device}, compute_type={compute_type})"
        )
        _model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
        )
    return _model


def transcribe(
    audio_or_video_path: str | Path,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Transcribe a video or audio file.
    Returns a structured result with segments and word-level timestamps.
    """
    path = Path(audio_or_video_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    model = get_whisper_model()

    logger.info(f"Transcribing: {path.name}")
    segments_gen, info = model.transcribe(
        str(path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )

    segments = []
    full_text_parts = []

    for seg in segments_gen:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    {
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3),
                    }
                )

        segment = {
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
        }
        segments.append(segment)
        full_text_parts.append(seg.text.strip())

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
    return result
