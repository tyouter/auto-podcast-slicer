from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from pipeline.subtitle_style import (
    OrientationStyle,
    SubtitleStyle,
    _ORIENTATION_FIELDS,
    _parse_aspect_ratio,
    get_font_metrics,
)


@dataclass
class ExtractedRegion:
    x: int
    y: int
    w: int
    h: int
    mask: np.ndarray


@dataclass
class ExtractedStyle:
    text_color: str = "FFFFFF"
    text_color_alpha: int = 0
    outline_width: float = 0.0
    outline_color: str = "000000"
    outline_alpha: int = 0
    shadow_depth: float = 0.0
    shadow_color: str = "000000"
    shadow_alpha: int = 0
    bg_enabled: bool = False
    bg_color: str = "1A1A1A"
    bg_alpha: int = 128
    bg_outline_color: str = "000000"
    bg_outline_alpha: int = 255
    bg_shadow_color: str = "000000"
    bg_shadow_alpha: int = 255
    corner_radius: int = 0
    padding_h: int = 0
    padding_v: int = 0
    margin_v: int = 90
    font_size: int = 104
    bold: bool = False
    italic: bool = False
    spacing: float = 0.0
    text_alignment: int = 2
    max_text_width_ratio: float = 0.85
    video_width: int = 3840
    video_height: int = 2160
    is_vertical: bool = False
    overlay_content_aspect: str = ""
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


def extract_frames_from_video(
    video_path: str | Path,
    timestamps: list[float] | None = None,
    max_frames: int = 5,
) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    if timestamps is None:
        if duration > 10:
            start = duration * 0.2
            end = duration * 0.8
            step = (end - start) / max(max_frames - 1, 1)
            timestamps = [start + i * step for i in range(max_frames)]
        else:
            timestamps = [duration / 2]

    frames = []
    for ts in timestamps:
        frame_idx = int(ts * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)

    cap.release()
    return frames


