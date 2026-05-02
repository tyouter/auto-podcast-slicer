import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from pipeline.text_normalizer import (
    TRADITIONAL_TO_SIMPLIFIED,
    TRADITIONAL_ONLY,
    ZHU_KEEP_COMPOUNDS,
    traditional_to_simplified,
    convert_zhu_to_zhe,
    normalize_chinese,
)
from pipeline.subtitle_formatter import (
    LINE_START_FORBIDDEN,
    LINE_END_FORBIDDEN,
    QUESTION_INDICATORS,
    EXCLAMATION_INDICATORS,
    CONNECTIVE_WORDS,
    PAUSE_PUNCTUATION,
    add_punctuation_smart,
    clean_subtitle_text,
    enforce_single_line,
    format_subtitle_single_line,
    check_line_start_rules,
    check_line_end_rules,
    detect_meaningless_words,
    detect_context_anomalies,
    remove_display_punctuation,
)
from pipeline.subtitle_renderer import (
    COMMERCIAL_FREE_FONTS,
    NON_COMMERCIAL_FONTS,
    generate_ass_with_rounded_bg,
    get_frosted_glass_ffmpeg_filter,
    validate_font_license,
    validate_render_style,
)
from pipeline.errata_engine import (
    ErrataConfig,
    flatten_errata,
    load_errata_yaml,
    apply_errata as _apply_errata_engine,
    apply_asr_phonetic_corrections as _apply_asr_phonetic_engine,
    detect_asr_phonetic_errors as _detect_asr_phonetic_engine,
)
from pipeline.content_validator import (
    ContentValidationIssue,
    ContentValidationResult,
    validate_simplified_chinese,
    validate_punctuation,
    validate_single_line,
    validate_line_length,
    validate_errata as _validate_errata_generic,
    validate_asr_phonetic as _validate_asr_phonetic_generic,
    validate_sentence_by_sentence as _validate_sentence_generic,
    validate_context_coherence,
    validate_line_break_rules,
    validate_contextual_errata as _validate_contextual_errata_generic,
    validate_word_level,
    validate_subtitle_overlap,
    validate_subtitle_content as _validate_subtitle_content_generic,
)


_DEFAULT_ERRATA_CONFIG: ErrataConfig | None = None


def get_default_errata_config() -> ErrataConfig:
    global _DEFAULT_ERRATA_CONFIG
    if _DEFAULT_ERRATA_CONFIG is None:
        _DEFAULT_ERRATA_CONFIG = ErrataConfig()
    return _DEFAULT_ERRATA_CONFIG


def set_default_errata_config(config: ErrataConfig):
    global _DEFAULT_ERRATA_CONFIG
    _DEFAULT_ERRATA_CONFIG = config
    _sync_errata_from_config()


def load_errata_from_project(project_dir: Path) -> ErrataConfig:
    config = ErrataConfig.from_project_dir(project_dir)
    set_default_errata_config(config)
    return config


COMMON_VARIANTS: dict = {}

ERRATA_AUTHORS: dict = {}
ERRATA_WORKS: dict = {}
ERRATA_IDIOMS: dict = {}
ERRATA_COMMON: dict = {}
ERRATA_ASR_PHONETIC: dict = {}
ERRATA_ASR_NOISE: dict = {}
ASR_PHONETIC_PATTERNS: list[tuple[str, str]] = []
SEMANTIC_ANOMALY_PATTERNS: list[tuple] = []


def _sync_errata_from_config():
    config = get_default_errata_config()
    if config and config.flat_errata:
        from pipeline.errata_engine import (
            load_asr_phonetic_patterns,
            load_semantic_patterns,
        )
        raw = getattr(config, '_raw_data', None) or {}
        if raw:
            COMMON_VARIANTS.clear()
            COMMON_VARIANTS.update(raw.get("variants", {}))

            ERRATA_AUTHORS.clear()
            ERRATA_AUTHORS.update(raw.get("authors", {}))

            ERRATA_WORKS.clear()
            ERRATA_WORKS.update(raw.get("works", {}))

            ERRATA_IDIOMS.clear()
            ERRATA_IDIOMS.update(raw.get("idioms", {}))

            ERRATA_COMMON.clear()
            ERRATA_COMMON.update(raw.get("common", {}))

            ERRATA_ASR_PHONETIC.clear()
            ERRATA_ASR_PHONETIC.update(raw.get("asr_phonetic", {}))

            ERRATA_ASR_NOISE.clear()
            ERRATA_ASR_NOISE.update(raw.get("asr_noise", {}))

            ASR_PHONETIC_PATTERNS.clear()
            for item in raw.get("asr_phonetic_patterns", []):
                if isinstance(item, dict) and "pattern" in item and "replacement" in item:
                    ASR_PHONETIC_PATTERNS.append((item["pattern"], item["replacement"]))

            SEMANTIC_ANOMALY_PATTERNS.clear()
            for item in raw.get("semantic_patterns", []):
                if isinstance(item, dict) and "pattern" in item:
                    SEMANTIC_ANOMALY_PATTERNS.append(
                        (item["pattern"], item.get("correction"), item.get("description"))
                    )


