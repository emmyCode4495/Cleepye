"""
Custom caption fonts — user-uploaded TTF/OTF stored under data/fonts.
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_EXT = {".ttf", ".otf", ".ttc"}
MAX_FONT_BYTES = 8 * 1024 * 1024  # 8 MB


def fonts_dir() -> Path:
    settings = get_settings()
    d = Path(settings.data_dir) / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE).strip("_")
    return (stem or "font")[:60]


def list_fonts() -> list[dict[str, Any]]:
    root = fonts_dir()
    out: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
            continue
        # id is filename without path; display uses stem before __id suffix if present
        file_id = path.name
        display = path.stem
        if "__" in path.stem:
            display = path.stem.rsplit("__", 1)[0]
        out.append(
            {
                "id": file_id,
                "name": display.replace("_", " "),
                "filename": path.name,
                "path": str(path),
                "size": path.stat().st_size,
            }
        )
    return out


def get_font_path(font_id: str) -> Path | None:
    if not font_id or ".." in font_id or "/" in font_id or "\\" in font_id:
        return None
    path = fonts_dir() / font_id
    if path.is_file() and path.suffix.lower() in ALLOWED_EXT:
        return path
    return None


def save_font(filename: str, data: bytes) -> dict[str, Any]:
    if len(data) > MAX_FONT_BYTES:
        raise ValueError(f"Font too large (max {MAX_FONT_BYTES // (1024 * 1024)} MB)")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Only .ttf, .otf, and .ttc fonts are supported")
    stem = _safe_stem(filename)
    short = uuid.uuid4().hex[:8]
    stored_name = f"{stem}__{short}{ext}"
    dest = fonts_dir() / stored_name
    dest.write_bytes(data)
    logger.info(f"Saved custom font: {stored_name} ({len(data)} bytes)")
    return {
        "id": stored_name,
        "name": stem.replace("_", " "),
        "filename": stored_name,
        "path": str(dest),
        "size": len(data),
    }


def delete_font(font_id: str) -> bool:
    path = get_font_path(font_id)
    if not path:
        return False
    path.unlink(missing_ok=True)
    return True


def font_family_name(font_path: Path) -> str:
    """
    Best-effort family name for ASS Fontname.
    Prefer stem before __id; libass matches family when fontsdir is set.
    """
    stem = font_path.stem
    if "__" in stem:
        stem = stem.rsplit("__", 1)[0]
    return stem.replace("_", " ") or "Custom"
