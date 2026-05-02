import json
import pytest
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.clip_processor import (
    extract_clip_entries,
    process_clip_subtitles,
    merge_short_entries,
    generate_srt,
    generate_ass,
    write_metadata,
    process_clip,
)
from pipeline.errata_engine import ErrataConfig
from pipeline.content_validator import validate_subtitle_content

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"


class TestProjectIntegration:
    def test_load_and_validate_project(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        assert ctx.config.project_name == "小径分岔的花园"
        assert len(ctx.entries) > 0
        assert len(ctx.custom_errata) > 0

    def test_extract_and_process_entries(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        all_clips = ctx.config.get_all_clips()
        assert len(all_clips) > 0

        first_series = list(all_clips.keys())[0]
        first_clip = all_clips[first_series][0]
        start_s = first_clip["start_s"]
        end_s = first_clip["end_s"]

        clip_entries = extract_clip_entries(ctx.entries, start_s, end_s)
        assert len(clip_entries) > 0

        processed = process_clip_subtitles(clip_entries, ctx.custom_errata)
        assert len(processed) > 0
        for entry in processed:
            assert "text" in entry
            assert "start_s" in entry
            assert "end_s" in entry
            assert entry["start_s"] < entry["end_s"]

    def test_merge_and_validate(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        all_clips = ctx.config.get_all_clips()
        first_series = list(all_clips.keys())[0]
        first_clip = all_clips[first_series][0]

        clip_entries = extract_clip_entries(
            ctx.entries, first_clip["start_s"], first_clip["end_s"]
        )
        processed = process_clip_subtitles(clip_entries, ctx.custom_errata)
        merged = merge_short_entries(processed)

        assert len(merged) > 0
        for i in range(len(merged) - 1):
            assert merged[i]["end_s"] <= merged[i + 1]["start_s"] + 0.05

    def test_srt_generation(self, tmp_path):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好"},
            {"index": 2, "start_s": 2.5, "end_s": 5.0, "text": "世界"},
        ]
        output = tmp_path / "test.srt"
        assert generate_srt(entries, output, skip_existing=False)
        content = output.read_text(encoding="utf-8")
        assert "1\n" in content
        assert "00:00:00,000 --> 00:00:02,000" in content

    def test_ass_generation(self, tmp_path):
        entries = [
            {"index": 1, "start_s": 0.0, "end_s": 2.0, "text": "你好"},
        ]
        output = tmp_path / "test.ass"
        assert generate_ass(entries, output)
        content = output.read_text(encoding="utf-8")
        assert "[Script Info]" in content
        assert "Dialogue:" in content

    def test_metadata_generation(self, tmp_path):
        clip = {
            "id": "test_clip",
            "title": "测试",
            "series": "测试系列",
            "description": "测试描述",
            "start_s": 0.0,
            "end_s": 60.0,
        }
        entries = [{"index": 1, "text": "测试"}]
        assert write_metadata(clip, entries, tmp_path)
        metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["id"] == "test_clip"
        assert metadata["duration_s"] == 60.0

    def test_errata_applied_in_processing(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        all_clips = ctx.config.get_all_clips()
        first_series = list(all_clips.keys())[0]
        first_clip = all_clips[first_series][0]

        clip_entries = extract_clip_entries(
            ctx.entries, first_clip["start_s"], first_clip["end_s"]
        )
        processed = process_clip_subtitles(clip_entries, ctx.custom_errata)

        for entry in processed:
            for wrong, correct in ctx.custom_errata.items():
                assert wrong not in entry["text"], f"Errata not applied: {wrong} found in text"

    def test_content_validation_on_processed_entries(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        all_clips = ctx.config.get_all_clips()
        first_series = list(all_clips.keys())[0]
        first_clip = all_clips[first_series][0]

        clip_entries = extract_clip_entries(
            ctx.entries, first_clip["start_s"], first_clip["end_s"]
        )
        processed = process_clip_subtitles(clip_entries, ctx.custom_errata)
        merged = merge_short_entries(processed)

        result = validate_subtitle_content(merged)
        assert result.accuracy_rate > 0

    def test_project_errata_config(self):
        errata_config = ErrataConfig.from_project_dir(PROJECT_DIR)
        assert len(errata_config.flat_errata) > 0
        assert "博赫斯" in errata_config.flat_errata
        assert errata_config.flat_errata["博赫斯"] == "博尔赫斯"


class TestNewProjectTemplate:
    def test_empty_config_works(self):
        config = PipelineConfig()
        assert config.project_dir is None
        assert config.project_name == ""
        assert len(config.get_all_clips()) == 0

    def test_project_dir_structure(self):
        assert (PROJECT_DIR / "project.yaml").exists()
        assert (PROJECT_DIR / "clips.yaml").exists()
        assert (PROJECT_DIR / "corrections.yaml").exists()
        assert (PROJECT_DIR / "errata.yaml").exists()

    def test_config_sources_empty_by_default(self):
        config = PipelineConfig()
        assert config.source_transcript == Path("")
        assert config.source_audio == Path("")
        assert config.source_video == Path("")
