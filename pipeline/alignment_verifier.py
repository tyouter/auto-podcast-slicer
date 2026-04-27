import json
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.transcribe import TranscriptResult, TranscriptSegment


@dataclass
class AlignmentIssue:
    segment_index: int
    issue_type: str
    severity: str
    description: str
    expected: str = ""
    actual: str = ""
    position_s: float = 0.0


@dataclass
class AlignmentReport:
    total_segments: int = 0
    alignment_score: float = 0.0
    coverage_score: float = 0.0
    timing_accuracy_score: float = 0.0
    continuity_score: float = 0.0
    interruption_quality_score: float = 0.0
    issues: list[dict] = field(default_factory=list)
    passed: bool = False
    publishing_ready: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def check_timestamp_continuity(segments: list[TranscriptSegment]) -> list[AlignmentIssue]:
    issues = []
    sorted_segs = sorted(segments, key=lambda s: s.start_ms)

    for i in range(1, len(sorted_segs)):
        prev = sorted_segs[i - 1]
        curr = sorted_segs[i]

        gap_ms = curr.start_ms - prev.end_ms
        overlap_ms = prev.end_ms - curr.start_ms

        if overlap_ms > 0:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="timestamp_overlap",
                severity="critical",
                description=f"时间戳重叠: 前段结束于{prev.end_ms}ms, 后段开始于{curr.start_ms}ms, 重叠{overlap_ms}ms",
                expected="后段开始 >= 前段结束",
                actual=f"重叠 {overlap_ms}ms",
                position_s=prev.end_s,
            ))
        elif gap_ms > 2000:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="large_gap",
                severity="info",
                description=f"时间戳间隔较大: {gap_ms}ms (播客中可能为自然停顿)",
                expected="间隔 < 2000ms",
                actual=f"间隔 {gap_ms}ms",
                position_s=prev.end_s,
            ))
        elif gap_ms > 500:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="moderate_gap",
                severity="info",
                description=f"时间戳间隔: {gap_ms}ms",
                actual=f"间隔 {gap_ms}ms",
                position_s=prev.end_s,
            ))

    return issues


def check_segment_duration_validity(segments: list[TranscriptSegment]) -> list[AlignmentIssue]:
    issues = []
    for i, seg in enumerate(segments):
        duration_ms = seg.end_ms - seg.start_ms
        if duration_ms <= 0:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="zero_or_negative_duration",
                severity="critical",
                description=f"段时长为零或负: start={seg.start_ms}ms, end={seg.end_ms}ms",
                position_s=seg.start_s,
            ))
        elif duration_ms < 500:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="too_short_segment",
                severity="warning",
                description=f"段时长过短: {duration_ms}ms, 文本='{seg.text[:30]}'",
                expected=">= 500ms",
                actual=f"{duration_ms}ms",
                position_s=seg.start_s,
            ))
    return issues


def check_subtitle_audio_synchronization(
    segments: list[TranscriptSegment],
    config: PipelineConfig,
) -> tuple[list[AlignmentIssue], dict]:
    issues = []
    metrics = {
        "total_text_duration_ms": 0,
        "total_audio_duration_ms": 0,
        "coverage_ratio": 0.0,
        "avg_segment_duration_ms": 0,
        "text_to_duration_ratio": 0.0,
    }

    if not segments:
        return issues, metrics

    sorted_segs = sorted(segments, key=lambda s: s.start_ms)
    total_span_ms = sorted_segs[-1].end_ms - sorted_segs[0].start_ms
    total_text_ms = sum(s.end_ms - s.start_ms for s in sorted_segs)

    metrics["total_text_duration_ms"] = total_text_ms
    metrics["total_audio_duration_ms"] = total_span_ms
    metrics["coverage_ratio"] = total_text_ms / total_span_ms if total_span_ms > 0 else 0
    metrics["avg_segment_duration_ms"] = total_text_ms / len(sorted_segs)

    total_chars = sum(len(s.text) for s in sorted_segs)
    total_duration_s = total_text_ms / 1000
    metrics["text_to_duration_ratio"] = total_chars / total_duration_s if total_duration_s > 0 else 0

    if metrics["coverage_ratio"] < 0.85:
        issues.append(AlignmentIssue(
            segment_index=0,
            issue_type="low_coverage",
            severity="warning",
            description=f"字幕覆盖率过低: {metrics['coverage_ratio']*100:.1f}% (目标>=85%)",
            expected=">= 85%",
            actual=f"{metrics['coverage_ratio']*100:.1f}%",
        ))

    if metrics["text_to_duration_ratio"] > 8:
        issues.append(AlignmentIssue(
            segment_index=0,
            issue_type="text_too_dense",
            severity="warning",
            description=f"文本密度过高: {metrics['text_to_duration_ratio']:.1f}字/秒",
            expected="<= 6字/秒",
            actual=f"{metrics['text_to_duration_ratio']:.1f}字/秒",
        ))
    elif metrics["text_to_duration_ratio"] < 1:
        issues.append(AlignmentIssue(
            segment_index=0,
            issue_type="text_too_sparse",
            severity="warning",
            description=f"文本密度过低: {metrics['text_to_duration_ratio']:.1f}字/秒",
            expected=">= 1字/秒",
            actual=f"{metrics['text_to_duration_ratio']:.1f}字/秒",
        ))

    return issues, metrics


