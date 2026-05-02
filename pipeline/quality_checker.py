import json
from pathlib import Path
from dataclasses import dataclass, field
from pipeline.config import PipelineConfig
from pipeline.audio_verifier import verify_audio, AudioVerificationResult
from pipeline.subtitle_verifier import verify_subtitles, SubtitleVerificationResult
from pipeline.subtitle_generator import SubtitleResult


@dataclass
class QualityReport:
    version_key: str = ""
    overall_score: float = 0.0
    passed: bool = False
    audio_results: list[dict] = field(default_factory=list)
    subtitle_result: dict | None = None
    efficiency_result: dict | None = None
    export_results: list[dict] = field(default_factory=list)
    critical_issues: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version_key": self.version_key,
            "overall_score": round(self.overall_score, 1),
            "passed": self.passed,
            "audio_results": self.audio_results,
            "subtitle_result": self.subtitle_result,
            "efficiency_result": self.efficiency_result,
            "export_results": self.export_results,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def check_audio_files(
    audio_dir: Path, config: PipelineConfig
) -> list[dict]:
    results = []
    if not audio_dir.exists():
        return results

    for audio_file in audio_dir.rglob("*.wav"):
        verification = verify_audio(audio_file, config)
        results.append(verification.to_dict())

    for audio_file in audio_dir.rglob("*.mp3"):
        verification = verify_audio(audio_file, config)
        results.append(verification.to_dict())

    return results


def check_subtitle_files(
    srt_dir: Path, config: PipelineConfig
) -> dict | None:
    if not srt_dir.exists():
        return None

    srt_files = list(srt_dir.glob("*.srt")) + list(srt_dir.rglob("*.srt"))
    ass_files = list(srt_dir.glob("*.ass")) + list(srt_dir.rglob("*.ass"))
    sub_files = list(set(srt_files + ass_files))

    if not sub_files:
        return None

    from pipeline.subtitle_generator import SubtitleEntry
    from pipeline.subtitle_content import validate_subtitle_content as validate_content_facade, load_custom_errata

    custom_errata = load_custom_errata(Path("config/corrections.yaml"))

    all_issues = []
    total_entries = 0
    total_score = 0
    errata_violations = 0
    style_score = 95.0

    for sub_file in sub_files:
        try:
            if sub_file.suffix == ".ass":
                entries = parse_ass_file(sub_file)
            else:
                entries = parse_srt_file(sub_file)

            subtitle_result = SubtitleResult(entries=entries, source_file=str(sub_file))
            verification = verify_subtitles(subtitle_result, config)
            total_entries += verification.total_entries
            total_score += verification.score
            all_issues.extend(verification.to_dict()["issues"])

            content_result = validate_content_facade(
                [{"text": e.text, "start_s": e.start_ms / 1000, "end_s": e.end_ms / 1000} for e in entries],
                max_chars=config.get("pipeline.subtitle.max_chars_per_line_cn", 18),
            )
            for issue in content_result.issues:
                if issue.severity in ("critical", "warning"):
                    errata_violations += 1
                    all_issues.append({"source": "subtitle_content", "issue_type": issue.issue_type, "severity": issue.severity, "description": issue.description, "suggestion": issue.suggestion})

            if sub_file.suffix == ".ass":
                with open(sub_file, "r", encoding="utf-8") as f:
                    ass_content = f.read()
                has_border_style_3 = "BorderStyle,3" in ass_content or ",3," in ass_content.split("BorderStyle")[1].split(",")[0:2] if "BorderStyle" in ass_content else False
                has_rounded_bg = "\\p1}" in ass_content and "\\1c&H" in ass_content and "\\1a&H" in ass_content
                if not has_border_style_3 and not has_rounded_bg:
                    style_score -= 5
                if "Noto Sans SC" not in ass_content:
                    style_score -= 10
                if "ScaledBorderAndShadow" not in ass_content:
                    style_score -= 5
        except (OSError, UnicodeDecodeError):
            pass

    if total_entries == 0:
        return None

    avg_score = total_score / max(1, len(sub_files))

    return {
        "total_entries": total_entries,
        "average_score": round(avg_score, 1),
        "style_score": round(max(0, style_score), 1),
        "errata_violations": errata_violations,
        "issues": all_issues,
    }


def parse_srt_file(path: Path) -> list:
    from pipeline.subtitle_generator import SubtitleEntry

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0])
            time_line = lines[1]
            text = "\n".join(lines[2:])

            start_str, end_str = time_line.split(" --> ")
            start_ms = parse_srt_time(start_str.strip())
            end_ms = parse_srt_time(end_str.strip())

            entries.append(SubtitleEntry(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            ))
        except (ValueError, IndexError):
            continue

    return entries


def parse_srt_time(time_str: str) -> int:
    parts = time_str.replace(",", ":").split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2])
    ms = int(parts[3])
    return h * 3600000 + m * 60000 + s * 1000 + ms


def parse_ass_time(time_str: str) -> int:
    parts = time_str.replace(".", ":").split(":")
    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2])
    cs = int(parts[3])
    return h * 3600000 + m * 60000 + s * 1000 + cs * 10


