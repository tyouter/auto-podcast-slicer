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
    word_level_error_count: int = 0

    subtitle_style_extraction_score: float = 0.0
    vertical_overlay_aspect_compliant: bool = True
    vertical_style_completeness: float = 0.0

    alignment_score: float = 0.0
    alignment_coverage_score: float = 0.0
    alignment_timing_accuracy: float = 0.0
    alignment_continuity_score: float = 0.0

    loudness_normalization_pass: bool = True
    loudness_lufs_deviation: float = 0.0

    generation_efficiency_score: float = 0.0
    generation_time_s: float = 0.0
    generation_redundant_count: int = 0

    subtitle_semantic_completeness: float = 100.0
    subtitle_multiline_compliance: float = 100.0
    subtitle_visual_bounds_score: float = 100.0
    subtitle_font_size_score: float = 100.0
    subtitle_filler_cleanup_score: float = 100.0
    subtitle_fragment_count: int = 0

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
            elif issue.get("issue_type") == "subtitle_overlap":
                metrics.subtitle_overlap_count += 1
            elif issue.get("issue_type", "").startswith("word_level_"):
                # Exclude filler_sound from error count — it's natural spoken style
                if issue.get("issue_type") != "word_level_filler_sound":
                    metrics.word_level_error_count += 1
            elif issue.get("issue_type") in ("errata_violation", "traditional_chinese", "wrong_name", "wrong_work", "asr_phonetic_error", "semantic_anomaly"):
                metrics.subtitle_errata_violations += 1

        metrics.subtitle_style_score = report.subtitle_result.get("style_score", 0)

    if report.alignment_result:
        metrics.alignment_score = report.alignment_result.get("alignment_score", 0)
        metrics.alignment_coverage_score = report.alignment_result.get("coverage_score", 0)
        metrics.alignment_timing_accuracy = report.alignment_result.get("timing_accuracy_score", 0)
        metrics.alignment_continuity_score = report.alignment_result.get("continuity_score", 0)

    if report.style_extraction_result:
        metrics.subtitle_style_extraction_score = report.style_extraction_result.get("score", 0)
        metrics.vertical_overlay_aspect_compliant = report.style_extraction_result.get("vertical_overlay_aspect_compliant", True)
        metrics.vertical_style_completeness = report.style_extraction_result.get("vertical_style_completeness", 0)

    if report.loudness_result:
        metrics.loudness_normalization_pass = report.loudness_result.get("passed", True)
        metrics.loudness_lufs_deviation = report.loudness_result.get("lufs_deviation", 0)

    if report.efficiency_result:
        metrics.generation_efficiency_score = report.efficiency_result.get("efficiency_score", 0)
        metrics.generation_time_s = report.efficiency_result.get("total_time_s", 0)
        metrics.generation_redundant_count = report.efficiency_result.get("redundant_count", 0)

    # Compute new subtitle quality metrics from subtitle_result issues
    if report.subtitle_result:
        issues = report.subtitle_result.get("issues", [])
        total = report.subtitle_result.get("total_entries", 0)

        # Semantic completeness: percentage of entries without truncation issues
        truncated = sum(1 for i in issues if i.get("issue_type") in ("line_start_forbidden", "line_end_forbidden", "suspected_fragment"))
        metrics.subtitle_semantic_completeness = round(((total - truncated) / total * 100) if total > 0 else 100, 1)

        # Multiline compliance: percentage of entries within line limits
        multiline_violations = sum(1 for i in issues if i.get("issue_type") in ("multi_line_subtitle", "too_many_lines", "line_too_long"))
        metrics.subtitle_multiline_compliance = round(((total - multiline_violations) / total * 100) if total > 0 else 100, 1)

        # Visual bounds score: based on style_score
        metrics.subtitle_visual_bounds_score = report.subtitle_result.get("style_score", 100)

        # Font size score: based on style presence
        metrics.subtitle_font_size_score = 90 if report.subtitle_result.get("style_score", 0) > 80 else 60

        # Filler cleanup score: percentage without meaningless fillers
        filler_issues = sum(1 for i in issues if i.get("issue_type") in ("meaningless_filler", "word_level_filler_sound"))
        metrics.subtitle_filler_cleanup_score = round(((total - filler_issues) / total * 100) if total > 0 else 100, 1)

        # Fragment count: suspected_fragment + truncated subtitles
        fragment_types = ("suspected_fragment", "truncated_subtitle")
        metrics.subtitle_fragment_count = sum(
            1 for i in issues if i.get("issue_type") in fragment_types
        )

    return metrics


def compare_metrics(before: PipelineMetrics, after: PipelineMetrics) -> dict:
    def delta(a, b):
        return round(b - a, 2)

    # Multi-dimensional improvement: consistent with compute_better_than_baseline
    IMPROVEMENT_THRESHOLD = 0.5
    improved = (
        (after.passed and not before.passed)
        or (after.overall_score - before.overall_score) >= IMPROVEMENT_THRESHOLD
        or (abs(after.overall_score - before.overall_score) < IMPROVEMENT_THRESHOLD
            and after.critical_issue_count < before.critical_issue_count)
        or (after.subtitle_fragment_count < before.subtitle_fragment_count
            and after.overall_score >= before.overall_score - 0.1)
    )
    regressed = (
        (before.passed and not after.passed)
        or after.overall_score < before.overall_score
    )

    return {
        "overall_score_delta": delta(before.overall_score, after.overall_score),
        "audio_quality_delta": delta(before.audio_quality_score, after.audio_quality_score),
        "subtitle_quality_delta": delta(before.subtitle_quality_score, after.subtitle_quality_score),
        "critical_issues_delta": delta(before.critical_issue_count, after.critical_issue_count),
        "warnings_delta": delta(before.warning_count, after.warning_count),
        "style_extraction_delta": delta(before.subtitle_style_extraction_score, after.subtitle_style_extraction_score),
        "alignment_score_delta": delta(before.alignment_score, after.alignment_score),
        "vertical_compliance_maintained": after.vertical_overlay_aspect_compliant,
        "loudness_normalization_maintained": after.loudness_normalization_pass,
        "subtitle_semantic_completeness_delta": delta(before.subtitle_semantic_completeness, after.subtitle_semantic_completeness),
        "subtitle_multiline_compliance_delta": delta(before.subtitle_multiline_compliance, after.subtitle_multiline_compliance),
        "subtitle_visual_bounds_delta": delta(before.subtitle_visual_bounds_score, after.subtitle_visual_bounds_score),
        "subtitle_font_size_delta": delta(before.subtitle_font_size_score, after.subtitle_font_size_score),
        "subtitle_filler_cleanup_delta": delta(before.subtitle_filler_cleanup_score, after.subtitle_filler_cleanup_score),
        "subtitle_fragment_delta": delta(before.subtitle_fragment_count, after.subtitle_fragment_count),
        "improved": improved,
        "regressed": regressed,
        "passed_before": before.passed,
        "passed_after": after.passed,
    }


def compute_better_than_baseline(metrics: PipelineMetrics, baseline: PipelineMetrics) -> bool:
    IMPROVEMENT_THRESHOLD = 0.5
    if metrics.passed and not baseline.passed:
        return True
    if (metrics.overall_score - baseline.overall_score) >= IMPROVEMENT_THRESHOLD:
        return True
    if (metrics.subtitle_fragment_count < baseline.subtitle_fragment_count
            and metrics.overall_score >= baseline.overall_score - 0.1):
        return True
    if (abs(metrics.overall_score - baseline.overall_score) < IMPROVEMENT_THRESHOLD
            and metrics.critical_issue_count < baseline.critical_issue_count):
        return True
    return False
