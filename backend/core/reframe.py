"""
Smart reframing: 16:9 → 9:16 with optional face tracking.
Falls back to a stable upper-center crop when OpenCV face tools are unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Social / platform output sizes (width x height)
ASPECT_PRESETS: dict[str, dict] = {
    "9:16": {"width": 1080, "height": 1920, "label": "9:16 · TikTok / Reels / Shorts"},
    "16:9": {"width": 1920, "height": 1080, "label": "16:9 · YouTube / landscape"},
    "1:1": {"width": 1080, "height": 1080, "label": "1:1 · Instagram feed"},
    "4:5": {"width": 1080, "height": 1350, "label": "4:5 · Instagram portrait"},
    "4:3": {"width": 1440, "height": 1080, "label": "4:3 · Classic"},
}


def resolve_aspect(aspect: str) -> tuple[int, int]:
    key = (aspect or "9:16").strip()
    preset = ASPECT_PRESETS.get(key) or ASPECT_PRESETS["9:16"]
    return int(preset["width"]), int(preset["height"])


def list_aspects() -> list[dict]:
    return [
        {"id": k, "label": v["label"], "width": v["width"], "height": v["height"]}
        for k, v in ASPECT_PRESETS.items()
    ]


try:
    import cv2
    _CV2_OK = hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "VideoCapture")
except Exception:
    cv2 = None  # type: ignore
    _CV2_OK = False

_yunet_available = _CV2_OK and hasattr(cv2, "FaceDetectorYN")


def _create_detector(frame_width: int = 640, frame_height: int = 480):
    if not _CV2_OK:
        logger.warning("OpenCV face tools unavailable — using center crop")
        return ("none", None)

    if _yunet_available:
        try:
            model_path = cv2.data.haarcascades.replace(
                "haarcascades", "face_detection_yunet_2023mar.onnx"
            )
            detector = cv2.FaceDetectorYN.create(
                model_path,
                "",
                (frame_width, frame_height),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5,
            )
            logger.info("Using OpenCV YuNet face detector")
            return ("yunet", detector)
        except Exception:
            pass

    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if detector.empty():
            logger.warning("Haar cascade failed to load — using center crop")
            return ("none", None)
        logger.info("Using OpenCV Haar cascade face detector")
        return ("haar", detector)
    except Exception as e:
        logger.warning(f"Face detector unavailable ({e}) — using center crop")
        return ("none", None)


def detect_faces_in_frame(
    frame: np.ndarray,
    detector_type: str,
    detector,
) -> List[Tuple[float, float, float, float]]:
    if detector_type == "none" or detector is None or not _CV2_OK:
        return []

    h, w = frame.shape[:2]
    boxes = []

    try:
        if detector_type == "yunet":
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
            if faces is not None:
                for face in faces:
                    x, y, bw, bh = face[:4]
                    boxes.append(
                        (
                            max(0.0, x / w),
                            max(0.0, y / h),
                            min(1.0, bw / w),
                            min(1.0, bh / h),
                        )
                    )
        elif detector_type == "haar":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            for (x, y, bw, bh) in faces:
                boxes.append((x / w, y / h, bw / w, bh / h))
    except Exception as e:
        logger.debug(f"Face detect failed on frame: {e}")

    return boxes


def smooth_centers(
    centers: List[Tuple[float, float]], alpha: float = 0.22
) -> List[Tuple[float, float]]:
    if not centers:
        return centers
    smoothed = [centers[0]]
    for i in range(1, len(centers)):
        prev_x, prev_y = smoothed[-1]
        x, y = centers[i]
        smoothed.append((alpha * x + (1 - alpha) * prev_x, alpha * y + (1 - alpha) * prev_y))
    return smoothed


def compute_crop_boxes(
    video_path: str | Path,
    sample_fps: float = 2.0,
) -> List[dict]:
    """
    Return crop keyframes. Always succeeds — falls back to center crop.
    """
    # Default center-ish framing for talking-head content
    default = [{"time": 0.0, "x_center": 0.5, "y_center": 0.42}]

    if not _CV2_OK:
        logger.info("OpenCV unavailable — center crop only")
        return default

    path = Path(video_path)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            logger.warning(f"Cannot open video for face tracking: {path}")
            return default

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(fps / sample_fps))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

        detector_type, detector = _create_detector(width, height)

        centers = []
        times = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                t = frame_idx / fps
                boxes = detect_faces_in_frame(frame, detector_type, detector)
                if boxes:
                    largest = max(boxes, key=lambda b: b[2] * b[3])
                    x, y, bw, bh = largest
                    cx = x + bw / 2
                    cy = y + bh / 2
                else:
                    cx, cy = 0.5, 0.42
                centers.append((cx, cy))
                times.append(t)
            frame_idx += 1

        cap.release()

        if not centers:
            return default

        smoothed = smooth_centers(centers)
        result = [
            {"time": round(t, 3), "x_center": round(cx, 4), "y_center": round(cy, 4)}
            for t, (cx, cy) in zip(times, smoothed)
        ]
        logger.info(f"Computed {len(result)} crop keyframes for {path.name}")
        return result
    except Exception as e:
        logger.warning(f"Face tracking failed ({e}) — using center crop")
        return default


def build_ffmpeg_crop_filter(
    crop_data: List[dict],
    input_width: int,
    input_height: int,
    output_width: int = 1080,
    output_height: int = 1920,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> str:
    if not crop_data:
        cx, cy = 0.5, 0.42
    else:
        relevant = [
            d
            for d in crop_data
            if d["time"] >= clip_start and (clip_end is None or d["time"] <= clip_end)
        ]
        if not relevant:
            relevant = crop_data
        cx = sum(d["x_center"] for d in relevant) / len(relevant)
        cy = sum(d["y_center"] for d in relevant) / len(relevant)

    target_aspect = output_width / output_height

    if (input_width / input_height) > target_aspect:
        crop_h = input_height
        crop_w = int(input_height * target_aspect)
    else:
        crop_w = input_width
        crop_h = int(input_width / target_aspect)

    x = int(cx * input_width - crop_w / 2)
    y = int(cy * input_height - crop_h / 2)
    x = max(0, min(x, input_width - crop_w))
    y = max(0, min(y, input_height - crop_h))

    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={output_width}:{output_height}"
