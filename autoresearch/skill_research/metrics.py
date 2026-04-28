from dataclasses import dataclass, field, asdict


@dataclass
class ScenarioResult:
    scenario_id: str
    workflow_selection_correct: bool = False
    parameter_compliance: float = 0.0
    output_completeness: float = 0.0
    quality_compliance: float = 0.0
    delivery_score: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillMetrics:
    workflow_selection_accuracy: float = 0.0
    parameter_compliance: float = 0.0
    output_completeness: float = 0.0
    quality_compliance: float = 0.0
    delivery_score: float = 0.0
    scenario_results: list[ScenarioResult] = field(default_factory=list)
    scenario_count: int = 0
    scenarios_passed: int = 0
    passed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["scenario_results"] = [sr.to_dict() for sr in self.scenario_results]
        return d

    def compute_derived(self):
        if not self.scenario_results:
            return
        n = len(self.scenario_results)
        self.workflow_selection_accuracy = sum(
            1 for sr in self.scenario_results if sr.workflow_selection_correct
        ) / n * 100
        self.parameter_compliance = sum(
            sr.parameter_compliance for sr in self.scenario_results
        ) / n
        self.output_completeness = sum(
            sr.output_completeness for sr in self.scenario_results
        ) / n
        self.quality_compliance = sum(
            sr.quality_compliance for sr in self.scenario_results
        ) / n
        self.delivery_score = sum(
            sr.delivery_score for sr in self.scenario_results
        ) / n
        self.scenario_count = n
        self.scenarios_passed = sum(
            1 for sr in self.scenario_results if sr.delivery_score >= 80
        )
        self.passed = (
            self.workflow_selection_accuracy >= 80
            and self.delivery_score >= 75
            and self.scenarios_passed >= n * 0.8
        )


def compare_skill_metrics(before: SkillMetrics, after: SkillMetrics) -> dict:
    def delta(a, b):
        return round(b - a, 2)

    return {
        "workflow_selection_accuracy_delta": delta(
            before.workflow_selection_accuracy, after.workflow_selection_accuracy
        ),
        "parameter_compliance_delta": delta(
            before.parameter_compliance, after.parameter_compliance
        ),
        "output_completeness_delta": delta(
            before.output_completeness, after.output_completeness
        ),
        "quality_compliance_delta": delta(
            before.quality_compliance, after.quality_compliance
        ),
        "delivery_score_delta": delta(
            before.delivery_score, after.delivery_score
        ),
        "scenarios_passed_delta": delta(
            before.scenarios_passed, after.scenarios_passed
        ),
        "improved": after.delivery_score > before.delivery_score,
        "regressed": after.delivery_score < before.delivery_score,
        "passed_before": before.passed,
        "passed_after": after.passed,
    }
