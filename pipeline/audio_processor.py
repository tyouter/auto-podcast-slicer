import json
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.clip_planning import VersionPlan, ClipDefinition, MaterialDefinition


@dataclass
class AudioProcessResult:
    clip_id: str
    output_path: str
    duration_s: float
    crossfade_applied: bool = False
    breath_processed: bool = False
    fade_in_applied: bool = False
    fade_out_applied: bool = False
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def find_nearest_silence(
    audio_path: Path, target_s: float, search_range_s: float = 2.0, min_silence_s: float = 0.3
) -> Optional[float]:
    start_s = max(0, target_s - search_range_s)
    end_s = target_s + search_range_s

    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise=-40dB:d={min_silence_s}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    silences = []
    for line in result.stderr.split("\n"):
        if "silence_start" in line:
            try:
                t = float(line.split("silence_start:")[1].strip().split()[0])
                if start_s <= t <= end_s:
                    silences.append(t)
            except (ValueError, IndexError):
                pass
        elif "silence_end" in line:
            try:
                t = float(line.split("silence_end:")[1].strip().split("|")[0].strip())
                if start_s <= t <= end_s:
                    silences.append(t)
            except (ValueError, IndexError):
                pass

    if not silences:
        return None

    return min(silences, key=lambda s: abs(s - target_s))


def find_zero_crossing(audio_path: Path, target_s: float, search_range_s: float = 0.05) -> Optional[float]:
    return target_s


def apply_crossfade(
    input_path: Path, output_path: Path,
    start_s: float, end_s: float,
    crossfade_ms: int = 50,
    fade_in_ms: int = 30,
    fade_out_ms: int = 50,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = []
    filters.append(f"atrim=start={start_s}:end={end_s}")
    filters.append("asetpts=PTS-STARTPTS")
    filters.append(f"afade=t=in:st=0:d={fade_in_ms / 1000}")
    filters.append(f"afade=t=out:st={end_s - start_s - fade_out_ms / 1000}:d={fade_out_ms / 1000}")

    filter_str = ",".join(filters)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", filter_str,
        "-c:a", "pcm_s24le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Audio clip extraction failed: {result.stderr}")

    return output_path


def detect_breaths(audio_path: Path, threshold_db: float = -30, min_duration_s: float = 0.15, max_duration_s: float = 0.8) -> list[dict]:
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration_s}",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    breaths = []
    current_start = None

    for line in result.stderr.split("\n"):
        if "silence_start" in line:
            try:
                t = float(line.split("silence_start:")[1].strip().split()[0])
                current_start = t
            except (ValueError, IndexError):
                pass
        elif "silence_end" in line and current_start is not None:
            try:
                t = float(line.split("silence_end:")[1].strip().split("|")[0].strip())
                duration = t - current_start
                if min_duration_s <= duration <= max_duration_s:
                    breaths.append({
                        "start_s": current_start,
                        "end_s": t,
                        "duration_s": round(duration, 3),
                    })
                current_start = None
            except (ValueError, IndexError):
                current_start = None

    return breaths


def process_breaths(
    input_path: Path, output_path: Path,
    mode: str = "reduce",
    reduction_db: float = -20,
    min_duration: float = 0.15,
    max_duration: float = 0.8,
) -> Path:
    breaths = detect_breaths(input_path, min_duration_s=min_duration, max_duration_s=max_duration)

    if not breaths:
        if input_path != output_path:
            import shutil
            shutil.copy2(input_path, output_path)
        return output_path

    if mode == "remove":
        filters = []
        for b in breaths:
            filters.append(f"volume=0:enable='between(t,{b['start_s']},{b['end_s']})'")
        filter_str = ",".join(filters) if filters else "anull"
    else:
        filters = []
        for b in breaths:
            filters.append(f"volume={reduction_db}dB:enable='between(t,{b['start_s']},{b['end_s']})'")
        filter_str = ",".join(filters) if filters else "anull"

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", filter_str,
        "-c:a", "pcm_s24le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Breath processing failed: {result.stderr}")

    return output_path


def optimize_cut_point(
    audio_path: Path, target_start_s: float, target_end_s: float,
    config: PipelineConfig,
) -> tuple[float, float]:
    cfg = config.get("pipeline.audio_processor.cut_point", {})
    prefer_silence = cfg.get("prefer_silence", True)
    prefer_zero_crossing = cfg.get("prefer_zero_crossing", True)
    min_silence = cfg.get("min_silence_for_cut", 0.3)
    padding_before = cfg.get("padding_before_ms", 100) / 1000
    padding_after = cfg.get("padding_after_ms", 100) / 1000

    actual_start = max(0, target_start_s - padding_before)
    actual_end = target_end_s + padding_after

    if prefer_silence:
        silence_start = find_nearest_silence(audio_path, target_start_s, search_range_s=1.0, min_silence_s=min_silence)
        if silence_start is not None:
            actual_start = silence_start

        silence_end = find_nearest_silence(audio_path, target_end_s, search_range_s=1.0, min_silence_s=min_silence)
        if silence_end is not None:
            actual_end = silence_end

    return actual_start, actual_end


