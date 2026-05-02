import re
from dataclasses import dataclass, field
from typing import Optional

from pipeline.text_normalizer import TRADITIONAL_ONLY
from pipeline.subtitle_formatter import (
    check_line_start_rules,
    check_line_end_rules,
    detect_meaningless_words,
    detect_context_anomalies,
)
from pipeline.errata_engine import ErrataConfig


@dataclass
class ContentValidationIssue:
    entry_index: int
    issue_type: str
    severity: str
    description: str
    suggestion: str = ""


@dataclass
class ContentValidationResult:
    total_entries: int = 0
    issues: list[ContentValidationIssue] = field(default_factory=list)
    passed: bool = True
    score: float = 100.0
    accuracy_rate: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def errata_error_count(self) -> int:
        errata_types = {
            "errata_violation", "traditional_chinese", "wrong_name", "wrong_work",
            "asr_phonetic_error", "semantic_anomaly", "contextual_errata",
            "contextual_idiom_errata", "contextual_work_errata",
        }
        return sum(1 for i in self.issues if i.issue_type in errata_types and i.severity == "critical")

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "passed": self.passed,
            "score": round(self.score, 1),
            "accuracy_rate": round(self.accuracy_rate, 4),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "errata_error_count": self.errata_error_count,
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


def validate_simplified_chinese(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        found_traditional = [c for c in text if c in TRADITIONAL_ONLY]
        if found_traditional:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="traditional_chinese_detected",
                severity="critical",
                description=f"发现繁体字: {''.join(found_traditional[:5])}",
                suggestion="转换为简体中文",
            ))
    return issues


def validate_punctuation(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        if re.search(r'[,.!?;:]', text):
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="english_punctuation",
                severity="warning",
                description=f"使用英文标点: {re.findall(r'[,.!?;:]', text)}",
                suggestion="替换为中文标点",
            ))

        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if cn_chars > 8 and not re.search(r'[，。！？、；：]', text):
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="no_punctuation",
                severity="warning",
                description=f"中文字数{cn_chars}字但无标点断句",
                suggestion="根据说话者断句添加标点",
            ))
    return issues


def validate_single_line(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        if '\n' in text:
            lines = text.split('\n')
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="multi_line_subtitle",
                severity="critical",
                description=f"字幕含{len(lines)}行，要求单行",
                suggestion="合并为单行或缩短文本",
            ))
    return issues


def validate_line_length(entries: list[dict], max_chars: int = 18) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").replace('\n', '')
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if cn_chars > max_chars:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_too_long",
                severity="warning",
                description=f"单行{cn_chars}字超过限制{max_chars}字",
                suggestion="缩短文本或拆分",
            ))
    return issues


def validate_errata(entries: list[dict], errata: dict) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        for wrong, correct in errata.items():
            if wrong != correct and wrong in text:
                issues.append(ContentValidationIssue(
                    entry_index=entry.get("index", i),
                    issue_type="errata_violation",
                    severity="critical",
                    description=f"勘误词'{wrong}'应纠正为'{correct}'",
                    suggestion=f"替换'{wrong}'为'{correct}'",
                ))
    return issues


def validate_asr_phonetic(
    entries: list[dict],
    errata: dict,
    patterns: list[tuple[str, str]],
) -> list[ContentValidationIssue]:
    from pipeline.errata_engine import detect_asr_phonetic_errors
    issues = []
    context_window = 3
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue
        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context = " ".join(prev_texts + [text] + next_texts)
        asr_errors = detect_asr_phonetic_errors(text, errata, patterns)
        for err in asr_errors:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="asr_phonetic_error",
                severity="critical",
                description=err["description"],
                suggestion=f"替换'{err['wrong']}'为'{err['correct']}'",
            ))
    return issues


def validate_sentence_by_sentence(
    entries: list[dict],
    semantic_patterns: list[tuple[str, Optional[str], Optional[str]]],
) -> list[ContentValidationIssue]:
    issues = []
    context_window = 3
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue
        for pattern, correction, description in semantic_patterns:
            if correction is None:
                continue
            match = re.search(pattern, text)
            if match:
                issues.append(ContentValidationIssue(
                    entry_index=entry.get("index", i),
                    issue_type="semantic_anomaly",
                    severity="critical",
                    description=f"逐句语义审查：{description}",
                    suggestion=f"替换为'{correction}'",
                ))
    return issues


def validate_context_coherence(entries: list[dict], strip_punctuation: bool = True) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        meaningless = detect_meaningless_words(text)
        for mw in meaningless:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="meaningless_filler",
                severity="warning",
                description=f"发现无意义重复词: '{mw}'",
                suggestion="删除或精简重复词",
            ))

        anomalies = detect_context_anomalies(text, check_punctuation=not strip_punctuation)
        for anomaly in anomalies:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="context_anomaly",
                severity="warning",
                description=anomaly,
                suggestion="检查上下文是否通顺，修正ASR误识别",
            ))
    return issues


def validate_line_break_rules(entries: list[dict]) -> list[ContentValidationIssue]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        start_violations = check_line_start_rules(text)
        for v in start_violations:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_start_forbidden",
                severity="warning",
                description=v,
                suggestion="调整断句避免助词出现在行首",
            ))

        end_violations = check_line_end_rules(text)
        for v in end_violations:
            issues.append(ContentValidationIssue(
                entry_index=entry.get("index", i),
                issue_type="line_end_forbidden",
                severity="warning",
                description=v,
                suggestion="调整断句避免副词/连词出现在行末",
            ))
    return issues


