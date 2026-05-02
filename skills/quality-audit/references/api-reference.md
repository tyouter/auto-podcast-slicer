# API Reference — quality-audit

Complete index of quality-checking modules and their callable functions.

## Quality Checker

`pipeline/quality_checker.py`:
- `QualityReport` — Quality report dataclass (overall_score, passed, critical_issues, warnings, recommendations)
- `run_quality_check(output_dir, config, version_key)` — Run full quality check, returns QualityReport
- `check_audio_files(output_dir)` — Audio file integrity and spec check
- `check_subtitle_files(output_dir)` — Subtitle file check (SRT/ASS), including overlap detection, line length, errata coverage
- `check_efficiency(output_dir)` — Generation efficiency check
- `generate_recommendations(report)` — Generate fix recommendations from report

## Content Validator

`pipeline/content_validator.py`:
- `ContentValidationResult` — Validation result (with issues list)
- `validate_simplified_chinese()` — Simplified Chinese validation
- `validate_punctuation()` — Punctuation validation
- `validate_single_line()` — Single line validation
- `validate_line_length()` — Line length validation
- `validate_errata()` — Errata coverage validation
- `validate_asr_phonetic()` — ASR phonetic correction validation
- `validate_sentence_by_sentence()` — Sentence-by-sentence validation
- `validate_context_coherence()` — Context coherence validation
- `validate_line_break_rules()` — Line break rules validation
- `validate_contextual_errata()` — Contextual errata validation
- `validate_word_level()` — Word-level validation
- `validate_subtitle_overlap()` — Subtitle overlap validation (zero tolerance, veto item)
- `validate_subtitle_content()` — Comprehensive content validation entry point

## Loudness Normalizer

`pipeline/loudness_normalizer.py`:
- `measure_loudness_detailed()` — Detailed loudness measurement (LUFS/TruePeak/noise floor)
- `normalize_for_platform()` — Loudness normalization to target platform

## Errata Engine

`pipeline/errata_engine.py`:
- `ErrataConfig` — Errata configuration (loads project-level errata.yaml + framework-level rules)
- `flatten_errata()` — Flatten errata data
- `apply_errata()` — Apply errata corrections
- `apply_asr_phonetic_corrections()` — ASR phonetic corrections
- `detect_asr_phonetic_errors()` — Detect ASR phonetic errors
- `validate_errata_entries()` — Validate errata entries
- `validate_semantic_entries()` — Validate semantic entries

## Configuration Files

- `config/quality_standards.yaml` — Quality standard definitions (subtitle accuracy ≥99.9%, loudness targets, etc.)
- `config/platforms.yaml` — Platform technical specs (resolution, bitrate, LUFS targets)
- `config/default.yaml` — Default pipeline configuration

## Project-Level Configuration

- `projects/{project_name}/errata.yaml` — Project-specific errata (names/works/idioms/common knowledge corrections)
- `projects/{project_name}/project.yaml` — Project configuration
