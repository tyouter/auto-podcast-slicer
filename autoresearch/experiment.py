import json
import copy
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from pipeline.config import PipelineConfig
from autoresearch.metrics import PipelineMetrics, compute_metrics_from_quality_report, compare_metrics, compute_better_than_baseline
from pipeline.quality_checker import QualityReport

_SENTINEL = object()


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: str
    direction: str
    config_snapshot: dict
    metrics_before: dict | None = None
    metrics_after: dict | None = None
    comparison: dict | None = None
    improved: bool = False
    kept: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ExperimentLog:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "experiment_log.json"
        self.records: list[ExperimentRecord] = self._load()

    def _load(self) -> list[ExperimentRecord]:
        if not self.log_file.exists():
            return []
        with open(self.log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ExperimentRecord(**r) for r in data]

    def save(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self.records], f, ensure_ascii=False, indent=2)

    def add(self, record: ExperimentRecord):
        self.records.append(record)
        self.save()

    def get_latest(self) -> ExperimentRecord | None:
        return self.records[-1] if self.records else None

    def get_improvements(self) -> list[ExperimentRecord]:
        return [r for r in self.records if r.improved]

    def get_regressions(self) -> list[ExperimentRecord]:
        return [r for r in self.records if not r.improved and r.comparison is not None]

    def summary(self) -> dict:
        total = len(self.records)
        improved = len(self.get_improvements())
        regressed = len(self.get_regressions())
        kept = sum(1 for r in self.records if r.kept)

        return {
            "total_experiments": total,
            "improvements": improved,
            "regressions": regressed,
            "kept_changes": kept,
            "discarded_changes": total - kept,
            "improvement_rate": round(improved / max(1, total) * 100, 1),
        }


class Experiment:
    def __init__(
        self,
        config: PipelineConfig,
        log_dir: Path,
        direction: str = "general_quality",
    ):
        self.config = config
        self.log = ExperimentLog(log_dir)
        self.direction = direction
        self.baseline_metrics: PipelineMetrics | None = None
        self.current_metrics: PipelineMetrics | None = None
        self.experiment_count = 0

    def set_baseline(self, report: QualityReport):
        self.baseline_metrics = compute_metrics_from_quality_report(report)
        self.current_metrics = self.baseline_metrics

    def run_experiment(
        self,
        config_modifications: dict,
        quality_report_fn,
        notes: str = "",
    ) -> ExperimentRecord:
        self.experiment_count += 1
        experiment_id = f"exp_{self.experiment_count:04d}_{int(time.time())}"
        timestamp = datetime.now().isoformat()

        config_before = copy.deepcopy(self.config.to_dict())

        # Validate config paths exist before applying
        invalid_paths = []
        for dotpath in config_modifications:
            current_val = self.config.get(dotpath, _SENTINEL)
            if current_val is _SENTINEL:
                invalid_paths.append(dotpath)
        if invalid_paths:
            record = ExperimentRecord(
                experiment_id=experiment_id,
                timestamp=timestamp,
                direction=self.direction,
                config_snapshot=config_modifications,
                notes=f"VALIDATION FAILED: unknown config paths: {invalid_paths}",
                improved=False,
                kept=False,
            )
            self.log.add(record)
            return record

        for dotpath, value in config_modifications.items():
            self.config.set(dotpath, value)

        try:
            new_report = quality_report_fn(self.config)
            new_metrics = compute_metrics_from_quality_report(new_report)
        except Exception as e:
            self.config._data = config_before
            record = ExperimentRecord(
                experiment_id=experiment_id,
                timestamp=timestamp,
                direction=self.direction,
                config_snapshot=config_modifications,
                notes=f"EXPERIMENT FAILED: {str(e)}",
                improved=False,
                kept=False,
            )
            self.log.add(record)
            return record

        comparison = None
        improved = False
        if self.current_metrics:
            comparison = compare_metrics(self.current_metrics, new_metrics)
            improved = comparison["improved"]

        kept = improved
        if not improved:
            self.config._data = config_before
        else:
            self.current_metrics = new_metrics

        record = ExperimentRecord(
            experiment_id=experiment_id,
            timestamp=timestamp,
            direction=self.direction,
            config_snapshot=config_modifications,
            metrics_before=self.current_metrics.to_dict() if self.current_metrics else None,
            metrics_after=new_metrics.to_dict(),
            comparison=comparison,
            improved=improved,
            kept=kept,
            notes=notes,
        )
        self.log.add(record)

        return record

    def get_status(self) -> dict:
        return {
            "direction": self.direction,
            "experiment_count": self.experiment_count,
            "baseline_score": self.baseline_metrics.overall_score if self.baseline_metrics else None,
            "current_score": self.current_metrics.overall_score if self.current_metrics else None,
            "log_summary": self.log.summary(),
        }
