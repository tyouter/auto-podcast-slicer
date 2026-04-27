import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from pipeline.config import PipelineConfig


@dataclass
class NormalizationResult:
    input_path: str
    output_path: str
    input_lufs: float | None = None
    input_tp: float | None = None
    input_lra: float | None = None
    output_lufs: float | None = None
    output_tp: float | None = None
    output_lra: float | None = None
    success: bool = False

    def to_dict(self) -> dict:
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "input": {"lufs": self.input_lufs, "tp": self.input_tp, "lra": self.input_lra},
            "output": {"lufs": self.output_lufs, "tp": self.output_tp, "lra": self.output_lra},
            "success": self.success,
        }


def measure_loudness_detailed(audio_path: Path) -> dict:
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "loudnorm=print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    json_lines = []
    capturing = False
    for line in result.stderr.split("\n"):
        if line.strip() == "{":
            capturing = True
            json_lines = [line]
        elif capturing:
            json_lines.append(line)
            if line.strip() == "}":
                break

    if json_lines:
        try:
            return json.loads("\n".join(json_lines))
        except json.JSONDecodeError:
            pass

    return {}


def normalize_loudness(
    input_path: Path,
    output_path: Path,
    target_lufs: float = -14.0,
    true_peak: float = -1.0,
    max_lra: float = 11.0,
) -> NormalizationResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    first_pass = measure_loudness_detailed(input_path)

    if not first_pass:
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={max_lra}",
            "-c:a", "pcm_s24le",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"Loudness normalization failed: {result.stderr}")

        return NormalizationResult(
            input_path=str(input_path),
            output_path=str(output_path),
            success=True,
        )

    input_i = float(first_pass.get("input_i", 0))
    input_tp = float(first_pass.get("input_tp", 0))
    input_lra = float(first_pass.get("input_lra", 0))
    input_thresh = float(first_pass.get("input_thresh", 0))
    target_offset = float(first_pass.get("target_offset", 0))

    measured_i = float(first_pass.get("input_i", target_lufs))
    measured_tp = float(first_pass.get("input_tp", true_peak))
    measured_lra = float(first_pass.get("input_lra", max_lra))
    measured_thresh = float(first_pass.get("input_thresh", -70))

    linear_filter = (
        f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={max_lra}"
        f":measured_I={measured_i}:measured_TP={measured_tp}"
        f":measured_LRA={measured_lra}:measured_thresh={measured_thresh}"
        f":linear=true"
    )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", linear_filter,
        "-c:a", "pcm_s24le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Two-pass loudness normalization failed: {result.stderr}")

    second_pass = measure_loudness_detailed(output_path)
    output_lufs = float(second_pass.get("input_i", 0)) if second_pass else None
    output_tp = float(second_pass.get("input_tp", 0)) if second_pass else None
    output_lra = float(second_pass.get("input_lra", 0)) if second_pass else None

    return NormalizationResult(
        input_path=str(input_path),
        output_path=str(output_path),
        input_lufs=round(input_i, 1),
        input_tp=round(input_tp, 1),
        input_lra=round(input_lra, 1),
        output_lufs=round(output_lufs, 1) if output_lufs else None,
        output_tp=round(output_tp, 1) if output_tp else None,
        output_lra=round(output_lra, 1) if output_lra else None,
        success=True,
    )


def normalize_for_platform(
    input_path: Path,
    output_path: Path,
    platform: str,
    config: PipelineConfig,
) -> NormalizationResult:
    platform_cfg = config.get_platform_config(platform)
    audio_cfg = platform_cfg.get("audio", {})

    target_lufs = float(audio_cfg.get("target_lufs", -14))
    true_peak = float(audio_cfg.get("true_peak", -1))

    return normalize_loudness(input_path, output_path, target_lufs, true_peak)


def batch_normalize(
    audio_files: list[Path],
    output_dir: Path,
    target_lufs: float = -14.0,
    true_peak: float = -1.0,
) -> list[NormalizationResult]:
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for audio_path in audio_files:
        output_path = output_dir / f"{audio_path.stem}_normalized{audio_path.suffix}"
        try:
            result = normalize_loudness(audio_path, output_path, target_lufs, true_peak)
            results.append(result)
        except Exception as e:
            results.append(NormalizationResult(
                input_path=str(audio_path),
                output_path=str(output_path),
                success=False,
            ))

    return results