def apply_variant_corrections(text: str) -> str:
    for wrong, correct in COMMON_VARIANTS.items():
        text = text.replace(wrong, correct)
    return text


def apply_errata(text: str) -> str:
    all_errata = {}
    all_errata.update(ERRATA_AUTHORS)
    all_errata.update(ERRATA_WORKS)
    all_errata.update(ERRATA_IDIOMS)
    all_errata.update(ERRATA_COMMON)
    all_errata.update(ERRATA_ASR_NOISE)
    return _apply_errata_engine(text, all_errata)


def apply_asr_phonetic_corrections(text: str) -> str:
    return _apply_asr_phonetic_engine(text, ERRATA_ASR_PHONETIC, ASR_PHONETIC_PATTERNS)


def detect_asr_phonetic_errors(text: str, context: str = "") -> list[dict]:
    return _detect_asr_phonetic_engine(text, ERRATA_ASR_PHONETIC, ASR_PHONETIC_PATTERNS)


def load_custom_errata(corrections_path: Path) -> dict:
    if not corrections_path.exists():
        return {}
    import yaml
    with open(corrections_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("corrections", {})


def apply_custom_errata(text: str, errata: dict) -> str:
    return _apply_errata_engine(text, errata)


def normalize_to_simplified_chinese(text: str) -> str:
    text = traditional_to_simplified(text)
    text = apply_variant_corrections(text)
    text = apply_errata(text)
    text = apply_asr_phonetic_corrections(text)
    text = convert_zhu_to_zhe(text)
    return text


def validate_errata(entries: list[dict]) -> list[ContentValidationIssue]:
    all_errata = {}
    all_errata.update(ERRATA_AUTHORS)
    all_errata.update(ERRATA_WORKS)
    all_errata.update(ERRATA_IDIOMS)
    all_errata.update(ERRATA_COMMON)
    return _validate_errata_generic(entries, all_errata)


def validate_asr_phonetic(entries: list[dict]) -> list[ContentValidationIssue]:
    return _validate_asr_phonetic_generic(entries, ERRATA_ASR_PHONETIC, ASR_PHONETIC_PATTERNS)


def validate_sentence_semantic(text: str, context: str = "") -> list[ContentValidationIssue]:
    issues = []
    for pattern, correction, description in SEMANTIC_ANOMALY_PATTERNS:
        if correction is None:
            continue
        match = re.search(pattern, text)
        if match:
            issues.append(ContentValidationIssue(
                entry_index=0,
                issue_type="semantic_anomaly",
                severity="critical",
                description=f"逐句语义审查：{description}",
                suggestion=f"替换为'{correction}'",
            ))
    return issues


def validate_sentence_by_sentence(entries: list[dict]) -> list[ContentValidationIssue]:
    return _validate_sentence_generic(entries, SEMANTIC_ANOMALY_PATTERNS)


_PROJECT_VERIFICATION_CONFIG: dict = {}


def set_project_verification_config(verification: dict):
    global _PROJECT_VERIFICATION_CONFIG
    _PROJECT_VERIFICATION_CONFIG = verification


def validate_contextual_errata(entries: list[dict]) -> list[ContentValidationIssue]:
    context_keywords = _PROJECT_VERIFICATION_CONFIG.get("context_keywords", {})

    return _validate_contextual_errata_generic(
        entries,
        get_default_errata_config(),
        context_keywords=context_keywords,
    )


def validate_subtitle_content(
    entries: list[dict],
    max_chars: int = 18,
    render_style: dict | None = None,
    strip_punctuation: bool = True,
    enable_word_verify: bool = True,
    enable_overlap_check: bool = True,
) -> ContentValidationResult:
    context_keywords = _PROJECT_VERIFICATION_CONFIG.get("context_keywords", {})
    context_disambiguation = _PROJECT_VERIFICATION_CONFIG.get("context_disambiguation", [])

    return _validate_subtitle_content_generic(
        entries,
        errata_config=get_default_errata_config(),
        max_chars=max_chars,
        render_style=render_style,
        strip_punctuation=strip_punctuation,
        enable_word_verify=enable_word_verify,
        enable_overlap_check=enable_overlap_check,
        context_keywords=context_keywords if context_keywords else None,
        context_disambiguation=context_disambiguation if context_disambiguation else None,
    )


def process_subtitle_content(
    text: str,
    duration_s: float = 0,
    next_text: str = '',
    gap_s: float = 0,
    max_chars: int = 18,
    is_last: bool = False,
    custom_errata: dict | None = None,
    strip_punctuation: bool = True,
) -> str:
    text = normalize_to_simplified_chinese(text)
    if custom_errata:
        text = apply_custom_errata(text, custom_errata)
    text = clean_subtitle_text(text)
    text = add_punctuation_smart(text, next_text, duration_s, gap_s, is_last)
    text = enforce_single_line(text)
    text = format_subtitle_single_line(text, max_chars)
    if strip_punctuation:
        text = remove_display_punctuation(text)
    return text


_sync_errata_from_config()