def process_clip_audio(
    source_audio: Path,
    clip: ClipDefinition,
    output_dir: Path,
    config: PipelineConfig,
) -> AudioProcessResult:
    cfg = config.get("pipeline.audio_processor", {})
    crossfade_ms = cfg.get("crossfade_duration_ms", 50)
    fade_in_ms = cfg.get("fade_in_duration_ms", 30)
    fade_out_ms = cfg.get("fade_out_duration_ms", 50)
    breath_cfg = cfg.get("breath_handling", {})

    actual_start, actual_end = optimize_cut_point(
        source_audio, clip.start_s, clip.end_s, config
    )

    raw_clip_path = output_dir / f"{clip.id}_raw.wav"
    output_path = output_dir / f"{clip.id}.wav"

    output_dir.mkdir(parents=True, exist_ok=True)

    apply_crossfade(
        source_audio, raw_clip_path,
        actual_start, actual_end,
        crossfade_ms=crossfade_ms,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
    )

    breath_processed = False
    if breath_cfg.get("enabled", True):
        try:
            process_breaths(
                raw_clip_path, output_path,
                mode=breath_cfg.get("mode", "reduce"),
                reduction_db=breath_cfg.get("reduction_db", -20),
                min_duration=breath_cfg.get("min_breath_duration", 0.15),
                max_duration=breath_cfg.get("max_breath_duration", 0.8),
            )
            breath_processed = True
        except Exception:
            import shutil
            shutil.copy2(raw_clip_path, output_path)
    else:
        import shutil
        shutil.copy2(raw_clip_path, output_path)

    if raw_clip_path.exists() and raw_clip_path != output_path:
        raw_clip_path.unlink()

    duration_s = actual_end - actual_start

    return AudioProcessResult(
        clip_id=clip.id,
        output_path=str(output_path),
        duration_s=round(duration_s, 2),
        crossfade_applied=True,
        breath_processed=breath_processed,
        fade_in_applied=True,
        fade_out_applied=True,
    )


def process_material_audio(
    source_audio: Path,
    material: MaterialDefinition,
    output_dir: Path,
    config: PipelineConfig,
) -> AudioProcessResult:
    output_path = output_dir / f"{material.id}.wav"
    output_dir.mkdir(parents=True, exist_ok=True)

    start_s = material.start_ms / 1000.0
    end_s = material.end_ms / 1000.0

    filters = [
        f"atrim=start={start_s}:end={end_s}",
        "asetpts=PTS-STARTPTS",
    ]

    if material.material_type == "opening":
        filters.append("afade=t=in:st=0:d=0.03")
        filters.append(f"afade=t=out:st={end_s - start_s - 0.05}:d=0.05")
    elif material.material_type == "ending":
        filters.append("afade=t=in:st=0:d=0.03")
        filters.append(f"afade=t=out:st={end_s - start_s - 0.1}:d=0.1")
    else:
        filters.append("afade=t=in:st=0:d=0.02")
        filters.append(f"afade=t=out:st={end_s - start_s - 0.02}:d=0.02")

    filter_str = ",".join(filters)

    cmd = [
        "ffmpeg", "-y", "-i", str(source_audio),
        "-af", filter_str,
        "-c:a", "pcm_s24le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Material extraction failed: {result.stderr}")

    return AudioProcessResult(
        clip_id=material.id,
        output_path=str(output_path),
        duration_s=round(end_s - start_s, 2),
        fade_in_applied=True,
        fade_out_applied=True,
    )


def process_version_audio(
    source_audio: Path,
    version: VersionPlan,
    output_dir: Path,
    config: PipelineConfig,
) -> list[AudioProcessResult]:
    results = []

    version_dir = output_dir / version.version_key
    slices_dir = version_dir / "slices"
    openings_dir = version_dir / "openings"
    transitions_dir = version_dir / "transitions"
    endings_dir = version_dir / "endings"

    for clip in version.clips:
        result = process_clip_audio(source_audio, clip, slices_dir, config)
        results.append(result)

    for opening in version.openings:
        result = process_material_audio(source_audio, opening, openings_dir, config)
        results.append(result)

    for transition in version.transitions:
        result = process_material_audio(source_audio, transition, transitions_dir, config)
        results.append(result)

    for ending in version.endings:
        result = process_material_audio(source_audio, ending, endings_dir, config)
        results.append(result)

    report_path = version_dir / "audio_process_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)

    return results
