import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from pipeline.config import PipelineConfig


@dataclass
class AudioIssue:
    issue_type: str
    severity: str
    description: str
    position_s: float = 0.0
    suggestion: str = ""


@dataclass
class AudioVerificationResult:
    file_path: str = ""
    duration_s: float = 0.0
    issues: list[AudioIssue] = field(default_factory=list)
    passed: bool = True
    score: float = 100.0
    loudness_lufs: float | None = None
    true_peak_dbtp: float | None = None
    lra: float | None = None

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "duration_s": round(self.duration_s, 2),
            "passed": self.passed,
            "score": round(self.score, 1),
            "loudness_lufs": self.loudness_lufs,
            "true_peak_dbtp": self.true_peak_dbtp,
            "lra": self.lra,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "description": i.description,
                    "position_s": i.position_s,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
        }


def measure_loudness(audio_path: Path) -> dict:
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "loudnorm=print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    json_match = None
    lines = result.stderr.split("\n")
    json_lines = []
    capturing = False
    for line in lines:
        if line.strip() == "{":
            capturing = True
            json_lines = [line]
        elif capturing:
            json_lines.append(line)
            if line.strip() == "}":
                capturing = False
                json_match = "\n".join(json_lines)
                break

    if json_match:
        try:
            return json.loads(json_match)
        except json.JSONDecodeError:
            pass

    return {}


def check_abrupt_start(audio_path: Path, threshold_db: float = -20) -> list[AudioIssue]:
    issues = []
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", f"astats=metadata=1:reset=0.1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    rms_values = []
    for line in result.stdout.split("\n"):
        if "lavfi.astats.Overall.RMS_level" in line:
            try:
                val = float(line.split("=")[1].strip())
                if val != float("-inf"):
                    rms_values.append(val)
            except (ValueError, IndexError):
                pass

    if rms_values and len(rms_values) > 2:
        first_rms = rms_values[0]
        avg_rms = sum(rms_values[1:5]) / len(rms_values[1:5]) if len(rms_values) > 5 else sum(rms_values) / len(rms_values)

        if first_rms > avg_rms + 15:
            issues.append(AudioIssue(
                issue_type="abrupt_start",
                severity="warning",
                description=f"音频开头突然进入，首段RMS {first_rms:.1f}dB 远高于平均 {avg_rms:.1f}dB",
                position_s=0.0,
                suggestion="增加淡入时间或调整切点至静音处",
            ))

    return issues


def check_abrupt_end(audio_path: Path, threshold_db: float = -20) -> list[AudioIssue]:
    issues = []
    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "areverse,astats=metadata=1:reset=0.1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    rms_values = []
    for line in result.stdout.split("\n"):
        if "lavfi.astats.Overall.RMS_level" in line:
            try:
                val = float(line.split("=")[1].strip())
                if val != float("-inf"):
                    rms_values.append(val)
            except (ValueError, IndexError):
                pass

    if rms_values and len(rms_values) > 2:
        last_rms = rms_values[0]
        avg_rms = sum(rms_values[1:5]) / len(rms_values[1:5]) if len(rms_values) > 5 else sum(rms_values) / len(rms_values)

        if last_rms > avg_rms + 15:
            issues.append(AudioIssue(
                issue_type="abrupt_end",
                severity="warning",
                description=f"音频戛然而止，末段RMS {last_rms:.1f}dB 远高于平均 {avg_rms:.1f}dB",
                position_s=0.0,
                suggestion="增加淡出时间或调整切点至自然停顿处",
            ))

    return issues


def check_loudness_compliance(audio_path: Path, config: PipelineConfig) -> tuple[list[AudioIssue], dict]:
    issues = []
    target_lufs = config.get("pipeline.audio_verification.loudness.target_lufs", -14)
    max_tp = config.get("pipeline.audio_verification.loudness.true_peak_dbtp", -1)
    max_lra = config.get("pipeline.audio_verification.loudness.max_lra", 10)

    measurements = measure_loudness(audio_path)

    measured_i = None
    measured_tp = None
    measured_lra = None

    if measurements:
        measured_i = float(measurements.get("input_i", 0))
        measured_tp = float(measurements.get("input_tp", 0))
        measured_lra = float(measurements.get("input_lra", 0))

        if abs(measured_i - target_lufs) > 2:
            issues.append(AudioIssue(
                issue_type="loudness_out_of_range",
                severity="warning",
                description=f"响度 {measured_i:.1f} LUFS 偏离目标 {target_lufs} LUFS 超过2dB",
                suggestion="进行响度标准化处理",
            ))

        if measured_tp > max_tp:
            issues.append(AudioIssue(
                issue_type="true_peak_exceeded",
                severity="critical",
                description=f"真峰值 {measured_tp:.1f} dBTP 超过限制 {max_tp} dBTP",
                suggestion="应用True Peak限幅器",
            ))

        if measured_lra > max_lra:
            issues.append(AudioIssue(
                issue_type="lra_too_high",
                severity="warning",
                description=f"响度范围 {measured_lra:.1f} LU 超过限制 {max_lra} LU",
                suggestion="压缩动态范围",
            ))

    return issues, {
        "measured_i": measured_i,
        "measured_tp": measured_tp,
        "measured_lra": measured_lra,
    }


def verify_audio(audio_path: Path, config: PipelineConfig) -> AudioVerificationResult:
    if not audio_path.exists():
        return AudioVerificationResult(
            file_path=str(audio_path),
            passed=False,
            score=0,
            issues=[AudioIssue(
                issue_type="file_not_found",
                severity="critical",
                description=f"音频文件不存在: {audio_path}",
            )],
        )

    all_issues = []

    loudness_issues, loudness_data = check_loudness_compliance(audio_path, config)
    all_issues.extend(loudness_issues)

    abrupt_start_issues = check_abrupt_start(audio_path)
    all_issues.extend(abrupt_start_issues)

    abrupt_end_issues = check_abrupt_end(audio_path)
    all_issues.extend(abrupt_end_issues)

    critical = sum(1 for i in all_issues if i.severity == "critical")
    warning = sum(1 for i in all_issues if i.severity == "warning")
    score = max(0, 100 - critical * 15 - warning * 3)
    passed = critical == 0

    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0

    return AudioVerificationResult(
        file_path=str(audio_path),
        duration_s=duration,
        issues=all_issues,
        passed=passed,
        score=score,
        loudness_lufs=loudness_data.get("measured_i"),
        true_peak_dbtp=loudness_data.get("measured_tp"),
        lra=loudness_data.get("measured_lra"),
    )