def _detect_subtitle_region(
    frame: np.ndarray,
    search_ratio: float = 0.3,
) -> ExtractedRegion | None:
    h, w = frame.shape[:2]
    search_top = int(h * (1 - search_ratio))
    roi = frame[search_top:, :]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blurred, 50, 150)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
    dilated = cv2.dilate(edges, kernel_h, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area < w * h * 0.005:
            continue
        aspect = cw / max(ch, 1)
        if aspect < 1.5:
            continue
        if ch > h * 0.15:
            continue
        candidates.append((x, y + search_top, cw, ch, area))

    if not candidates:
        return _fallback_subtitle_region(frame)

    candidates.sort(key=lambda c: c[4], reverse=True)
    best = candidates[0]
    rx, ry, rw, rh = best[0], best[1], best[2], best[3]

    pad_x = int(rw * 0.05)
    pad_y = int(rh * 0.3)
    rx = max(0, rx - pad_x)
    ry = max(0, ry - pad_y)
    rw = min(w - rx, rw + pad_x * 2)
    rh = min(h - ry, rh + pad_y * 2)

    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    mask[ry:ry + rh, rx:rx + rw] = 255

    return ExtractedRegion(x=rx, y=ry, w=rw, h=rh, mask=mask)


def _fallback_subtitle_region(frame: np.ndarray) -> ExtractedRegion | None:
    h, w = frame.shape[:2]
    ry = int(h * 0.82)
    rx = int(w * 0.05)
    rw = int(w * 0.9)
    rh = int(h * 0.12)

    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    mask[ry:ry + rh, rx:rx + rw] = 255

    return ExtractedRegion(x=rx, y=ry, w=rw, h=rh, mask=mask)


def _rgb_to_hex(bgr: tuple[int, int, int]) -> str:
    return f"{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"


def _analyze_text_color(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> tuple[str, int]:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    v_channel = hsv[:, :, 2]
    s_channel = hsv[:, :, 1]

    bright_mask = (v_channel > 180) & (s_channel < 80)
    bright_pixels = roi[bright_mask]

    if len(bright_pixels) < 10:
        dark_mask = (v_channel < 80) & (s_channel < 80)
        dark_pixels = roi[dark_mask]
        if len(dark_pixels) >= 10:
            mean_color = np.mean(dark_pixels, axis=0).astype(int)
            return _rgb_to_hex(tuple(mean_color)), 0
        return "FFFFFF", 0

    mean_color = np.mean(bright_pixels, axis=0).astype(int)
    return _rgb_to_hex(tuple(mean_color)), 0


def _analyze_background(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> tuple[bool, str, int, int]:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 30, 100)
    edge_density = np.sum(edges > 0) / max(edges.size, 1)

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    low_sat_mask = s_channel < 50
    mid_val_mask = (v_channel > 20) & (v_channel < 200)
    bg_candidate_mask = low_sat_mask & mid_val_mask

    bg_pixel_count = np.sum(bg_candidate_mask)
    total_pixels = bg_candidate_mask.size
    bg_ratio = bg_pixel_count / max(total_pixels, 1)

    bg_enabled = bg_ratio > 0.15 and edge_density < 0.3

    if bg_enabled:
        bg_pixels = roi[bg_candidate_mask]
        if len(bg_pixels) > 0:
            mean_color = np.mean(bg_pixels, axis=0).astype(int)
            bg_hex = _rgb_to_hex(tuple(mean_color))
            alpha = min(255, max(64, int(bg_ratio * 400)))
            return True, bg_hex, alpha, 0
        return True, "1A1A1A", 128, 0

    return False, "000000", 0, 0


def _analyze_corner_radius(
    frame: np.ndarray,
    region: ExtractedRegion,
    bg_enabled: bool,
) -> int:
    if not bg_enabled:
        return 0

    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0

    largest = max(contours, key=cv2.contourArea)
    x, y, cw, ch = cv2.boundingRect(largest)
    perimeter = cv2.arcLength(largest, True)
    rect_perimeter = 2 * (cw + ch)

    if rect_perimeter == 0:
        return 0

    circularity = perimeter / rect_perimeter
    if circularity < 1.05:
        return 0

    approx = cv2.approxPolyDP(largest, 0.02 * perimeter, True)
    corner_pts = len(approx)

    if corner_pts <= 4:
        r = min(cw, ch) // 6
        return min(r, 30)

    return 0


def _analyze_outline(
    frame: np.ndarray,
    region: ExtractedRegion,
    text_color_hex: str,
) -> tuple[float, str, int]:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=1)

    text_mask = (gray > 180) if text_color_hex[0] >= '8' else (gray < 80)
    outline_zone = dilated & ~text_mask.astype(np.uint8) * 255
    outline_pixels = np.sum(outline_zone > 0)

    if outline_pixels < roi.size * 0.005:
        return 0.0, "000000", 0

    outline_mask = outline_zone > 0
    outline_pixels_arr = roi[outline_mask]
    if len(outline_pixels_arr) == 0:
        return 0.0, "000000", 0

    mean_color = np.mean(outline_pixels_arr, axis=0).astype(int)
    outline_hex = _rgb_to_hex(tuple(mean_color))

    h, w = roi.shape[:2]
    scale = 3840 / max(w, 1)
    outline_w = max(1, min(6, int(1.5 * scale)))

    return float(outline_w), outline_hex, 0


def _analyze_shadow(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> tuple[float, str, int]:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    shadow_mask = (gray > 10) & (gray < 80)
    shadow_pixels = np.sum(shadow_mask)

    if shadow_pixels < roi.size * 0.01:
        return 0.0, "000000", 0

    shadow_pixels_arr = roi[shadow_mask]
    if len(shadow_pixels_arr) == 0:
        return 0.0, "000000", 0

    mean_color = np.mean(shadow_pixels_arr, axis=0).astype(int)
    shadow_hex = _rgb_to_hex(tuple(mean_color))

    return 2.0, shadow_hex, 80


def _estimate_font_size(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> int:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 72

    char_heights = []
    for cnt in contours:
        _, _, _, ch = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        if area < 20:
            continue
        char_heights.append(ch)

    if not char_heights:
        return 72

    median_h = sorted(char_heights)[len(char_heights) // 2]

    frame_h = frame.shape[0]
    scale = 3840 / max(frame_h, 1)
    estimated = int(median_h * scale * 2.0)

    return max(60, min(220, estimated))


def _estimate_margin_v(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> int:
    frame_h = frame.shape[0]
    bottom_dist = frame_h - (region.y + region.h)
    scale = 2160 / max(frame_h, 1)
    return max(20, int(bottom_dist * scale))


def _estimate_padding(
    frame: np.ndarray,
    region: ExtractedRegion,
    bg_enabled: bool,
) -> tuple[int, int]:
    if not bg_enabled:
        return 0, 0

    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    text_pixels = np.where(binary > 0)
    if len(text_pixels[0]) == 0:
        return 20, 10

    min_x = np.min(text_pixels[1])
    max_x = np.max(text_pixels[1])
    min_y = np.min(text_pixels[0])
    max_y = np.max(text_pixels[0])

    h, w = roi.shape[:2]
    pad_h = max(0, min(min_x, w - max_x))
    pad_v = max(0, min(min_y, h - max_y))

    scale = 3840 / max(w, 1)
    return int(pad_h * scale), int(pad_v * scale)


def _detect_alignment(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> int:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    h, w = binary.shape
    left_weight = np.sum(binary[:, :w // 3])
    center_weight = np.sum(binary[:, w // 3:2 * w // 3])
    right_weight = np.sum(binary[:, 2 * w // 3:])

    if center_weight > left_weight and center_weight > right_weight:
        return 2
    if left_weight > right_weight:
        return 1
    return 9


def _detect_bold(
    frame: np.ndarray,
    region: ExtractedRegion,
) -> bool:
    roi = frame[region.y:region.y + region.h, region.x:region.x + region.w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / max(edges.size, 1)

    return edge_density > 0.15


def _detect_is_vertical(frame: np.ndarray) -> bool:
    h, w = frame.shape[:2]
    return h > w


def _estimate_overlay_aspect(frame: np.ndarray, is_vertical: bool) -> str:
    if not is_vertical:
        return ""
    h, w = frame.shape[:2]
    ratio = h / max(w, 1)
    if abs(ratio - 16 / 9) < 0.3:
        return "16:9"
    if abs(ratio - 4 / 3) < 0.3:
        return "4:3"
    return "16:9"


def extract_style_from_frame(frame: np.ndarray) -> ExtractedStyle:
    result = ExtractedStyle()

    is_vertical = _detect_is_vertical(frame)
    result.is_vertical = is_vertical
    h, w = frame.shape[:2]

    if is_vertical:
        result.video_width = 1080
        result.video_height = 1920
    else:
        result.video_width = 3840
        result.video_height = 2160

    result.overlay_content_aspect = _estimate_overlay_aspect(frame, is_vertical)

    region = _detect_subtitle_region(frame)
    if region is None:
        result.notes.append("No subtitle region detected, using defaults")
        result.confidence = 0.1
        return result

    result.text_color, result.text_color_alpha = _analyze_text_color(frame, region)
    result.bg_enabled, result.bg_color, result.bg_alpha, result.bg_outline_alpha = _analyze_background(frame, region)
    result.corner_radius = _analyze_corner_radius(frame, region, result.bg_enabled)
    result.outline_width, result.outline_color, result.outline_alpha = _analyze_outline(frame, region, result.text_color)
    result.shadow_depth, result.shadow_color, result.shadow_alpha = _analyze_shadow(frame, region)
    result.font_size = _estimate_font_size(frame, region)
    result.margin_v = _estimate_margin_v(frame, region)
    result.padding_h, result.padding_v = _estimate_padding(frame, region, result.bg_enabled)
    result.text_alignment = _detect_alignment(frame, region)
    result.bold = _detect_bold(frame, region)

    result.confidence = 0.7
    result.notes.append("Style extracted from single frame")

    return result


def extract_style_from_image(image_path: str | Path) -> ExtractedStyle:
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")
    return extract_style_from_frame(img)


def extract_style_from_video(
    video_path: str | Path,
    timestamps: list[float] | None = None,
    max_frames: int = 5,
) -> ExtractedStyle:
    frames = extract_frames_from_video(video_path, timestamps, max_frames)
    if not frames:
        raise ValueError(f"No frames extracted from video: {video_path}")

    if len(frames) == 1:
        return extract_style_from_frame(frames[0])

    styles = [extract_style_from_frame(f) for f in frames]
    merged = _merge_styles(styles)
    merged.notes.append(f"Style extracted from {len(frames)} frames")
    return merged


def _merge_styles(styles: list[ExtractedStyle]) -> ExtractedStyle:
    if not styles:
        return ExtractedStyle()

    best = max(styles, key=lambda s: s.confidence)

    text_colors = [s.text_color for s in styles if s.confidence > 0.3]
    if text_colors:
        from collections import Counter
        best.text_color = Counter(text_colors).most_common(1)[0][0]

    bg_enabled_count = sum(1 for s in styles if s.bg_enabled)
    best.bg_enabled = bg_enabled_count > len(styles) / 2

    font_sizes = [s.font_size for s in styles if s.confidence > 0.3]
    if font_sizes:
        best.font_size = int(np.median(font_sizes))

    best.confidence = np.mean([s.confidence for s in styles])
    return best


def _ensure_python_type(val):
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    return val


def extracted_to_orientation_style(
    extracted: ExtractedStyle,
    is_vertical: bool = False,
) -> OrientationStyle:
    if is_vertical:
        return OrientationStyle(
            video_width=1080,
            video_height=1920,
            output_width=1080,
            output_height=1920,
            font_size=72,  # default vertical — style copy doesn't transfer font size
            bold=bool(_ensure_python_type(extracted.bold)),
            text_color=str(extracted.text_color),
            text_color_alpha=int(_ensure_python_type(extracted.text_color_alpha)),
            outline_width=float(_ensure_python_type(extracted.outline_width)),
            outline_color=str(extracted.outline_color),
            outline_alpha=int(_ensure_python_type(extracted.outline_alpha)),
            shadow_depth=float(_ensure_python_type(extracted.shadow_depth)),
            shadow_color=str(extracted.shadow_color),
            shadow_alpha=int(_ensure_python_type(extracted.shadow_alpha)),
            bg_enabled=bool(_ensure_python_type(extracted.bg_enabled)),
            bg_color=str(extracted.bg_color),
            bg_alpha=min(255, int(_ensure_python_type(extracted.bg_alpha) * 1.2)),
            bg_outline_color=str(extracted.bg_outline_color),
            bg_outline_alpha=int(_ensure_python_type(extracted.bg_outline_alpha)),
            bg_shadow_color=str(extracted.bg_shadow_color),
            bg_shadow_alpha=int(_ensure_python_type(extracted.bg_shadow_alpha)),
            corner_radius=max(0, int(_ensure_python_type(extracted.corner_radius) * 0.7)),
            padding_h=max(0, int(_ensure_python_type(extracted.padding_h) * 0.7)),
            padding_v=max(0, int(_ensure_python_type(extracted.padding_v) * 0.7)),
            margin_v=max(20, int(_ensure_python_type(extracted.margin_v) * 0.8)),
            max_text_width_ratio=float(_ensure_python_type(extracted.max_text_width_ratio)),
            text_alignment=int(_ensure_python_type(extracted.text_alignment)),
            overlay_content_aspect=str(extracted.overlay_content_aspect) if extracted.overlay_content_aspect else "16:9",
        )

    return OrientationStyle(
        video_width=int(_ensure_python_type(extracted.video_width)),
        video_height=int(_ensure_python_type(extracted.video_height)),
        font_size=96,  # default — style copy doesn't transfer font size
        bold=bool(_ensure_python_type(extracted.bold)),
        text_color=str(extracted.text_color),
        text_color_alpha=int(_ensure_python_type(extracted.text_color_alpha)),
        outline_width=float(_ensure_python_type(extracted.outline_width)),
        outline_color=str(extracted.outline_color),
        outline_alpha=int(_ensure_python_type(extracted.outline_alpha)),
        shadow_depth=float(_ensure_python_type(extracted.shadow_depth)),
        shadow_color=str(extracted.shadow_color),
        shadow_alpha=int(_ensure_python_type(extracted.shadow_alpha)),
        bg_enabled=bool(_ensure_python_type(extracted.bg_enabled)),
        bg_color=str(extracted.bg_color),
        bg_alpha=int(_ensure_python_type(extracted.bg_alpha)),
        bg_outline_color=str(extracted.bg_outline_color),
        bg_outline_alpha=int(_ensure_python_type(extracted.bg_outline_alpha)),
        bg_shadow_color=str(extracted.bg_shadow_color),
        bg_shadow_alpha=int(_ensure_python_type(extracted.bg_shadow_alpha)),
        corner_radius=max(8, int(_ensure_python_type(extracted.corner_radius))) if bool(_ensure_python_type(extracted.bg_enabled)) else 0,
        padding_h=max(30, int(_ensure_python_type(extracted.padding_h))) if bool(_ensure_python_type(extracted.bg_enabled)) else 0,
        padding_v=max(16, int(_ensure_python_type(extracted.padding_v))) if bool(_ensure_python_type(extracted.bg_enabled)) else 0,
        margin_v=60,  # default — style copy doesn't transfer position
        max_text_width_ratio=float(_ensure_python_type(extracted.max_text_width_ratio)),
        text_alignment=int(_ensure_python_type(extracted.text_alignment)),
    )


def generate_style_config(
    extracted: ExtractedStyle,
    name: str = "extracted_style",
    description: str = "",
) -> SubtitleStyle:
    if not description:
        desc_parts = []
        if extracted.bg_enabled:
            desc_parts.append(f"背景色#{extracted.bg_color}")
        desc_parts.append(f"文字色#{extracted.text_color}")
        if extracted.outline_width > 0:
            desc_parts.append(f"描边{extracted.outline_width}px")
        if extracted.shadow_depth > 0:
            desc_parts.append("阴影")
        if extracted.bold:
            desc_parts.append("粗体")
        description = "提取样式 - " + " + ".join(desc_parts)

    horizontal = extracted_to_orientation_style(extracted, is_vertical=False)
    vertical = extracted_to_orientation_style(extracted, is_vertical=True)

    return SubtitleStyle(
        name=name,
        description=description,
        horizontal=horizontal,
        vertical=vertical,
    )


def save_style_yaml(
    style: SubtitleStyle,
    output_path: str | Path,
) -> Path:
    import yaml

    output_path = Path(output_path)

    data = {
        "name": style.name,
        "description": style.description,
    }

    for orientation_name, orientation in [("horizontal", style.horizontal), ("vertical", style.vertical)]:
        if orientation is None:
            continue
        orient_data = {}
        for f_name in _ORIENTATION_FIELDS:
            val = getattr(orientation, f_name)
            if isinstance(val, (np.integer, np.int64, np.int32)):
                val = int(val)
            elif isinstance(val, (np.floating, np.float64, np.float32)):
                val = float(val)
            elif isinstance(val, np.bool_):
                val = bool(val)
            elif isinstance(val, np.ndarray):
                val = val.tolist()
            orient_data[f_name] = val
        data[orientation_name] = orient_data

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return output_path


def extract_and_save(
    source: str | Path,
    output_name: str = "extracted_style",
    output_dir: str | Path | None = None,
    timestamps: list[float] | None = None,
    max_frames: int = 5,
) -> tuple[SubtitleStyle, Path]:
    source = Path(source)

    if source.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"):
        extracted = extract_style_from_image(source)
    elif source.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"):
        extracted = extract_style_from_video(source, timestamps, max_frames)
    else:
        raise ValueError(f"Unsupported file format: {source.suffix}")

    style = generate_style_config(extracted, name=output_name)

    if output_dir is None:
        from pipeline.subtitle_style import _STYLES_DIR
        output_dir = _STYLES_DIR
    output_dir = Path(output_dir)

    yaml_path = save_style_yaml(style, output_dir / f"{output_name}.yaml")

    return style, yaml_path


def verify_extracted_style(
    style: SubtitleStyle,
    sample_text: str = "字幕样式验证测试",
    output_dir: str | Path | None = None,
) -> dict:
    from pipeline.subtitle_renderer import generate_ass_with_style

    results = {"horizontal": {}, "vertical": {}}

    for orientation_name in ("horizontal", "vertical"):
        orientation = getattr(style, orientation_name)
        if orientation is None:
            continue

        entries = [
            {"start_s": 0.0, "end_s": 5.0, "text": sample_text},
            {"start_s": 5.5, "end_s": 10.0, "text": "第二行测试文字"},
        ]

        ass_content = generate_ass_with_style(entries, orientation)

        has_script_info = "[Script Info]" in ass_content
        has_events = "[Events]" in ass_content
        has_dialogue = "Dialogue:" in ass_content
        has_text = sample_text in ass_content

        results[orientation_name] = {
            "ass_generated": True,
            "has_script_info": has_script_info,
            "has_events": has_events,
            "has_dialogue": has_dialogue,
            "has_text": has_text,
            "ass_length": len(ass_content),
            "video_resolution": f"{orientation.video_width}x{orientation.video_height}",
            "font_name": orientation.font_name,
            "font_size": orientation.font_size,
            "text_color": orientation.text_color,
            "bg_enabled": orientation.bg_enabled,
            "bg_color": orientation.bg_color if orientation.bg_enabled else "N/A",
            "outline_width": orientation.outline_width,
            "shadow_depth": orientation.shadow_depth,
        }

        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            ass_path = output_dir / f"verify_{style.name}_{orientation_name}.ass"
            ass_path.write_text(ass_content, encoding="utf-8")
            results[orientation_name]["ass_path"] = str(ass_path)

    return results
