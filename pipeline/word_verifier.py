import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WordIssue:
    word: str
    position: int
    issue_type: str
    severity: str
    description: str
    suggestion: str = ""
    confidence: float = 0.0


@dataclass
class WordVerificationResult:
    total_words: int = 0
    issues: list[WordIssue] = field(default_factory=list)
    score: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


WORD_DICT: set[str] = set()
WORD_DICT_LOADED = False
_PROJECT_WORD_DICT_EXTRA: list[str] = []


def set_project_word_dict_extra(words: list[str]):
    global _PROJECT_WORD_DICT_EXTRA, WORD_DICT_LOADED
    _PROJECT_WORD_DICT_EXTRA = words
    WORD_DICT_LOADED = False


def _load_word_dict():
    global WORD_DICT, WORD_DICT_LOADED
    if WORD_DICT_LOADED:
        return
    WORD_DICT_LOADED = True

    from pipeline.subtitle_content import (
        ERRATA_AUTHORS, ERRATA_WORKS, ERRATA_IDIOMS, ERRATA_COMMON,
        ERRATA_ASR_PHONETIC,
    )

    for correct in list(ERRATA_AUTHORS.values()) + list(ERRATA_WORKS.values()) + list(ERRATA_IDIOMS.values()) + list(ERRATA_COMMON.values()) + list(ERRATA_ASR_PHONETIC.values()):
        if correct and len(correct) >= 2:
            WORD_DICT.add(correct)

    for w in _PROJECT_WORD_DICT_EXTRA:
        if len(w) >= 2:
            WORD_DICT.add(w)


def forward_max_match(text: str, word_dict: set[str], max_len: int = 6) -> list[str]:
    words = []
    i = 0
    while i < len(text):
        matched = False
        for length in range(min(max_len, len(text) - i), 1, -1):
            candidate = text[i:i + length]
            if candidate in word_dict:
                words.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            words.append(text[i])
            i += 1
    return words


SWALLOW_CHAR_PATTERNS = [
    (r'(.)\1{2,}', 'repeat_stutter', '疑似口吃/重复：{0}出现3次以上'),
    (r'[\u4e00-\u9fff][啊呃嗯唔哦噢哈呀哇嘛呗]', 'filler_sound', '疑似语气词/含糊音：{0}'),
    (r'什么[教叫要是]', 'asr_confusion', '疑似ASR混淆："什么{1}"可能为"什么叫做/就是"'),
]

CONTEXT_DISAMBIGUATION: list[dict] = []

_PROJECT_CONTEXT_DISAMBIGUATION: list[dict] = []


def set_project_context_disambiguation(rules: list[dict]):
    global CONTEXT_DISAMBIGUATION, _PROJECT_CONTEXT_DISAMBIGUATION
    _PROJECT_CONTEXT_DISAMBIGUATION = rules
    CONTEXT_DISAMBIGUATION.clear()
    CONTEXT_DISAMBIGUATION.extend(rules)

PHONETIC_CONFUSION_GROUPS = [
    {"zh": "z", "ch": "c", "sh": "s"},
    {"n": "l", "l": "n"},
    {"f": "h", "h": "f"},
    {"an": "ang", "ang": "an", "en": "eng", "eng": "en", "in": "ing", "ing": "in"},
]


def _check_phonetic_confusion(word: str, word_dict: set[str]) -> list[tuple[str, float]]:
    candidates = []
    for group in PHONETIC_CONFUSION_GROUPS:
        for wrong, correct in group.items():
            if wrong in word:
                variant = word.replace(wrong, correct)
                if variant in word_dict and variant != word:
                    candidates.append((variant, 0.6))
    return candidates


def verify_word_level(
    text: str,
    context_before: str = "",
    context_after: str = "",
    custom_errata: dict | None = None,
) -> WordVerificationResult:
    _load_word_dict()

    result = WordVerificationResult()
    words = forward_max_match(text, WORD_DICT)
    result.total_words = len(words)

    full_context = f"{context_before} {text} {context_after}".strip()

    pos = 0
    for word in words:
        if len(word) < 2:
            pos += 1
            continue

        if custom_errata:
            for wrong, correct in custom_errata.items():
                if wrong in word and wrong != correct:
                    result.issues.append(WordIssue(
                        word=word, position=pos,
                        issue_type="custom_errata",
                        severity="critical",
                        description=f"自定义勘误：'{wrong}'应为'{correct}'",
                        suggestion=correct,
                        confidence=0.95,
                    ))

        for ctx_rule in CONTEXT_DISAMBIGUATION:
            if any(cw in full_context for cw in ctx_rule["context_words"]):
                for wrong, correct in ctx_rule["corrections"].items():
                    if wrong in text and correct not in text:
                        result.issues.append(WordIssue(
                            word=wrong, position=text.index(wrong),
                            issue_type="contextual_disambiguation",
                            severity="critical",
                            description=f"语境纠错：'{wrong}'应为'{correct}'（上下文含{[w for w in ctx_rule['context_words'] if w in full_context][:3]}）",
                            suggestion=correct,
                            confidence=0.85,
                        ))

        if word not in WORD_DICT and len(word) >= 3:
            candidates = _check_phonetic_confusion(word, WORD_DICT)
            for candidate, conf in candidates:
                result.issues.append(WordIssue(
                    word=word, position=pos,
                    issue_type="phonetic_confusion",
                    severity="warning",
                    description=f"疑似平翘舌/韵母混淆：'{word}'可能为'{candidate}'",
                    suggestion=candidate,
                    confidence=conf,
                ))

        pos += len(word)

    for pattern, issue_type, desc_template in SWALLOW_CHAR_PATTERNS:
        for match in re.finditer(pattern, text):
            matched_text = match.group()
            desc = desc_template.format(matched_text, matched_text[-1] if len(matched_text) > 1 else "")
            result.issues.append(WordIssue(
                word=matched_text, position=match.start(),
                issue_type=issue_type,
                severity="warning",
                description=desc,
                suggestion="",
                confidence=0.5,
            ))

    if result.issues:
        result.score = max(0, 100 - result.critical_count * 10 - result.warning_count * 3)

    return result


def verify_entries_word_level(
    entries: list[dict],
    custom_errata: dict | None = None,
    context_window: int = 3,
) -> list[WordVerificationResult]:
    results = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context_before = " ".join(prev_texts)
        context_after = " ".join(next_texts)

        result = verify_word_level(text, context_before, context_after, custom_errata)
        results.append(result)

    return results


def check_subtitle_overlap(entries: list[dict]) -> list[WordIssue]:
    issues = []
    sorted_entries = sorted(entries, key=lambda e: e.get("start_s", 0))
    for i in range(len(sorted_entries) - 1):
        curr_end = sorted_entries[i].get("end_s", 0)
        next_start = sorted_entries[i + 1].get("start_s", 0)
        if curr_end > next_start:
            overlap = curr_end - next_start
            issues.append(WordIssue(
                word="", position=i,
                issue_type="subtitle_overlap",
                severity="critical",
                description=f"字幕重叠：第{i + 1}条结束于{curr_end:.2f}s，第{i + 2}条开始于{next_start:.2f}s，重叠{overlap:.2f}s",
                suggestion=f"将第{i + 1}条end_s调整为{next_start - 0.04:.2f}s",
                confidence=1.0,
            ))
    return issues
