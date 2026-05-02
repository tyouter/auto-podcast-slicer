# API Reference — video-clip

Complete index of all pipeline modules and their callable functions.

## Video Processing

`pipeline/video_processor.py`:
- `cut_video_clip()` — Video cutting
- `cut_video_with_jl_cut()` — J-Cut/L-Cut
- `compose_clips_with_transitions()` — Multi-clip composition with transitions

## Audio Processing

`pipeline/audio_processor.py`:
- `apply_crossfade()` — Crossfade
- `detect_breaths()` / `process_breaths()` — Breath detection and processing
- `find_nearest_silence()` — Silence point detection
- `optimize_cut_point()` — Smart cut point optimization

`pipeline/loudness_normalizer.py`:
- `normalize_for_platform()` — Loudness normalization to target platform
- `measure_loudness_detailed()` — Detailed loudness measurement (LUFS/TruePeak/noise floor)

## Subtitle Processing

`pipeline/text_normalizer.py`:
- `traditional_to_simplified()` — Traditional to Simplified Chinese
- `convert_zhu_to_zhe()` — 著→着 smart conversion (protects compound words)
- `normalize_chinese()` — Full Chinese text normalization (traditional→simplified + 著→着 + punctuation)

`pipeline/subtitle_formatter.py`:
- `format_subtitle_single_line()` — Single-line subtitle formatting (line breaking, kinsoku, line length control)
- `add_punctuation_smart()` — Smart punctuation addition
- `clean_subtitle_text()` — Subtitle text cleaning
- `enforce_single_line()` — Force single line
- `check_line_start_rules()` / `check_line_end_rules()` — Line start/end kinsoku check
- `detect_meaningless_words()` — Meaningless word detection
- `detect_context_anomalies()` — Context anomaly detection
- `remove_display_punctuation()` — Remove display punctuation

`pipeline/subtitle_renderer.py`:
- `generate_ass_with_rounded_bg()` — Rounded background ASS subtitle rendering
- `get_frosted_glass_ffmpeg_filter()` — Frosted glass ffmpeg filter
- `validate_font_license()` — Font license validation
- `validate_render_style()` — Render style validation

`pipeline/errata_engine.py`:
- `ErrataConfig` — Errata configuration (loads project-level errata.yaml + framework-level correction rules)
- `flatten_errata()` — Flatten errata data
- `apply_errata()` — Apply errata corrections
- `apply_asr_phonetic_corrections()` — ASR phonetic corrections
- `detect_asr_phonetic_errors()` — Detect ASR phonetic errors
- `validate_errata_entries()` — Validate errata entries
- `validate_semantic_entries()` — Validate semantic entries

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
- `validate_subtitle_overlap()` — Subtitle overlap validation (zero tolerance)
- `validate_subtitle_content()` — Comprehensive content validation entry point

`pipeline/subtitle_content.py` — Facade module integrating the above, provides `process_subtitle_content()` high-level interface.

`pipeline/subtitle_merger.py` — Subtitle merge optimization

`pipeline/subtitle_generator.py` — Subtitle generation and clip extraction

## Topic & Planning

`pipeline/topic_analysis.py` — Topic analysis and keyword extraction

`pipeline/clip_planning.py` — Clip planning and version management

## Export & Quality

`pipeline/exporter.py`:
- `export_for_platform()` — Single platform export
- `export_all_platforms()` — Batch multi-platform export
- `export_audio_only()` — Audio-only export

`pipeline/quality_checker.py`:
- `QualityReport` — Quality report dataclass (overall_score, passed, critical_issues, warnings, recommendations)
- `run_quality_check(output_dir, config, version_key)` — Run full quality check
- `check_audio_files(output_dir)` — Audio file integrity and spec check
- `check_subtitle_files(output_dir)` — Subtitle file check (overlap, line length, errata coverage)
- `check_efficiency(output_dir)` — Generation efficiency check
- `generate_recommendations(report)` — Generate fix recommendations from report

## Clip Processing

`pipeline/clip_processor.py`:
- `ClipProcessResult` — Clip processing result dataclass
- `extract_clip_entries()` — Extract clip intervals from transcript entries
- `process_clip_subtitles()` — Clip subtitle processing (errata + normalization + formatting)
- `merge_short_entries()` — Merge short entries
- `generate_audio()` — Generate clip audio (WAV+MP3)
- `generate_ass()` — Generate ASS subtitle file
- `generate_srt()` — Generate SRT subtitle file
- `generate_video_subtitled()` — Generate horizontal subtitled video (with timeout protection)
- `generate_video_vertical()` — Generate vertical video (blurred background fill, with timeout protection)
- `write_metadata()` — Write metadata JSON
- `process_clip()` — Single clip complete processing entry point
- `process_series()` — Batch process entire series

## Project Configuration

- `projects/{project_name}/project.yaml` — Project config (media source + clip definitions)
- `projects/{project_name}/errata.yaml` — Project-level errata (names/works/idioms/common knowledge)
- `projects/{project_name}/clips.yaml` — Project-level clip definitions (optional)

## Framework Configuration

- `config/platforms.yaml` — 6 platform specs (Bilibili/Douyin/YouTube/Podcast/Apple/Archive)
- `config/quality_standards.yaml` — Quality standards (subtitle accuracy ≥99.9%, etc.)
- `config/default.yaml` — Default pipeline configuration
