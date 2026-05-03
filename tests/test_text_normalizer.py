import pytest
from pipeline.text_normalizer import (
    traditional_to_simplified,
    convert_zhu_to_zhe,
    normalize_chinese,
    ZHU_KEEP_COMPOUNDS,
)


class TestTraditionalToSimplified:
    def test_basic_conversion(self):
        result = traditional_to_simplified("書籍")
        assert "书" in result

    def test_mixed_text(self):
        result = traditional_to_simplified("這是一本書")
        assert "这" in result
        assert "书" in result

    def test_already_simplified(self):
        text = "这是一本书"
        result = traditional_to_simplified(text)
        assert result == text

    def test_empty_string(self):
        assert traditional_to_simplified("") == ""


class TestConvertZhuToZhe:
    def test_basic_conversion(self):
        result = convert_zhu_to_zhe("他看著書")
        assert "着" in result
        assert "著" not in result

    def test_keep_compounds(self):
        text = "他是著名的作家"
        result = convert_zhu_to_zhe(text)
        assert "著名" in result
        assert "着名" not in result

    def test_empty_string(self):
        assert convert_zhu_to_zhe("") == ""


class TestNormalizeChinese:
    def test_full_pipeline(self):
        result = normalize_chinese("他看著書")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_string(self):
        assert normalize_chinese("") == ""
