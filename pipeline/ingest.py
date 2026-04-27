import json
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pipeline.config import PipelineConfig


@dataclass
class MediaAsset:
    path: Path
    media_type: str
    duration_s: float = 0.0
    file_size_mb: float = 0.0
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    metadata: dict = field(default_factory=dict)


def probe_media(filepath: Path) -> MediaAsset:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(filepath)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {filepath}: {result.stderr}")

    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", 0))
    size_mb = float(info.get("format", {}).get("size", 0)) / (1024 * 1024)

    video_stream = None
    audio_stream = None
    for stream in info.get("streams", []):
        if stream["codec_type"] == "video" and video_stream is None:
            video_stream = stream
        elif stream["codec_type"] == "audio" and audio_stream is None:
            audio_stream = stream

    media_type = "video" if video_stream else "audio"

    asset = MediaAsset(
        path=filepath,
        media_type=media_type,
        duration_s=duration,
        file_size_mb=size_mb,
        video_codec=video_stream.get("codec_name") if video_stream else None,
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
        width=int(video_stream["width"]) if video_stream and "width" in video_stream else None,
        height=int(video_stream["height"]) if video_stream and "height" in video_stream else None,
        fps=eval(video_stream.get("r_frame_rate", "0/1")) if video_stream else None,
        sample_rate=int(audio_stream["sample_rate"]) if audio_stream and "sample_rate" in audio_stream else None,
        channels=int(audio_stream["channels"]) if audio_stream and "channels" in audio_stream else None,
        bit_depth=int(audio_stream.get("bits_per_sample", 0)) if audio_stream else None,
    )
    return asset


def extract_audio(video_path: Path, output_path: Path, config: PipelineConfig) -> Path:
    cfg = config.get("pipeline.ingest.audio_extraction", {})
    sample_rate = cfg.get("sample_rate", 48000)
    channels = cfg.get("channels", 2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s24le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")

    return output_path


def ingest(source: Path, config: PipelineConfig) -> dict:
    supported = config.get("pipeline.ingest.supported_formats", [])
    if source.suffix.lower() not in supported:
        raise ValueError(f"Unsupported format: {source.suffix}. Supported: {supported}")

    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    asset = probe_media(source)
    output_dir = config.output_dir
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "source": str(source),
        "asset": {
            "media_type": asset.media_type,
            "duration_s": asset.duration_s,
            "file_size_mb": round(asset.file_size_mb, 2),
            "video_codec": asset.video_codec,
            "audio_codec": asset.audio_codec,
            "width": asset.width,
            "height": asset.height,
            "fps": asset.fps,
            "sample_rate": asset.sample_rate,
            "channels": asset.channels,
        },
    }

    if asset.media_type == "video":
        audio_path = audio_dir / f"{source.stem}_audio.wav"
        if not audio_path.exists():
            extract_audio(source, audio_path, config)
        result["extracted_audio"] = str(audio_path)

    result["audio_source"] = result.get("extracted_audio", str(source))
    return result
