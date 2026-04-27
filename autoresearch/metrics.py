import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from pipeline.quality_checker import QualityReport
from pipeline.audio_verifier import AudioVerificationResult
from pipeline.subtitle_verifier import SubtitleVerificationResult


@dataclass
class PipelineMetrics:
    audio_quality_score: float = 0.0
    subtitle_quality_score: float = 0.0
    overall_score: float = 0.0
    critical_issue_count: int = 0
    warning_count: int = 0
    passed: bool = False

    audio_lufs_deviation: float = 0.0
    audio_tp_violations: int = 0
    audio_abrupt_start_count: int = 0
    audio_abrupt_end_count: int = 0

    subtitle_timing_violations: int = 0
    subtitle_reading_speed_violations: int = 0
    subtitle_line_length_violations: int = 0
    subtitle_overlap_count: int = 0
    subtitle_errata_violations: int = 0
    subtitle_style_score: float = 0.0

    generation_efficiency_score: float = 0.0
    generation_time_s: float = 0.0
    generation_redundant_count: int = 0

    clip_count: int = 0
    avg_clip_duration_s: float = 0.0
    total_duration_s: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics_from_quality_report(report: QualityReport) -> PipelineMetrics:
    metrics = PipelineMetrics(
        overall_score=report.overall_score,
        critical_issue_count=len(report.critical_issues),
        warning_count=len(report.warnings),
        passed=report.passed,
    )

    audio_scores = []
    for ar in report.audio_results:
        metrics.audio_quality_score += ar.get("score", 0)
        metrics.audio_tp_violations += sum(
            1 for i in ar.get("issues", [])
            if i.get("issue_type") == "true_peak_exceeded"
        )
        metrics.audio_abrupt_start_count += sum(
            1 for i in ar.get("issues", [])
            if i.get("issue_type") == "abrupt_start"
        )
        metrics.audio_abrupt_end_count += sum(
            1 for i in ar.get("issues", [])
            if i.get("issue_type") == "abrupt_end"
        )
        if ar.get("loudness_lufs") is not None:
            metrics.audio_lufs_deviation += abs(ar.get("loudness_lufs", 0) - (-14))

    if report.audio_results:
        metrics.audio_quality_score /= len(report.audio_results)
        metrics.audio_lufs_deviation /= len(report.audio_results)

    if report.subtitle_result:
        metrics.subtitle_quality_score = report.subtitle_result.get("average_score", 0)
        for issue in report.subtitle_result.get("issues", []):
            if issue.get("issue_type") in ("duration_too_short", "duration_too_long"):
                metrics.subtitle_timing_violations += 1
            elif issue.get("issue_type") in ("reading_speed_too_fast", "reading_speed_fast"):
                metrics.subtitle_reading_speed_violations += 1
            elif issue.get("issue_type") == "line_too_long":
                metrics.subtitle_line_length_violations += 1
            elif issue.get("issue_type") == "overlap":
                metrics.subtitle_overlap_count += 1
            elif issue.get("issue_type") in ("errata_violation", "traditional_chinese", "wrong_name", "wrong_work", "asr_phonetic_error", "semantic_anomaly"):
                metrics.subtitle_errata_violations += 1

        metrics.subtitle_style_score = report.subtitle_result.get("style_score", 0)

    if report.efficiency_result:
        metrics.generation_efficiency_score = report.efficiency_result.get("efficiency_score", 0)
        metrics.generation_time_s = report.efficiency_result.get("total_time_s", 0)
        metrics.generation_redundant_count = report.efficiency_result.get("redundant_count", 0)

    return metrics


def compare_metrics(before: PipelineMetrics, after: PipelineMetrics) -> dict:
    def delta(a, b):
        return round(b - a, 2)

    return {
        "overall_score_delta": delta(before.overall_score, after.overall_score),
        "audio_quality_delta": delta(before.audio_quality_score, after.audio_quality_score),
        "subtitle_quality_delta": delta(before.subtitle_quality_score, after.subtitle_quality_score),
        "critical_issues_delta": delta(before.critical_issue_count, after.critical_issue_count),
        "warnings_delta": delta(before.warning_count, after.warning_count),
        "improved": after.overall_score > before.overall_score,
        "regressed": after.overall_score < before.overall_score,
        "passed_before": before.passed,
        "passed_after": after.passed,
    }


def compute_better_than_baseline(metrics: PipelineMetrics, baseline: PipelineMetrics) -> bool:
    if metrics.passed and not baseline.passed:
        return True
    if metrics.overall_score > baseline.overall_score:
        return True
    if metrics.overall_score == baseline.overall_score and metrics.critical_issue_count < baseline.critical_issue_count:
        return True
    return False
