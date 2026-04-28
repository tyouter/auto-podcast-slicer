import json
import copy
import time
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from autoresearch.skill_research.metrics import SkillMetrics, compare_skill_metrics
from autoresearch.skill_research.strategies import (
    VerificationScenario,
    SkillModification,
    get_all_scenarios,
    get_all_modifications,
    get_recommended_modifications,
)
from autoresearch.skill_research.verifier import SkillVerifier


@dataclass
class SkillExperimentRecord:
    experiment_id: str
    timestamp: str
    modification_id: str
    modification_description: str
    skill_snapshot_before: str = ""
    skill_snapshot_after: str = ""
    metrics_before: dict | None = None
    metrics_after: dict | None = None
    comparison: dict | None = None
    improved: bool = False
    kept: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["skill_snapshot_before"] = self.skill_snapshot_before[:500] + "..." if len(self.skill_snapshot_before) > 500 else self.skill_snapshot_before
        d["skill_snapshot_after"] = self.skill_snapshot_after[:500] + "..." if len(self.skill_snapshot_after) > 500 else self.skill_snapshot_after
        return d


class SkillExperimentLog:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "skill_experiment_log.json"
        self.records: list[SkillExperimentRecord] = self._load()

    def _load(self) -> list[SkillExperimentRecord]:
        if not self.log_file.exists():
            return []
        with open(self.log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [SkillExperimentRecord(**r) for r in data]

    def save(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in self.records],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def add(self, record: SkillExperimentRecord):
        self.records.append(record)
        self.save()

    def get_latest(self) -> SkillExperimentRecord | None:
        return self.records[-1] if self.records else None

    def get_improvements(self) -> list[SkillExperimentRecord]:
        return [r for r in self.records if r.improved]

    def get_regressions(self) -> list[SkillExperimentRecord]:
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


class SkillExperiment:
    def __init__(
        self,
        project_root: Path,
        log_dir: Path | None = None,
        skill_path: Path | None = None,
    ):
        self.project_root = project_root
        if skill_path is None:
            skill_path = project_root / ".trae" / "skills" / "video-clip" / "SKILL.md"
        self.skill_path = skill_path
        if log_dir is None:
            log_dir = project_root / "output" / "skill_experiments"
        self.log = SkillExperimentLog(log_dir)
        self.verifier = SkillVerifier(project_root, skill_path)
        self.baseline_metrics: SkillMetrics | None = None
        self.current_metrics: SkillMetrics | None = None
        self.experiment_count = 0

    def set_baseline(self) -> SkillMetrics:
        scenarios = get_all_scenarios()
        self.baseline_metrics = self.verifier.verify_all(scenarios)
        self.current_metrics = self.baseline_metrics
        return self.baseline_metrics

    def run_experiment(
        self,
        modification: SkillModification,
        notes: str = "",
    ) -> SkillExperimentRecord:
        self.experiment_count += 1
        experiment_id = f"skill_exp_{self.experiment_count:04d}_{int(time.time())}"
        timestamp = datetime.now().isoformat()

        skill_before = self.skill_path.read_text(encoding="utf-8") if self.skill_path.exists() else ""

        metrics_before = self.current_metrics

        modified_skill = self._apply_modification(skill_before, modification)
        backup_path = self.skill_path.with_suffix(".md.bak")
        self.skill_path.write_text(modified_skill, encoding="utf-8")

        try:
            scenarios = get_all_scenarios()
            new_metrics = self.verifier.verify_all(scenarios)
        except Exception as e:
            self.skill_path.write_text(skill_before, encoding="utf-8")
            if backup_path.exists():
                backup_path.unlink()
            record = SkillExperimentRecord(
                experiment_id=experiment_id,
                timestamp=timestamp,
                modification_id=modification.modification_id,
                modification_description=modification.description,
                skill_snapshot_before=skill_before[:500],
                notes=f"EXPERIMENT FAILED: {str(e)}",
                improved=False,
                kept=False,
            )
            self.log.add(record)
            return record

        comparison = None
        improved = False
        if metrics_before:
            comparison = compare_skill_metrics(metrics_before, new_metrics)
            improved = comparison["improved"]

        kept = improved
        if not improved:
            self.skill_path.write_text(skill_before, encoding="utf-8")
        else:
            self.current_metrics = new_metrics

        if backup_path.exists():
            backup_path.unlink()

        record = SkillExperimentRecord(
            experiment_id=experiment_id,
            timestamp=timestamp,
            modification_id=modification.modification_id,
            modification_description=modification.description,
            skill_snapshot_before=skill_before[:500],
            skill_snapshot_after=modified_skill[:500],
            metrics_before=metrics_before.to_dict() if metrics_before else None,
            metrics_after=new_metrics.to_dict(),
            comparison=comparison,
            improved=improved,
            kept=kept,
            notes=notes,
        )
        self.log.add(record)
        return record

    def run_recommended(self, max_iterations: int = 5) -> list[SkillExperimentRecord]:
        if not self.baseline_metrics:
            self.set_baseline()

        results = []
        current_dict = self.current_metrics.to_dict() if self.current_metrics else {}
        recommended = get_recommended_modifications(current_dict)

        for i, mod in enumerate(recommended[:max_iterations]):
            record = self.run_experiment(mod, notes=f"Auto-recommended iteration {i + 1}")
            results.append(record)
            if record.improved:
                current_dict = self.current_metrics.to_dict()
            else:
                break

        return results

    def _apply_modification(self, skill_text: str, modification: SkillModification) -> str:
        patch = modification.skill_patch
        section = patch.get("section", "")
        action = patch.get("action", "")
        content = patch.get("content", "")

        if action == "prepend":
            return self._prepend_to_section(skill_text, section, content)
        elif action == "append":
            return self._append_to_section(skill_text, section, content)
        elif action == "replace":
            return self._replace_section(skill_text, section, content)
        elif action == "append_to_each_workflow":
            return self._append_to_each_workflow(skill_text, content)
        elif action == "modify_each_workflow":
            return self._modify_each_workflow(skill_text, content)
        else:
            return skill_text + "\n\n" + content

    def _find_section_start(self, text: str, section_name: str) -> int:
        patterns = [
            f"## {section_name}",
            f"### {section_name}",
            f"# {section_name}",
        ]
        for pattern in patterns:
            idx = text.find(pattern)
            if idx >= 0:
                return idx
        return -1

    def _find_next_section_start(self, text: str, from_pos: int) -> int:
        for i in range(from_pos + 1, len(text)):
            if text[i] == "\n" and i + 1 < len(text):
                rest = text[i + 1:]
                if rest.startswith("## ") or rest.startswith("# "):
                    return i + 1
        return len(text)

    def _prepend_to_section(self, text: str, section: str, content: str) -> str:
        idx = self._find_section_start(text, section)
        if idx < 0:
            return text + "\n\n" + content + "\n"
        line_end = text.find("\n", idx)
        if line_end < 0:
            line_end = len(text)
        return text[:line_end + 1] + content + "\n" + text[line_end + 1:]

    def _append_to_section(self, text: str, section: str, content: str) -> str:
        idx = self._find_section_start(text, section)
        if idx < 0:
            return text + "\n\n" + content + "\n"
        next_idx = self._find_next_section_start(text, idx)
        return text[:next_idx] + "\n" + content + "\n" + text[next_idx:]

    def _replace_section(self, text: str, section: str, content: str) -> str:
        idx = self._find_section_start(text, section)
        if idx < 0:
            return text + "\n\n" + content + "\n"
        next_idx = self._find_next_section_start(text, idx)
        header_end = text.find("\n", idx)
        if header_end < 0:
            header_end = len(text)
        return text[:header_end + 1] + content + "\n" + text[next_idx:]

    def _append_to_each_workflow(self, text: str, content: str) -> str:
        workflow_pattern = re.compile(r"(### 工作流\d+：.+?)(?=\n---|\n### 工作流|\n## |\Z)", re.DOTALL)
        matches = list(workflow_pattern.finditer(text))
        if not matches:
            return text + "\n\n" + content + "\n"
        offset = 0
        result = text
        for match in reversed(matches):
            end = match.end()
            result = result[:end + offset] + "\n" + content + "\n" + result[end + offset:]
            offset += len(content) + 2
        return result

    def _modify_each_workflow(self, text: str, content: str) -> str:
        return self._append_to_each_workflow(text, content)

    def get_status(self) -> dict:
        return {
            "skill_path": str(self.skill_path),
            "experiment_count": self.experiment_count,
            "baseline_delivery_score": self.baseline_metrics.delivery_score if self.baseline_metrics else None,
            "current_delivery_score": self.current_metrics.delivery_score if self.current_metrics else None,
            "baseline_passed": self.baseline_metrics.passed if self.baseline_metrics else None,
            "current_passed": self.current_metrics.passed if self.current_metrics else None,
            "log_summary": self.log.summary(),
        }