def detect_interruptions(segments: list[TranscriptSegment]) -> list[dict]:
    interruptions = []
    sorted_segs = sorted(segments, key=lambda s: s.start_ms)

    for i in range(1, len(sorted_segs)):
        prev = sorted_segs[i - 1]
        curr = sorted_segs[i]

        overlap_ms = prev.end_ms - curr.start_ms
        if overlap_ms > 0:
            prev_text = prev.text.strip()
            curr_text = curr.text.strip()

            prev_ends_incomplete = bool(re.search(r'[，、；：]$', prev_text)) or (
                not re.search(r'[。！？.!?]$', prev_text) and len(prev_text) > 5
            )

            curr_starts_connective = bool(re.match(r'^(但是|不过|可是|其实|然后|所以|而且|就是|对|嗯|啊|不是|你)', curr_text))

            is_interruption = prev_ends_incomplete or curr_starts_connective

            interruptions.append({
                "index": i,
                "prev_end_ms": prev.end_ms,
                "curr_start_ms": curr.start_ms,
                "overlap_ms": overlap_ms,
                "prev_text": prev_text[:50],
                "curr_text": curr_text[:50],
                "prev_incomplete": prev_ends_incomplete,
                "curr_connective": curr_starts_connective,
                "is_interruption": is_interruption,
                "interruption_confidence": "high" if (prev_ends_incomplete and curr_starts_connective) else "medium" if (prev_ends_incomplete or curr_starts_connective) else "low",
            })

    return interruptions


def validate_interruptions(interruptions: list[dict]) -> list[AlignmentIssue]:
    issues = []
    for intr in interruptions:
        if intr["is_interruption"]:
            if intr["interruption_confidence"] == "low":
                issues.append(AlignmentIssue(
                    segment_index=intr["index"],
                    issue_type="unverified_interruption",
                    severity="warning",
                    description=f"疑似打断但置信度低: 前段'{intr['prev_text'][:20]}' → 后段'{intr['curr_text'][:20]}'",
                    position_s=intr["prev_end_ms"] / 1000,
                ))
        else:
            if intr["overlap_ms"] > 500:
                issues.append(AlignmentIssue(
                    segment_index=intr["index"],
                    issue_type="large_overlap_not_interruption",
                    severity="warning",
                    description=f"大范围重叠但非打断: 重叠{intr['overlap_ms']}ms, 前段'{intr['prev_text'][:20]}' → 后段'{intr['curr_text'][:20]}'",
                    position_s=intr["prev_end_ms"] / 1000,
                ))
    return issues


def check_text_timestamp_consistency(segments: list[TranscriptSegment]) -> list[AlignmentIssue]:
    issues = []
    for i, seg in enumerate(segments):
        text = seg.text.strip()
        duration_ms = seg.end_ms - seg.start_ms
        if not text:
            continue

        char_count = len(re.findall(r'[\u4e00-\u9fff]', text))
        if char_count == 0:
            continue

        duration_s = duration_ms / 1000
        if duration_s > 0:
            speed = char_count / duration_s
            if speed > 12:
                issues.append(AlignmentIssue(
                    segment_index=i,
                    issue_type="impossible_speaking_speed",
                    severity="critical",
                    description=f"不可能的语速: {speed:.1f}字/秒, 文本='{text[:30]}', 时长={duration_s:.2f}s",
                    expected="<= 10字/秒",
                    actual=f"{speed:.1f}字/秒",
                    position_s=seg.start_s,
                ))
            elif speed > 8:
                issues.append(AlignmentIssue(
                    segment_index=i,
                    issue_type="fast_speaking_speed",
                    severity="warning",
                    description=f"语速过快: {speed:.1f}字/秒, 文本='{text[:30]}'",
                    expected="<= 8字/秒",
                    actual=f"{speed:.1f}字/秒",
                    position_s=seg.start_s,
                ))
            elif speed < 1 and char_count > 3:
                issues.append(AlignmentIssue(
                    segment_index=i,
                    issue_type="slow_speaking_speed",
                    severity="info",
                    description=f"语速过慢: {speed:.1f}字/秒, 可能时间戳不准确",
                    actual=f"{speed:.1f}字/秒",
                    position_s=seg.start_s,
                ))

    return issues


