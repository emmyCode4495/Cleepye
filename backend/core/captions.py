"""
Word-level animated captions (ASS format).
Generates stylish, karaoke-style subtitles from Whisper word timestamps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Caption styles
STYLES = {
    "viral": {
        "name": "Viral",
        "font": "Arial",
        "fontsize": 64,
        "primary": "&H00FFFFFF",      # White
        "highlight": "&H0000FFFF",    # Yellow
        "outline": "&H00000000",      # Black
        "outline_width": 3,
        "shadow": 0,
        "alignment": 2,               # Bottom center
        "margin_v": 80,
    },
    "clean": {
        "name": "Clean",
        "font": "Arial",
        "fontsize": 52,
        "primary": "&H00FFFFFF",
        "highlight": "&H00FFFFFF",
        "outline": "&H00000000",
        "outline_width": 2,
        "shadow": 1,
        "alignment": 2,
        "margin_v": 60,
    },
    "karaoke": {
        "name": "Karaoke",
        "font": "Arial Black",
        "fontsize": 60,
        "primary": "&H00CCCCCC",      # Gray
        "highlight": "&H0000FFFF",    # Yellow
        "outline": "&H00000000",
        "outline_width": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 90,
    },
    "bold": {
        "name": "Bold",
        "font": "Impact",
        "fontsize": 68,
        "primary": "&H00FFFFFF",
        "highlight": "&H0000A5FF",    # Orange
        "outline": "&H00000000",
        "outline_width": 4,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 70,
    },
    "neon": {
        "name": "Neon",
        "font": "Arial",
        "fontsize": 62,
        "primary": "&H00FFFFFF",
        "highlight": "&H00FF00FF",    # Magenta
        "outline": "&H00000000",
        "outline_width": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 85,
    },
    "minimal": {
        "name": "Minimal",
        "font": "Helvetica",
        "fontsize": 48,
        "primary": "&H00FFFFFF",
        "highlight": "&H00FFFFFF",
        "outline": "&H00000000",
        "outline_width": 1,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 50,
    },
    "pop": {
        "name": "Pop",
        "font": "Comic Sans MS",
        "fontsize": 58,
        "primary": "&H0000FFFF",      # Yellow
        "highlight": "&H000000FF",    # Red
        "outline": "&H00000000",
        "outline_width": 3,
        "shadow": 0,
        "alignment": 2,
        "margin_v": 75,
    },
}


def list_styles() -> list[dict[str, str]]:
    """Return available caption styles for UI / CLI."""
    return [{"id": k, "name": v["name"]} for k, v in STYLES.items()]


def _format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _escape_ass_text(text: str) -> str:
    """Escape special ASS characters."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def generate_ass(
    segments: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    style_name: str = "viral",
    max_words_per_line: int = 4,
) -> str:
    """
    Generate ASS subtitle content for a specific clip window.
    Words outside [clip_start, clip_end] are ignored.
    Relative timestamps are used (0 = start of the clip).
    """
    style = STYLES.get(style_name, STYLES["viral"])

    # ASS header
    header = f"""[Script Info]
Title: ClipMine Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style['font']},{style['fontsize']},{style['primary']},{style['highlight']},{style['outline']},&H80000000,-1,0,0,0,100,100,0,0,1,{style['outline_width']},{style['shadow']},{style['alignment']},40,40,{style['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    current_line_words = []
    line_start = None

    def flush_line():
        nonlocal current_line_words, line_start
        if not current_line_words:
            return

        # Build karaoke line with \k tags (centiseconds)
        parts = []
        for w in current_line_words:
            duration_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
            word_text = _escape_ass_text(w["word"].strip())
            parts.append(f"{{\\k{duration_cs}}}{word_text}")

        text = "".join(parts)
        start_t = _format_ass_time(line_start - clip_start)
        end_t = _format_ass_time(current_line_words[-1]["end"] - clip_start)

        events.append(
            f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{text}"
        )
        current_line_words = []
        line_start = None

    # Collect words that fall inside the clip window
    for seg in segments:
        words = seg.get("words") or []
        for w in words:
            w_start = w["start"]
            w_end = w["end"]

            # Skip words outside the clip
            if w_end <= clip_start or w_start >= clip_end:
                continue

            # Clamp to clip boundaries
            w_start = max(w_start, clip_start)
            w_end = min(w_end, clip_end)

            word_data = {
                "word": w["word"],
                "start": w_start,
                "end": w_end,
            }

            if line_start is None:
                line_start = w_start

            current_line_words.append(word_data)

            # Flush when we hit max words or a natural pause
            if len(current_line_words) >= max_words_per_line:
                flush_line()

    flush_line()

    return header + "\n".join(events) + "\n"


def write_ass_file(
    segments: list[dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_path: Path,
    style_name: str = "viral",
) -> Path:
    """Generate and write an ASS file for a clip."""
    content = generate_ass(segments, clip_start, clip_end, style_name=style_name)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote captions: {output_path.name} ({style_name})")
    return output_path
