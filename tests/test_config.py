import pytest
from pathlib import Path
from pipeline.config import PipelineConfig, load_yaml, deep_merge

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"


class TestPipelineConfig:
    def test_load_default_config(self):
        config = PipelineConfig()
        assert config.pipeline is not None
        assert "pipeline" in config.to_dict()

    def test_load_project_config(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        assert config.project_dir == PROJECT_DIR
        assert config.project_name == "小径分岔的花园"
        assert config.project_description != ""

    def test_project_sources(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        assert config.source_transcript.exists() or config.source_transcript != Path(".")
        assert config.source_audio.exists() or config.source_audio != Path(".")
        assert config.source_video.exists() or config.source_video != Path(".")

    def test_project_clips(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        all_clips = config.get_all_clips()
        assert len(all_clips) > 0
        for series_name, clips in all_clips.items():
            assert isinstance(clips, list)
            for clip in clips:
                assert "id" in clip
                assert "start_s" in clip
                assert "end_s" in clip

    def test_project_errata_config(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        errata = config.errata_config
        assert errata is not None
        assert len(errata.flat_errata) > 0

    def test_project_verification_config(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        verification = config.verification_config
        assert isinstance(verification, dict)
        assert "context_keywords" in verification

    def test_output_dir(self):
        config = PipelineConfig(project_dir=PROJECT_DIR)
        assert config.output_dir is not None

    def test_config_override(self):
        config = PipelineConfig(config_override={"pipeline": {"test_key": "test_value"}})
        assert config.get("pipeline.test_key") == "test_value"

    def test_deep_merge(self):
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 4, "e": 5}, "f": 6}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}, "f": 6}

    def test_get_dotpath(self):
        config = PipelineConfig()
        assert config.get("pipeline.ingest.supported_formats") is not None
        assert config.get("nonexistent.key", "default") == "default"

    def test_platforms(self):
        config = PipelineConfig()
        assert config.platforms is not None

    def test_standards(self):
        config = PipelineConfig()
        assert config.standards is not None

    def test_no_project_dir(self):
        config = PipelineConfig()
        assert config.project_dir is None
        assert config.project_name == ""
        assert config.verification_config == {}


class TestLoadYaml:
    def test_load_existing(self):
        path = PROJECT_ROOT / "config" / "default.yaml"
        data = load_yaml(path)
        assert isinstance(data, dict)
        assert "pipeline" in data

    def test_load_nonexistent(self):
        data = load_yaml(Path("/nonexistent/file.yaml"))
        assert data == {}