def validate_contextual_errata(
    entries: list[dict],
    errata_config: ErrataConfig,
    context_keywords: dict[str, list[str]] | None = None,
    context_disambiguation: list[dict] | None = None,
) -> list[ContentValidationIssue]:
    issues = []
    context_window = 3
    errata = errata_config.flat_errata

    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue

        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context = " ".join(prev_texts + [text] + next_texts)

        if context_keywords:
            for domain, keywords in context_keywords.items():
                in_context = any(kw in context for kw in keywords)
                if not in_context:
                    continue
                for wrong, correct in errata.items():
                    if wrong != correct and wrong in text and correct not in text:
                        issues.append(ContentValidationIssue(
                            entry_index=entry.get("index", i),
                            issue_type=f"contextual_{domain}_errata",
                            severity="critical",
                            description=f"{domain}语境中勘误：'{wrong}'应为'{correct}'",
                            suggestion=f"替换'{wrong}'为'{correct}'",
                        ))

        if context_disambiguation:
            for rule in context_disambiguation:
                rule_context_words = rule.get("context_words", [])
                rule_corrections = rule.get("corrections", {})
                if any(cw in context for cw in rule_context_words):
                    for wrong, correct in rule_corrections.items():
                        if wrong in text:
                            issues.append(ContentValidationIssue(
                                entry_index=entry.get("index", i),
                                issue_type="contextual_disambiguation",
                                severity="critical",
                                description=f"上下文消歧：'{wrong}'应为'{correct}'",
                                suggestion=f"替换'{wrong}'为'{correct}'",
                            ))

    return issues


def validate_word_level(entries: list[dict], context_window: int = 3) -> list[ContentValidationIssue]:
    from pipeline.word_verifier import verify_entries_word_level
    results = verify_entries_word_level(entries, context_window=context_window)
    issues = []
    for i, result in enumerate(results):
        for wi in result.issues:
            issues.append(ContentValidationIssue(
                entry_index=entries[i].get("index", i + 1),
                issue_type=f"word_level_{wi.issue_type}",
                severity=wi.severity,
                description=f"逐词校验：{wi.description}",
                suggestion=wi.suggestion,
            ))
    return issues


def validate_subtitle_overlap(entries: list[dict]) -> list[ContentValidationIssue]:
    from pipeline.word_verifier import check_subtitle_overlap
    overlap_issues = check_subtitle_overlap(entries)
    issues = []
    for oi in overlap_issues:
        issues.append(ContentValidationIssue(
            entry_index=oi.position + 1,
            issue_type="subtitle_overlap",
            severity="critical",
            description=oi.description,
            suggestion=oi.suggestion,
        ))
    return issues


def validate_subtitle_content(
    entries: list[dict],
    errata_config: ErrataConfig | None = None,
    max_chars: int = 18,
    render_style: dict | None = None,
    strip_punctuation: bool = True,
    enable_word_verify: bool = True,
    enable_overlap_check: bool = True,
    context_keywords: dict[str, list[str]] | None = None,
    context_disambiguation: list[dict] | None = None,
) -> ContentValidationResult:
    if errata_config is None:
        errata_config = ErrataConfig()

    all_issues = []

    all_issues.extend(validate_simplified_chinese(entries))
    if not strip_punctuation:
        all_issues.extend(validate_punctuation(entries))
    all_issues.extend(validate_single_line(entries))
    all_issues.extend(validate_line_length(entries, max_chars))
    all_issues.extend(validate_errata(entries, errata_config.flat_errata))
    all_issues.extend(validate_asr_phonetic(entries, errata_config.flat_errata, errata_config.asr_phonetic_patterns))
    all_issues.extend(validate_sentence_by_sentence(entries, errata_config.semantic_patterns))
    all_issues.extend(validate_context_coherence(entries, strip_punctuation=strip_punctuation))
    all_issues.extend(validate_line_break_rules(entries))
    all_issues.extend(validate_contextual_errata(entries, errata_config, context_keywords, context_disambiguation))

    if enable_word_verify:
        word_issues = validate_word_level(entries)
        all_issues.extend(word_issues)

    if enable_overlap_check:
        overlap_issues = validate_subtitle_overlap(entries)
        all_issues.extend(overlap_issues)

    if render_style:
        from pipeline.subtitle_renderer import validate_render_style
        style_issues = validate_render_style(render_style)
        for si in style_issues:
            all_issues.append(ContentValidationIssue(
                entry_index=0,
                issue_type=si["issue_type"],
                severity=si["severity"],
                description=si["description"],
                suggestion=si["suggestion"],
            ))

    total = len(entries)
    critical = sum(1 for i in all_issues if i.severity == "critical")
    warning = sum(1 for i in all_issues if i.severity == "warning")

    score = max(0, 100 - critical * 15 - min(warning * 0.1, 15))
    passed = critical == 0

    errata_types = {
        "errata_violation", "traditional_chinese", "wrong_name", "wrong_work",
        "asr_phonetic_error", "semantic_anomaly", "contextual_errata",
        "contextual_idiom_errata", "contextual_work_errata",
        "word_level_error", "subtitle_overlap",
    }
    errata_errors = sum(1 for i in all_issues if i.issue_type in errata_types and i.severity == "critical")
    accuracy_rate = ((total - errata_errors) / total * 100) if total > 0 else 100.0
    if accuracy_rate < 99.9 and errata_errors > 0:
        passed = False

    return ContentValidationResult(
        total_entries=total,
        issues=all_issues,
        passed=passed,
        score=score,
        accuracy_rate=accuracy_rate,
    )
