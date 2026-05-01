import re
from dataclasses import dataclass, field
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.subtitle_generator import SubtitleResult, SubtitleEntry


@dataclass
class SubtitleIssue:
    entry_index: int
    issue_type: str
    severity: str
    description: str
    suggestion: str = ""


@dataclass
class SubtitleVerificationResult:
    total_entries: int = 0
    issues: list[SubtitleIssue] = field(default_factory=list)
    passed: bool = True
    score: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "passed": self.passed,
            "score": round(self.score, 1),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "entry_index": i.entry_index,
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "description": i.description,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
        }


def check_display_duration(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleIssue]:
    min_display = config.get("pipeline.subtitle.min_display_duration", 1.0)
    max_display = config.get("pipeline.subtitle.max_display_duration", 7.0)

    issues = []
    for entry in entries:
        duration = entry.duration_s
        if duration < min_display:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="duration_too_short",
                severity="warning",
                description=f"显示时长 {duration:.2f}s 低于建议 {min_display}s",
                suggestion=f"延长至 {min_display}s 或合并到相邻字幕",
            ))
        elif duration > max_display:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="duration_too_long",
                severity="warning",
                description=f"显示时长 {duration:.2f}s 超过最大限制 {max_display}s",
                suggestion="拆分为多条字幕",
            ))

    return issues


def check_reading_speed(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleIssue]:
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)

    issues = []
    for entry in entries:
        text_clean = entry.text.replace("\n", "")
        char_count = len(re.findall(r'[\u4e00-\u9fff]', text_clean))
        if char_count == 0:
            continue

        actual_speed = char_count / entry.duration_s if entry.duration_s > 0 else 999
        if actual_speed > reading_speed * 2.0:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="reading_speed_too_fast",
                severity="critical",
                description=f"阅读速度 {actual_speed:.1f} 字/秒 超过标准 {reading_speed} 字/秒的2倍",
                suggestion="缩短文本或延长显示时间",
            ))
        elif actual_speed > reading_speed * 1.5:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="reading_speed_fast",
                severity="warning",
                description=f"阅读速度 {actual_speed:.1f} 字/秒 超过标准 {reading_speed} 字/秒的1.5倍",
                suggestion="考虑优化文本长度",
            ))

    return issues


def check_line_length(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleIssue]:
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 18)
    max_lines = config.get("pipeline.subtitle.max_lines", 1)

    issues = []
    for entry in entries:
        lines = entry.text.split("\n")
        if len(lines) > max_lines:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="too_many_lines",
                severity="warning",
                description=f"字幕行数 {len(lines)} 超过限制 {max_lines}",
                suggestion="精简文本或重新分行",
            ))

        for line_idx, line in enumerate(lines):
            cn_chars = len(re.findall(r'[\u4e00-\u9fff]', line))
            if cn_chars > max_chars:
                issues.append(SubtitleIssue(
                    entry_index=entry.index,
                    issue_type="line_too_long",
                    severity="warning",
                    description=f"第{line_idx + 1}行 {cn_chars} 字 超过限制 {max_chars} 字",
                    suggestion="缩短该行或拆分",
                ))

    return issues


def check_gap_duration(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleIssue]:
    min_gap = config.get("pipeline.subtitle.min_gap_duration", 0.067)

    issues = []
    for i in range(1, len(entries)):
        gap_ms = entries[i].start_ms - entries[i - 1].end_ms
        gap_s = gap_ms / 1000.0

        if gap_s < 0:
            issues.append(SubtitleIssue(
                entry_index=entries[i].index,
                issue_type="overlap",
                severity="critical",
                description=f"与第{entries[i - 1].index}条字幕时间重叠 {abs(gap_s):.3f}s",
                suggestion="调整时间轴消除重叠",
            ))
        elif gap_s < min_gap:
            issues.append(SubtitleIssue(
                entry_index=entries[i].index,
                issue_type="gap_too_short",
                severity="info",
                description=f"与上一条间隔 {gap_s:.3f}s 低于建议 {min_gap}s（连续语音可接受）",
                suggestion="增加间隔或合并字幕",
            ))

    return issues


def check_text_quality(entries: list[SubtitleEntry]) -> list[SubtitleIssue]:
    issues = []
    for entry in entries:
        text = entry.text.strip()
        if not text:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="empty_text",
                severity="critical",
                description="字幕文本为空",
                suggestion="删除空字幕或补充文本",
            ))
            continue

        if len(text) > 100:
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="text_too_long",
                severity="warning",
                description=f"单条字幕文本过长 ({len(text)}字)",
                suggestion="拆分为多条字幕",
            ))

        if re.search(r'[\u4e00-\u9fff]{30,}', text):
            issues.append(SubtitleIssue(
                entry_index=entry.index,
                issue_type="no_punctuation",
                severity="warning",
                description="长文本缺少标点断句",
                suggestion="在适当位置添加标点",
            ))

    return issues


def verify_subtitles(
    subtitle_result: SubtitleResult, config: PipelineConfig
) -> SubtitleVerificationResult:
    entries = subtitle_result.entries
    all_issues = []

    all_issues.extend(check_display_duration(entries, config))
    all_issues.extend(check_reading_speed(entries, config))
    all_issues.extend(check_line_length(entries, config))
    all_issues.extend(check_gap_duration(entries, config))
    all_issues.extend(check_text_quality(entries))
    all_issues.extend(check_word_level(entries, config))
    all_issues.extend(check_overlap(entries))

    total = len(entries)
    critical = sum(1 for i in all_issues if i.severity == "critical")
    warning = sum(1 for i in all_issues if i.severity == "warning")

    score = max(0, 100 - critical * 15 - warning * 2)
    passed = critical == 0

    return SubtitleVerificationResult(
        total_entries=total,
        issues=all_issues,
        passed=passed,
        score=score,
    )


def check_word_level(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleIssue]:
    from pipeline.word_verifier import verify_entries_word_level
    entry_dicts = [
        {"text": e.text, "start_s": e.start_ms / 1000, "end_s": e.end_ms / 1000}
        for e in entries
    ]
    results = verify_entries_word_level(entry_dicts)
    issues = []
    for i, result in enumerate(results):
        for wi in result.issues:
            issues.append(SubtitleIssue(
                entry_index=entries[i].index,
                issue_type=f"word_level_{wi.issue_type}",
                severity=wi.severity,
                description=f"逐词校验：{wi.description}",
                suggestion=wi.suggestion,
            ))
    return issues


def check_overlap(entries: list[SubtitleEntry]) -> list[SubtitleIssue]:
    from pipeline.word_verifier import check_subtitle_overlap
    entry_dicts = [
        {"text": e.text, "start_s": e.start_ms / 1000, "end_s": e.end_ms / 1000}
        for e in entries
    ]
    overlap_issues = check_subtitle_overlap(entry_dicts)
    issues = []
    for oi in overlap_issues:
        issues.append(SubtitleIssue(
            entry_index=oi.position + 1,
            issue_type="subtitle_overlap",
            severity="critical",
            description=oi.description,
            suggestion=oi.suggestion,
        ))
    return issues