def check_publishing_standards(segments: list[TranscriptSegment], config: PipelineConfig) -> list[AlignmentIssue]:
    issues = []
    std = config.standards.get("subtitle.srt", {})

    min_display = std.get("min_display_s", 1.0)
    max_display = std.get("max_display_s", 7.0)
    max_chars = std.get("max_chars_per_line_cn", 15)
    max_lines = std.get("max_lines", 2)
    reading_speed = std.get("reading_speed_cn_chars_per_s", 4)

    for i, seg in enumerate(segments):
        duration_s = seg.duration_s
        text = seg.text.strip()

        if duration_s < min_display:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="subtitle_too_short",
                severity="critical",
                description=f"字幕显示时长 {duration_s:.2f}s < 最低 {min_display}s: '{text[:30]}'",
                position_s=seg.start_s,
            ))

        if duration_s > max_display:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="subtitle_too_long",
                severity="warning",
                description=f"字幕显示时长 {duration_s:.2f}s > 最大 {max_display}s: '{text[:30]}'",
                position_s=seg.start_s,
            ))

        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if cn_chars > max_chars * max_lines:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="subtitle_text_too_long",
                severity="warning",
                description=f"字幕文本 {cn_chars}字 > 限制 {max_chars * max_lines}字: '{text[:30]}'",
                position_s=seg.start_s,
            ))

        if duration_s > 0:
            actual_speed = cn_chars / duration_s
            if actual_speed > reading_speed * 1.5:
                issues.append(AlignmentIssue(
                    segment_index=i,
                    issue_type="reading_speed_exceeded",
                    severity="warning",
                    description=f"阅读速度 {actual_speed:.1f}字/秒 > 标准 {reading_speed * 1.5:.1f}字/秒: '{text[:30]}'",
                    position_s=seg.start_s,
                ))

    for i in range(1, len(segments)):
        gap_ms = segments[i].start_ms - segments[i - 1].end_ms
        if gap_ms < -500:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="subtitle_overlap",
                severity="critical",
                description=f"字幕时间重叠过大 {abs(gap_ms)}ms (最大允许500ms)",
                position_s=segments[i].start_s,
            ))
        elif gap_ms < 0:
            issues.append(AlignmentIssue(
                segment_index=i,
                issue_type="subtitle_minor_overlap",
                severity="info",
                description=f"字幕轻微重叠 {abs(gap_ms)}ms (可读性扩展)",
                position_s=segments[i].start_s,
            ))

    return issues


def run_full_alignment_verification(
    transcript: TranscriptResult,
    config: PipelineConfig,
) -> AlignmentReport:
    segments = sorted(transcript.segments, key=lambda s: s.start_ms)
    all_issues = []

    continuity_issues = check_timestamp_continuity(segments)
    all_issues.extend(continuity_issues)

    duration_issues = check_segment_duration_validity(segments)
    all_issues.extend(duration_issues)

    sync_issues, sync_metrics = check_subtitle_audio_synchronization(segments, config)
    all_issues.extend(sync_issues)

    speed_issues = check_text_timestamp_consistency(segments)
    all_issues.extend(speed_issues)

    interruptions = detect_interruptions(segments)
    intr_issues = validate_interruptions(interruptions)
    all_issues.extend(intr_issues)

    publishing_issues = check_publishing_standards(segments, config)
    all_issues.extend(publishing_issues)

    total = len(segments)
    critical = sum(1 for i in all_issues if i.severity == "critical")
    warnings = sum(1 for i in all_issues if i.severity == "warning")

    coverage_score = min(100, sync_metrics.get("coverage_ratio", 0) * 100)

    timing_errors = [i for i in all_issues if i.issue_type in ("timestamp_overlap", "zero_or_negative_duration", "subtitle_overlap")]
    timing_accuracy_score = max(0, 100 - len(timing_errors) * 5)

    continuity_errors = [i for i in all_issues if i.issue_type in ("timestamp_overlap",)]
    continuity_warnings = [i for i in all_issues if i.issue_type == "large_gap"]
    continuity_score = max(0, 100 - len(continuity_errors) * 10 - len(continuity_warnings) * 1)

    valid_interruptions = sum(1 for intr in interruptions if intr["is_interruption"] and intr["interruption_confidence"] in ("high", "medium"))
    total_overlaps = len(interruptions)
    if total_overlaps > 0:
        interruption_quality_score = (valid_interruptions / total_overlaps) * 100
    else:
        interruption_quality_score = 100

    alignment_score = (
        coverage_score * 0.20
        + timing_accuracy_score * 0.35
        + continuity_score * 0.15
        + interruption_quality_score * 0.15
        + (100 - min(100, critical * 5)) * 0.15
    )

    passed = critical == 0
    publishing_ready = (
        critical == 0
        and warnings <= total * 0.10
        and alignment_score >= 85
        and timing_accuracy_score >= 95
        and coverage_score >= 90
    )

    return AlignmentReport(
        total_segments=total,
        alignment_score=round(alignment_score, 1),
        coverage_score=round(coverage_score, 1),
        timing_accuracy_score=round(timing_accuracy_score, 1),
        continuity_score=round(continuity_score, 1),
        interruption_quality_score=round(interruption_quality_score, 1),
        issues=[asdict(i) for i in all_issues],
        passed=passed,
        publishing_ready=publishing_ready,
    )
