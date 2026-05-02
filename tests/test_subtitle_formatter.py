import pytest
from pipeline.subtitle_formatter import (
    add_punctuation_smart,
    clean_subtitle_text,
    enforce_single_line,
    format_subtitle_single_line,
    check_line_start_rules,
    check_line_end_rules,
    detect_meaningless_words,
    remove_display_punctuation,
    QUESTION_INDICATORS,
    EXCLAMATION_INDICATORS,
)


class TestAddPunctuationSmart:
    def test_already_punctuated(self):
        result = add_punctuation_smart("这是测试。")
        assert result == "这是测试。"

    def test_question_indicator(self):
        result = add_punctuation_smart("你是什么意思")
        assert result.endswith("，") or result.endswith("？") or result.endswith("。")

    def test_empty_text(self):
        assert add_punctuation_smart("") == ""

    def test_exclamation_indicator(self):
        result = add_punctuation_smart("好哇")
        assert "！" in result


class TestCleanSubtitleText:
    def test_removes_extra_spaces(self):
        result = clean_subtitle_text("  测试  文本  ")
        assert "  " not in result

    def test_empty_string(self):
        assert clean_subtitle_text("") == ""


class TestEnforceSingleLine:
    def test_removes_newlines(self):
        result = enforce_single_line("第一行\n第二行")
        assert "\n" not in result

    def test_single_line_unchanged(self):
        text = "单行文本"
        assert enforce_single_line(text) == text


class TestFormatSubtitleSingleLine:
    def test_short_text(self):
        result = format_subtitle_single_line("短文本", max_chars=18)
        assert result == "短文本"

    def test_empty_text(self):
        assert format_subtitle_single_line("", max_chars=18) == ""


class TestCheckLineStartRules:
    def test_valid_start(self):
        violations = check_line_start_rules("这是测试")
        assert len(violations) == 0

    def test_empty_text(self):
        violations = check_line_start_rules("")
        assert len(violations) == 0


class TestCheckLineEndRules:
    def test_valid_end(self):
        violations = check_line_end_rules("这是测试")
        assert len(violations) == 0

    def test_empty_text(self):
        violations = check_line_end_rules("")
        assert len(violations) == 0


class TestDetectMeaninglessWords:
    def test_normal_text(self):
        result = detect_meaningless_words("这是正常文本")
        assert len(result) == 0

    def test_empty_text(self):
        result = detect_meaningless_words("")
        assert len(result) == 0


class TestRemoveDisplayPunctuation:
    def test_removes_punctuation(self):
        result = remove_display_punctuation("测试，文本。")
        assert "，" not in result
        assert "。" not in result

    def test_keeps_text(self):
        result = remove_display_punctuation("测试文本")
        assert result == "测试文本"

    def test_empty_string(self):
        assert remove_display_punctuation("") == ""
