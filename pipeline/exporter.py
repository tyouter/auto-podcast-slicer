import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.loudness_normalizer import normalize_for_platform


@dataclass
class ExportResult:
    platform: str
    output_path: str
    file_size_mb: float = 0.0
    duration_s: float = 0.0
    resolution: str = ""
    codec: str = ""
    audio_codec: str = ""
    audio_bitrate: str = ""
    loudness_lufs: float | None = None
    success: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "output_path": self.output_path,
            "file_size_mb": round(self.file_size_mb, 2),
            "duration_s": round(self.duration_s, 2),
            "resolution": self.resolution,
            "codec": self.codec,
            "audio_codec": self.audio_codec,
            "audio_bitrate": self.audio_bitrate,
            "loudness_lufs": self.loudness_lufs,
            "success": self.success,
            "issues": self.issues,
        }


def export_for_platform(
    input_path: Path,
    output_dir: Path,
    platform: str,
    config: PipelineConfig,
    subtitle_path: Path | None = None,
) -> ExportResult:
    platform_cfg = config.get_platform_config(platform)
    if not platform_cfg:
        return ExportResult(
            platform=platform,
            output_path="",
            success=False,
            issues=[f"Unknown platform: {platform}"],
        )

    video_cfg = platform_cfg.get("video", {})
    audio_cfg = platform_cfg.get("audio", {})

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}_{platform}.mp4"

    resolution = video_cfg.get("resolution", "1920x1080")
    width, height = resolution.split("x")
    bitrate = video_cfg.get("bitrate", "8M")
    fps = video_cfg.get("fps", 30)
    codec = video_cfg.get("codec", "libx264")
    pixel_format = video_cfg.get("pixel_format", "yuv420p")

    audio_codec = audio_cfg.get("codec", "aac")
    audio_bitrate = audio_cfg.get("bitrate", "192k")
    sample_rate = audio_cfg.get("sample_rate", 48000)
    channels = audio_cfg.get("channels", 2)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
    ]

    if subtitle_path and subtitle_path.exists():
        cmd.extend(["-i", str(subtitle_path)])

    cmd.extend([
        "-c:v", codec,
        "-b:v", bitrate,
        "-r", str(fps),
        "-s", resolution,
        "-pix_fmt", pixel_format,
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "tv",
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", str(sample_rate),
        "-ac", str(channels),
    ])

    if subtitle_path and subtitle_path.exists():
        subtitle_codec = "mov_text" if output_path.suffix == ".mp4" else "srt"
        cmd.extend(["-c:s", subtitle_codec])

    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return ExportResult(
            platform=platform,
            output_path=str(output_path),
            success=False,
            issues=[f"Export failed: {result.stderr[:500]}"],
        )

    audio_output = output_dir / f"{input_path.stem}_{platform}_audio.wav"
    try:
        normalize_for_platform(output_path, audio_output, platform, config)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    file_size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(output_path)
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, encoding="utf-8")
    duration_s = 0.0
    if probe_result.returncode == 0:
        info = json.loads(probe_result.stdout)
        duration_s = float(info.get("format", {}).get("duration", 0))

    return ExportResult(
        platform=platform,
        output_path=str(output_path),
        file_size_mb=file_size_mb,
        duration_s=duration_s,
        resolution=resolution,
        codec=codec,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        success=True,
    )


def export_all_platforms(
    input_path: Path,
    output_dir: Path,
    platforms: list[str],
    config: PipelineConfig,
    subtitle_path: Path | None = None,
) -> list[ExportResult]:
    results = []
    for platform in platforms:
        platform_dir = output_dir / platform
        result = export_for_platform(input_path, platform_dir, platform, config, subtitle_path)
        results.append(result)
    return results


def export_audio_only(
    input_path: Path,
    output_dir: Path,
    platform: str,
    config: PipelineConfig,
) -> ExportResult:
    platform_cfg = config.get_platform_config(platform)
    audio_cfg = platform_cfg.get("audio", {})

    output_dir.mkdir(parents=True, exist_ok=True)

    audio_codec = audio_cfg.get("codec", "aac")
    audio_bitrate = audio_cfg.get("bitrate", "192k")
    sample_rate = audio_cfg.get("sample_rate", 48000)
    channels = audio_cfg.get("channels", 2)

    ext = "m4a" if audio_codec == "aac" else "wav"
    output_path = output_dir / f"{input_path.stem}_{platform}.{ext}"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", str(sample_rate),
        "-ac", str(channels),
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return ExportResult(
            platform=platform,
            output_path=str(output_path),
            success=False,
            issues=[f"Audio export failed: {result.stderr[:500]}"],
        )

    file_size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    return ExportResult(
        platform=platform,
        output_path=str(output_path),
        file_size_mb=file_size_mb,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        success=True,
    )
