import pytest
from pathlib import Path
from pipeline.loader import load_project, ProjectContext

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"


class TestLoadProject:
    def test_load_garden_project(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        assert isinstance(ctx, ProjectContext)
        assert ctx.config is not None
        assert ctx.entries is not None
        assert len(ctx.entries) > 0
        assert ctx.config.project_name == "小径分岔的花园"

    def test_load_default(self):
        from pipeline.config import PipelineConfig
        config = PipelineConfig()
        assert config is not None

    def test_project_context_entries(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        for entry in ctx.entries[:5]:
            assert hasattr(entry, "start_ms")
            assert hasattr(entry, "end_ms")
            assert hasattr(entry, "text")

    def test_custom_errata(self):
        ctx = load_project(project_dir=PROJECT_DIR)
        assert ctx.custom_errata is not None
        assert isinstance(ctx.custom_errata, dict)
        assert len(ctx.custom_errata) > 0

    def test_nonexistent_project_dir(self):
        with pytest.raises(FileNotFoundError):
            load_project(project_dir=Path("/nonexistent/project"))
