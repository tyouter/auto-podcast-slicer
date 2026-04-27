import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.clip_planning import VersionPlan, ClipDefinition


@dataclass
class VideoProcessResult:
    clip_id: str
    output_path: str
    duration_s: float
    resolution: str = ""
    codec: str = ""
    file_size_mb: float = 0.0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id,
            "output_path": self.output_path,
            "duration_s": round(self.duration_s, 2),
            "resolution": self.resolution,
            "codec": self.codec,
            "file_size_mb": round(self.file_size_mb, 2),
            "issues": self.issues,
        }


def cut_video_clip(
    source_video: Path,
    start_s: float,
    end_s: float,
    output_path: Path,
    config: PipelineConfig,
) -> VideoProcessResult:
    cfg = config.get("pipeline.video_processor", {})
    codec = cfg.get("default_codec", "libx264")
    preset = cfg.get("default_preset", "slow")
    crf = cfg.get("default_crf", 20)
    pixel_format = cfg.get("pixel_format", "yuv420p")
    color_primaries = cfg.get("color_primaries", "bt709")
    color_trc = cfg.get("color_trc", "bt709")
    colorspace = cfg.get("colorspace", "bt709")
    color_range = cfg.get("color_range", "tv")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(source_video),
        "-ss", str(start_s),
        "-to", str(end_s),
        "-c:v", codec,
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", pixel_format,
        "-color_primaries", color_primaries,
        "-color_trc", color_trc,
        "-colorspace", colorspace,
        "-color_range", color_range,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Video clip extraction failed: {result.stderr}")

    duration_s = end_s - start_s
    file_size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    return VideoProcessResult(
        clip_id="",
        output_path=str(output_path),
        duration_s=duration_s,
        codec=codec,
        file_size_mb=file_size_mb,
    )


def cut_video_with_jl_cut(
    source_video: Path,
    start_s: float,
    end_s: float,
    output_path: Path,
    config: PipelineConfig,
    cut_type: str = "j_cut",
    audio_offset_frames: int = 5,
) -> VideoProcessResult:
    fps = config.get("pipeline.video_processor.default_fps", 30)
    offset_s = audio_offset_frames / fps

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = config.get("pipeline.video_processor", {})
    codec = cfg.get("default_codec", "libx264")
    preset = cfg.get("default_preset", "slow")
    crf = cfg.get("default_crf", 20)
    pixel_format = cfg.get("pixel_format", "yuv420p")

    if cut_type == "j_cut":
        audio_start = start_s - offset_s
        video_start = start_s
        audio_end = end_s
        video_end = end_s

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_video),
            "-filter_complex",
            f"[0:v]trim=start={video_start}:end={video_end},setpts=PTS-STARTPTS[v];"
            f"[0:a]atrim=start={audio_start}:end={audio_end},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", codec, "-preset", preset, "-crf", str(crf), "-pix_fmt", pixel_format,
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
    elif cut_type == "l_cut":
        audio_start = start_s
        video_start = start_s
        audio_end = end_s + offset_s
        video_end = end_s

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_video),
            "-filter_complex",
            f"[0:v]trim=start={video_start}:end={video_end},setpts=PTS-STARTPTS[v];"
            f"[0:a]atrim=start={audio_start}:end={audio_end},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", codec, "-preset", preset, "-crf", str(crf), "-pix_fmt", pixel_format,
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
    else:
        return cut_video_clip(source_video, start_s, end_s, output_path, config)

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        return cut_video_clip(source_video, start_s, end_s, output_path, config)

    duration_s = end_s - start_s
    file_size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    return VideoProcessResult(
        clip_id="",
        output_path=str(output_path),
        duration_s=duration_s,
        codec=codec,
        file_size_mb=file_size_mb,
    )


def compose_clips_with_transitions(
    clip_paths: list[Path],
    output_path: Path,
    config: PipelineConfig,
    transition_duration_s: float = 0.5,
) -> VideoProcessResult:
    if not clip_paths:
        raise ValueError("No clips provided for composition")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(clip_paths) == 1:
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return VideoProcessResult(
            clip_id="composed",
            output_path=str(output_path),
            duration_s=0,
        )

    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for clip_path in clip_paths:
            f.write(f"file '{clip_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Clip composition failed: {result.stderr}")

    concat_file.unlink(missing_ok=True)

    file_size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    return VideoProcessResult(
        clip_id="composed",
        output_path=str(output_path),
        duration_s=0,
        file_size_mb=file_size_mb,
    )


def process_version_video(
    source_video: Path,
    version: VersionPlan,
    output_dir: Path,
    config: PipelineConfig,
) -> list[VideoProcessResult]:
    results = []
    version_dir = output_dir / version.version_key
    video_dir = version_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    for clip in version.clips:
        output_path = video_dir / f"{clip.id}.mp4"
        try:
            result = cut_video_clip(
                source_video, clip.start_s, clip.end_s, output_path, config
            )
            result.clip_id = clip.id
            results.append(result)
        except Exception as e:
            results.append(VideoProcessResult(
                clip_id=clip.id,
                output_path=str(output_path),
                duration_s=0,
                issues=[str(e)],
            ))

    if len(version.clips) > 1:
        clip_paths = [
            video_dir / f"{clip.id}.mp4" for clip in version.clips
            if (video_dir / f"{clip.id}.mp4").exists()
        ]
        if clip_paths:
            composed_path = version_dir / f"{version.version_key}_full.mp4"
            try:
                compose_result = compose_clips_with_transitions(
                    clip_paths, composed_path, config
                )
                compose_result.clip_id = f"{version.version_key}_composed"
                results.append(compose_result)
            except Exception as e:
                results.append(VideoProcessResult(
                    clip_id=f"{version.version_key}_composed",
                    output_path=str(composed_path),
                    duration_s=0,
                    issues=[str(e)],
                ))

    report_path = version_dir / "video_process_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)

    return results
