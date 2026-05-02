import os
import yaml
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class PipelineConfig:
    def __init__(
        self,
        config_override: dict | None = None,
        project_dir: Path | str | None = None,
    ):
        self._data = load_yaml(CONFIG_DIR / "default.yaml")
        self._standards = load_yaml(CONFIG_DIR / "quality_standards.yaml")
        self._platforms = load_yaml(CONFIG_DIR / "platforms.yaml")
        self._clips = load_yaml(CONFIG_DIR / "clips.yaml")
        self._sources = load_yaml(CONFIG_DIR / "sources.yaml")

        self._project_dir: Path | None = None
        self._project_meta: dict = {}
        self._errata_config = None
        self._verification_config: dict = {}

        if project_dir is not None:
            self._project_dir = Path(project_dir)
            self._load_project(self._project_dir)

        if config_override:
            self._data = deep_merge(self._data, config_override)

        self._ensure_output_dirs()

    def _load_project(self, project_dir: Path):
        project_yaml = project_dir / "project.yaml"
        if not project_yaml.exists():
            raise FileNotFoundError(f"project.yaml not found in {project_dir}")

        project_data = load_yaml(project_yaml)
        self._project_meta = project_data

        clips_yaml = project_dir / "clips.yaml"
        if clips_yaml.exists():
            project_clips = load_yaml(clips_yaml)
            if project_clips:
                self._clips = project_clips
        elif "clips" in project_data:
            self._clips = project_data["clips"]

        if "sources" in project_data:
            self._sources = {"sources": project_data["sources"]}

        if "pipeline" in project_data:
            self._data = deep_merge(self._data, {"pipeline": project_data["pipeline"]})

        corrections_path = project_dir / "corrections.yaml"
        if corrections_path.exists():
            self._sources.setdefault("sources", {})
            self._sources["sources"]["corrections"] = str(corrections_path)

        output_base = project_data.get("output", {}).get("base_dir")
        if output_base:
            self._data.setdefault("output", {})
            self._data["output"]["base_dir"] = str(Path(output_base))

        self._errata_config = None
        self._verification_config = project_data.get("verification", {})

    @property
    def errata_config(self):
        if self._errata_config is None and self._project_dir is not None:
            from pipeline.errata_engine import ErrataConfig
            self._errata_config = ErrataConfig.from_project_dir(self._project_dir)
        return self._errata_config

    @property
    def verification_config(self) -> dict:
        return self._verification_config

    @property
    def project_dir(self) -> Path | None:
        return self._project_dir

    @property
    def project_name(self) -> str:
        if self._project_meta:
            return self._project_meta.get("name", "")
        return self._sources.get("sources", {}).get("project", "")

    @property
    def project_description(self) -> str:
        if self._project_meta:
            return self._project_meta.get("description", "")
        return ""

    def _ensure_output_dirs(self):
        base = Path(self.get("output.base_dir", str(OUTPUT_DIR)))
        for subdir in ["clips", "srt", "audio", "video", "reports", "experiments"]:
            (base / subdir).mkdir(parents=True, exist_ok=True)

    def get(self, dotpath: str, default: Any = None) -> Any:
        keys = dotpath.split(".")
        obj = self._data
        for key in keys:
            if isinstance(obj, dict) and key in obj:
                obj = obj[key]
            else:
                return default
        return obj

    def set(self, dotpath: str, value: Any):
        keys = dotpath.split(".")
        obj = self._data
        for key in keys[:-1]:
            if key not in obj or not isinstance(obj[key], dict):
                obj[key] = {}
            obj = obj[key]
        obj[keys[-1]] = value

    @property
    def pipeline(self) -> dict:
        return self._data.get("pipeline", {})

    @property
    def standards(self) -> dict:
        return self._standards

    @property
    def platforms(self) -> dict:
        return self._platforms

    def get_platform_config(self, platform: str) -> dict:
        return self._platforms.get("platforms", {}).get(platform, {})

    @property
    def output_dir(self) -> Path:
        return Path(self.get("output.base_dir", str(OUTPUT_DIR)))

    @property
    def clips(self) -> dict:
        return self._clips

    def get_clips(self, series: str) -> list[dict]:
        return self._clips.get(series, [])

    def get_all_clips(self) -> dict[str, list[dict]]:
        return {k: v for k, v in self._clips.items()}

    @property
    def sources(self) -> dict:
        return self._sources.get("sources", {})

    @property
    def source_transcript(self) -> Path:
        return Path(self.sources.get("transcript", ""))

    @property
    def source_audio(self) -> Path:
        return Path(self.sources.get("audio", ""))

    @property
    def source_video(self) -> Path:
        return Path(self.sources.get("video", ""))

    @property
    def source_corrections(self) -> Path:
        return Path(self.sources.get("corrections", "config/corrections.yaml"))

    def to_dict(self) -> dict:
        return self._data.copy()

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)
