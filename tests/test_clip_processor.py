import pytest
from pathlib import Path
from pipeline.clip_processor import (
    extract_clip_entries,
    process_clip_subtitles,
    merge_short_entries,
    generate_srt,
    ClipProcessResult,
)


class MockEntry:
    def __init__(self, start_ms, end_ms, text):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text


class TestExtractClipEntries:
    def test_basic_extraction(self):
        entries = [
            MockEntry(1000, 3000, "你好"),
            MockEntry(3000, 5000, "世界"),
            MockEntry(5000, 7000, "测试"),
        ]
        result = extract_clip_entries(entries, 1.0, 5.0)
        assert len(result) == 2
        assert result[0]["text"] == "你好"
        assert result[0]["start_s"] == 0.0
        assert result[0]["end_s"] == 2.0

    def test_no_entries_in_range(self):
        entries = [
            MockEntry(10000, 12000, "你好"),
        ]
        result = extract_clip_entries(entries, 1.0, 5.0)
        assert len(result) == 0

    def test_partial_overlap(self):
        entries = [
            MockEntry(3000, 7000, "跨越边界"),
        ]
        result = extract_clip_entries(entries, 4.0, 8.0)
        assert len(result) == 1
        assert result[0]["start_s"] == 0.0
        assert result[0]["end_s"] == 3.0

    def test_empty_entries(self):
        result = extract_clip_entries([], 1.0, 5.0)
        assert len(result) == 0


class TestProcessClipSubtitles:
    def test_basic_processing(self):
        raw = [
            {"start_s": 0.0, "end_s": 2.0, "text": "你好", "duration_s": 2.0},
            {"start_s": 2.5, "end_s": 4.5, "text": "世界", "duration_s": 2.0},
        ]
        result = process_clip_subtitles(raw)
        assert len(result) == 2
        assert result[0]["index"] == 1
        assert result[1]["index"] == 2

    def test_empty_entries(self):
        result = process_clip_subtitles([])
        assert len(result) == 0


class TestMergeShortEntries:
    def test_merge_short_entries(self):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 0.5, "text": "你"},
            {"index": 2, "start_s": 0.5, "end_s": 1.0, "text": "好"},
        ]
        result = merge_short_entries(entries, max_chars=18, min_duration_s=1.0)
        assert len(result) <= 2
        for e in result:
            assert e["end_s"] - e["start_s"] >= 0.5

    def test_no_merge_needed(self):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 3.0, "text": "你好世界"},
            {"index": 2, "start_s": 3.5, "end_s": 6.5, "text": "测试文本"},
        ]
        result = merge_short_entries(entries, max_chars=18, min_duration_s=1.0)
        assert len(result) == 2

    def test_empty_entries(self):
        result = merge_short_entries([], max_chars=18)
        assert len(result) == 0


class TestGenerateSrt:
    def test_basic_srt(self, tmp_path):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好"},
            {"index": 2, "start_s": 2.5, "end_s": 4.5, "text": "世界"},
        ]
        output = tmp_path / "test.srt"
        result = generate_srt(entries, output, skip_existing=False)
        assert result is True
        content = output.read_text(encoding="utf-8")
        assert "1\n" in content
        assert "你好" in content
        assert "世界" in content

    def test_skip_existing(self, tmp_path):
        entries = [{"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好"}]
        output = tmp_path / "test.srt"
        output.write_text("existing", encoding="utf-8")
        result = generate_srt(entries, output, skip_existing=True)
        assert result is True
        assert output.read_text(encoding="utf-8") == "existing"


class TestClipProcessResult:
    def test_to_dict(self):
        r = ClipProcessResult(
            clip_id="test",
            output_dir=Path("/tmp"),
            duration_s=60.0,
            subtitle_count=10,
            audio_wav_ok=True,
            errors=[],
        )
        d = r.to_dict()
        assert d["clip_id"] == "test"
        assert d["duration_s"] == 60.0
        assert d["subtitle_count"] == 10
        assert "errors" not in d

    def test_to_dict_with_errors(self):
        r = ClipProcessResult(
            clip_id="test",
            output_dir=Path("/tmp"),
            duration_s=60.0,
            errors=["something failed"],
        )
        d = r.to_dict()
        assert "errors" in d
        assert d["errors"] == ["something failed"]
