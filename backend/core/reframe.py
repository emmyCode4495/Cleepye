"""
Smart reframing: 16:9 → 9:16 with face / subject tracking.
Uses OpenCV (YuNet if available, otherwise Haar cascade) + temporal smoothing.
Supports per-clip average for more accurate framing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_yunet_available = hasattr(cv2, "FaceDetectorYN")


def _create_detector(frame_width: int = 640, frame_height: int = 480):
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

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        logger.warning("Haar cascade failed to load — will use center crop")
        return ("none", None)
    logger.info("Using OpenCV Haar cascade face detector")
    return ("haar", detector)


def detect_faces_in_frame(
    frame: np.ndarray,
    detector_type: str,
    detector,
) -> List[Tuple[float, float, float, float]]:
    h, w = frame.shape[:2]
    boxes = []

    if detector_type == "yunet" and detector is not None:
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
    elif detector_type == "haar" and detector is not None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        for (x, y, bw, bh) in faces:
            boxes.append((x / w, y / h, bw / w, bh / h))

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
    path = Path(video_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(fps / sample_fps))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

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
        return [{"time": 0.0, "x_center": 0.5, "y_center": 0.42}]

    smoothed = smooth_centers(centers)
    result = [
        {"time": round(t, 3), "x_center": round(cx, 4), "y_center": round(cy, 4)}
        for t, (cx, cy) in zip(times, smoothed)
    ]
    logger.info(f"Computed {len(result)} crop keyframes for {path.name}")
    return result


def build_ffmpeg_crop_filter(
    crop_data: List[dict],
    input_width: int,
    input_height: int,
    output_width: int = 1080,
    output_height: int = 1920,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> str:
    """
    Build crop filter using keyframes that fall inside the clip window.
    More accurate than a global average.
    """
    if not crop_data:
        cx, cy = 0.5, 0.42
    else:
        relevant = [
            d for d in crop_data
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
