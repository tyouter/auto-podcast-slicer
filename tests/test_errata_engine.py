import pytest
from pathlib import Path
from pipeline.errata_engine import (
    ErrataConfig,
    load_errata_yaml,
    flatten_errata,
    load_asr_phonetic_patterns,
    load_semantic_patterns,
    apply_errata,
    apply_asr_phonetic_corrections,
    detect_asr_phonetic_errors,
    validate_errata_entries,
    validate_semantic_entries,
)

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"
ERRATA_PATH = PROJECT_DIR / "errata.yaml"


class TestErrataConfig:
    def test_from_project_dir(self):
        config = ErrataConfig.from_project_dir(PROJECT_DIR)
        assert config is not None
        assert len(config.flat_errata) > 0
        assert len(config._raw_data) > 0

    def test_from_empty_dir(self, tmp_path):
        config = ErrataConfig.from_project_dir(tmp_path)
        assert config.flat_errata == {}
        assert config.asr_phonetic_patterns == []
        assert config.semantic_patterns == []

    def test_from_dict(self):
        data = {
            "authors": {"博赫斯": "博尔赫斯"},
            "works": {"小径分叉的花园": "小径分岔的花园"},
            "idioms": {"取高贺寡": "曲高和寡"},
        }
        config = ErrataConfig.from_dict(data)
        assert "博赫斯" in config.flat_errata
        assert config.flat_errata["博赫斯"] == "博尔赫斯"
        assert config._raw_data == data


class TestLoadErrataYaml:
    def test_load_existing(self):
        data = load_errata_yaml(ERRATA_PATH)
        assert isinstance(data, dict)
        assert "authors" in data

    def test_load_nonexistent(self):
        data = load_errata_yaml(Path("/nonexistent/errata.yaml"))
        assert data == {}


class TestFlattenErrata:
    def test_flatten(self):
        data = {
            "authors": {"博赫斯": "博尔赫斯"},
            "works": {"小径分叉的花园": "小径分岔的花园"},
            "idioms": {},
            "common": {},
            "variants": {},
            "asr_phonetic": {},
            "asr_noise": {},
        }
        flat = flatten_errata(data)
        assert "博赫斯" in flat
        assert flat["博赫斯"] == "博尔赫斯"

    def test_flatten_empty(self):
        flat = flatten_errata({})
        assert flat == {}


class TestApplyErrata:
    def test_basic_correction(self):
        text = "博赫斯写了一个故事"
        errata = {"博赫斯": "博尔赫斯"}
        result = apply_errata(text, errata)
        assert result == "博尔赫斯写了一个故事"

    def test_no_correction_needed(self):
        text = "博尔赫斯写了一个故事"
        errata = {"博赫斯": "博尔赫斯"}
        result = apply_errata(text, errata)
        assert result == "博尔赫斯写了一个故事"

    def test_empty_errata(self):
        text = "测试文本"
        result = apply_errata(text, {})
        assert result == "测试文本"


class TestApplyAsrPhoneticCorrections:
    def test_basic_correction(self):
        text = "互联码改变了世界"
        errata = {"互联码": "互联网"}
        result = apply_asr_phonetic_corrections(text, errata, [])
        assert "互联网" in result

    def test_with_patterns(self):
        text = "烫化很有趣"
        errata = {}
        patterns = [(r"烫化", "谈话")]
        result = apply_asr_phonetic_corrections(text, errata, patterns)
        assert "谈话" in result


class TestDetectAsrPhoneticErrors:
    def test_detect_error(self):
        text = "博赫斯写了一个故事"
        errata = {"博赫斯": "博尔赫斯"}
        errors = detect_asr_phonetic_errors(text, errata, [])
        assert len(errors) > 0
        assert errors[0]["type"] == "asr_phonetic_error"

    def test_no_errors(self):
        text = "博尔赫斯写了一个故事"
        errata = {"博赫斯": "博尔赫斯"}
        errors = detect_asr_phonetic_errors(text, errata, [])
        assert len(errors) == 0


class TestValidateErrataEntries:
    def test_validate_with_errors(self):
        entries = [{"text": "博赫斯写了一个故事", "index": 1}]
        errata = {"博赫斯": "博尔赫斯"}
        issues = validate_errata_entries(entries, errata)
        assert len(issues) > 0
        assert issues[0]["issue_type"] == "errata_violation"

    def test_validate_no_errors(self):
        entries = [{"text": "博尔赫斯写了一个故事", "index": 1}]
        errata = {"博赫斯": "博尔赫斯"}
        issues = validate_errata_entries(entries, errata)
        assert len(issues) == 0


class TestLoadAsrPhoneticPatterns:
    def test_load_patterns(self):
        data = {
            "asr_phonetic_patterns": [
                {"pattern": "烫化", "replacement": "谈话"},
            ]
        }
        patterns = load_asr_phonetic_patterns(data)
        assert len(patterns) == 1
        assert patterns[0] == ("烫化", "谈话")

    def test_load_empty(self):
        patterns = load_asr_phonetic_patterns({})
        assert patterns == []


class TestLoadSemanticPatterns:
    def test_load_patterns(self):
        data = {
            "semantic_patterns": [
                {"pattern": "暴喜", "correction": "白颊", "description": "暴喜→白颊?"},
            ]
        }
        patterns = load_semantic_patterns(data)
        assert len(patterns) == 1
        assert patterns[0][0] == "暴喜"
        assert patterns[0][1] == "白颊"

    def test_load_empty(self):
        patterns = load_semantic_patterns({})
        assert patterns == []