def parse_ass_file(path: Path) -> list:
    from pipeline.subtitle_generator import SubtitleEntry

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    in_events = False
    index = 0
    for line in content.split("\n"):
        line = line.strip()
        if line == "[Events]":
            in_events = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_events = False
            continue
        if not in_events or not line.startswith("Dialogue:"):
            continue

        parts = line.split(",", 9)
        if len(parts) < 10:
            continue

        start_str = parts[1].strip()
        end_str = parts[2].strip()
        text = parts[9].strip()

        import re
        text = re.sub(r"\{[^}]*\}", "", text).strip()
        if not text:
            continue
        if re.match(r"^[mbls]\s", text) or re.match(r"^\d", text):
            continue

        index += 1
        start_ms = parse_ass_time(start_str)
        end_ms = parse_ass_time(end_str)

        entries.append(SubtitleEntry(
            index=index,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
        ))

    return entries


def check_efficiency(output_dir: Path) -> dict | None:
    summary_files = list(output_dir.rglob("summary.json"))
    if not summary_files:
        return None

    total_generated = 0
    total_skipped = 0
    total_time_s = 0.0

    for sf in summary_files:
        try:
            with open(sf, "r", encoding="utf-8") as f:
                data = json.load(f)
            total_generated += data.get("generated_count", data.get("generated", 0))
            total_skipped += data.get("skipped_count", data.get("skipped", 0))
            total_time_s += data.get("total_time_s", 0)
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    total = total_generated + total_skipped
    if total == 0:
        return None

    skip_ratio = total_skipped / total
    efficiency_score = min(100, skip_ratio * 100 + 50)

    redundant_count = 0

    return {
        "total_generated": total_generated,
        "total_skipped": total_skipped,
        "total_time_s": round(total_time_s, 1),
        "skip_ratio": round(skip_ratio, 2),
        "efficiency_score": round(efficiency_score, 1),
        "redundant_count": redundant_count,
    }


def generate_recommendations(
    audio_results: list[dict],
    subtitle_result: dict | None,
    critical_issues: list[dict],
    warnings: list[dict],
) -> list[str]:
    recommendations = []

    loudness_issues = [i for i in critical_issues if i.get("issue_type") in ("loudness_out_of_range", "true_peak_exceeded")]
    if loudness_issues:
        recommendations.append("执行两遍响度标准化（loudnorm），确保符合平台目标LUFS")

    abrupt_issues = [i for i in critical_issues + warnings if i.get("issue_type") in ("abrupt_start", "abrupt_end")]
    if abrupt_issues:
        recommendations.append("调整切点至自然停顿处，增加淡入/淡出时间")

    subtitle_timing_issues = [i for i in critical_issues + warnings if i.get("issue_type") in ("duration_too_short", "overlap", "reading_speed_too_fast")]
    if subtitle_timing_issues:
        recommendations.append("修正字幕时间轴：调整过短字幕、消除重叠、控制阅读速度")

    breath_issues = [i for i in warnings if "breath" in i.get("issue_type", "").lower()]
    if breath_issues:
        recommendations.append("优化呼吸声处理：降低音量至-18~-24dB而非完全删除")

    if not critical_issues and not warnings:
        recommendations.append("所有检查通过，质量达标，可进入发布流程")

    return recommendations


def run_quality_check(
    version_dir: Path,
    config: PipelineConfig,
    version_key: str = "",
) -> QualityReport:
    audio_dir = version_dir / "slices"
    srt_dir = version_dir / "srt"
    video_dir = version_dir / "video"

    if not audio_dir.exists():
        audio_dir = version_dir
    if not srt_dir.exists():
        srt_dir = version_dir

    audio_results = check_audio_files(audio_dir, config)
    subtitle_result = check_subtitle_files(srt_dir, config)
    efficiency_result = check_efficiency(version_dir)

    all_critical = []
    all_warnings = []

    for ar in audio_results:
        for issue in ar.get("issues", []):
            if issue.get("severity") == "critical":
                all_critical.append({"source": "audio", **issue})
            elif issue.get("severity") == "warning":
                all_warnings.append({"source": "audio", **issue})

    if subtitle_result:
        for issue in subtitle_result.get("issues", []):
            if issue.get("severity") == "critical":
                all_critical.append({"source": "subtitle", **issue})
            elif issue.get("severity") == "warning":
                all_warnings.append({"source": "subtitle", **issue})

    audio_score = sum(ar.get("score", 0) for ar in audio_results) / max(1, len(audio_results)) if audio_results else 100
    subtitle_score = subtitle_result.get("average_score", 100) if subtitle_result else 100
    style_score = subtitle_result.get("style_score", 0) if subtitle_result else 0
    eff_score = efficiency_result.get("efficiency_score", 0) if efficiency_result else 0

    overall_score = audio_score * 0.3 + subtitle_score * 0.3 + style_score * 0.2 + eff_score * 0.2
    passed = len(all_critical) == 0 and overall_score >= 90

    recommendations = generate_recommendations(audio_results, subtitle_result, all_critical, all_warnings)

    if subtitle_result and subtitle_result.get("errata_violations", 0) > 0:
        recommendations.append("字幕勘误存在违规：检查人名/作品/成语/常识等错误")

    if style_score < 90:
        recommendations.append("字幕样式不达标：确保BorderStyle=3、Noto Sans SC字体、ScaledBorderAndShadow")

    if eff_score < 90:
        recommendations.append("生成效率不达标：启用skip_existing避免重复处理")

    report = QualityReport(
        version_key=version_key,
        overall_score=overall_score,
        passed=passed,
        audio_results=audio_results,
        subtitle_result=subtitle_result,
        efficiency_result=efficiency_result,
        critical_issues=all_critical,
        warnings=all_warnings,
        recommendations=recommendations,
    )

    report_path = version_dir / "quality_report.json"
    report.save(report_path)

    return report
