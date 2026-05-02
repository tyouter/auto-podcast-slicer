import pytest
from pathlib import Path
from pipeline.content_validator import (
    validate_simplified_chinese,
    validate_punctuation,
    validate_single_line,
    validate_line_length,
    validate_errata,
    validate_subtitle_overlap,
    validate_subtitle_content,
    validate_contextual_errata,
    ContentValidationIssue,
    ContentValidationResult,
)

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"


class TestValidateSimplifiedChinese:
    def test_simplified_text(self):
        entries = [{"index": 1, "text": "你好世界"}]
        issues = validate_simplified_chinese(entries)
        assert isinstance(issues, list)

    def test_empty_entries(self):
        issues = validate_simplified_chinese([])
        assert isinstance(issues, list)


class TestValidatePunctuation:
    def test_valid_punctuation(self):
        entries = [{"index": 1, "text": "你好世界"}]
        issues = validate_punctuation(entries)
        assert isinstance(issues, list)

    def test_empty_entries(self):
        issues = validate_punctuation([])
        assert isinstance(issues, list)


class TestValidateSingleLine:
    def test_single_line(self):
        entries = [{"index": 1, "text": "你好世界"}]
        issues = validate_single_line(entries)
        assert isinstance(issues, list)

    def test_multi_line(self):
        entries = [{"index": 1, "text": "第一行\n第二行"}]
        issues = validate_single_line(entries)
        assert len(issues) > 0


class TestValidateLineLength:
    def test_short_line(self):
        entries = [{"index": 1, "text": "你好"}]
        issues = validate_line_length(entries, max_chars=18)
        assert isinstance(issues, list)

    def test_long_line(self):
        entries = [{"index": 1, "text": "这是一个非常非常非常非常非常非常非常长的字幕文本"}]
        issues = validate_line_length(entries, max_chars=18)
        assert len(issues) > 0


class TestValidateErrata:
    def test_with_errata(self):
        entries = [{"index": 1, "text": "博赫斯是伟大的作家"}]
        errata = {"博赫斯": "博尔赫斯"}
        issues = validate_errata(entries, errata)
        assert len(issues) > 0

    def test_no_errata_violations(self):
        entries = [{"index": 1, "text": "博尔赫斯是伟大的作家"}]
        errata = {"博赫斯": "博尔赫斯"}
        issues = validate_errata(entries, errata)
        assert len(issues) == 0


class TestValidateSubtitleOverlap:
    def test_overlapping(self):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 3.0, "text": "你好"},
            {"index": 2, "start_s": 2.5, "end_s": 5.0, "text": "世界"},
        ]
        issues = validate_subtitle_overlap(entries)
        assert len(issues) > 0

    def test_non_overlapping(self):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好"},
            {"index": 2, "start_s": 2.5, "end_s": 5.0, "text": "世界"},
        ]
        issues = validate_subtitle_overlap(entries)
        assert len(issues) == 0


class TestValidateSubtitleContent:
    def test_basic_validation(self):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好世界"},
        ]
        result = validate_subtitle_content(entries)
        assert isinstance(result, ContentValidationResult)

    def test_empty_entries(self):
        result = validate_subtitle_content([])
        assert isinstance(result, ContentValidationResult)


class TestValidateContextualErrata:
    def test_with_context_keywords(self):
        from pipeline.errata_engine import ErrataConfig
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "博尔赫斯是伟大的作家"},
        ]
        errata_config = ErrataConfig.from_project_dir(PROJECT_DIR)
        context_keywords = {"literature": ["博尔赫斯", "文学"]}
        issues = validate_contextual_errata(entries, errata_config, context_keywords)
        assert isinstance(issues, list)

    def test_without_keywords(self):
        from pipeline.errata_engine import ErrataConfig
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "测试文本"},
        ]
        errata_config = ErrataConfig.from_project_dir(PROJECT_DIR)
        issues = validate_contextual_errata(entries, errata_config)
        assert isinstance(issues, list)
