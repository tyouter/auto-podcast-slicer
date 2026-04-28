import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoresearch.skill_research.experiment import SkillExperiment
from autoresearch.skill_research.strategies import get_all_scenarios, get_all_modifications, get_recommended_modifications
from autoresearch.skill_research.verifier import SkillVerifier
from autoresearch.skill_research.metrics import SkillMetrics


def print_separator(title: str = ""):
    print(f"\n{'=' * 60}")
    if title:
        print(f"  {title}")
        print(f"{'=' * 60}")


def print_metrics(metrics: SkillMetrics, label: str = ""):
    if label:
        print(f"\n--- {label} ---")
    print(f"  工作流选择准确率: {metrics.workflow_selection_accuracy:.1f}%")
    print(f"  参数合规率:       {metrics.parameter_compliance:.1f}%")
    print(f"  输出完整度:       {metrics.output_completeness:.1f}%")
    print(f"  质量合规率:       {metrics.quality_compliance:.1f}%")
    print(f"  交付效果分:       {metrics.delivery_score:.1f}")
    print(f"  场景通过:         {metrics.scenarios_passed}/{metrics.scenario_count}")
    print(f"  总体通过:         {'✓ PASSED' if metrics.passed else '✗ NOT PASSED'}")

    for sr in metrics.scenario_results:
        status = "✓" if sr.delivery_score >= 80 else "✗"
        print(f"    {status} {sr.scenario_id}: 交付分={sr.delivery_score:.1f} "
              f"工作流={'✓' if sr.workflow_selection_correct else '✗'} "
              f"参数={sr.parameter_compliance:.0f}% "
              f"输出={sr.output_completeness:.0f}% "
              f"质量={sr.quality_compliance:.0f}%")


def run_verify(project_root: Path):
    print_separator("SKILL 验证报告")
    verifier = SkillVerifier(project_root)
    scenarios = get_all_scenarios()
    metrics = verifier.verify_all(scenarios)
    print_metrics(metrics, "当前SKILL验证结果")
    return metrics


def run_experiment(project_root: Path, max_iterations: int = 5):
    print_separator("SKILL 自我改进实验")
    experiment = SkillExperiment(project_root)

    print("\n[1/3] 设置基线...")
    baseline = experiment.set_baseline()
    print_metrics(baseline, "基线指标")

    print("\n[2/3] 运行推荐修改实验...")
    results = experiment.run_recommended(max_iterations=max_iterations)

    print("\n[3/3] 实验结果汇总:")
    for record in results:
        status = "✓ 采纳" if record.kept else ("✗ 改进" if record.improved else "✗ 回退")
        print(f"  {record.experiment_id}: {record.modification_id} → {status}")
        if record.comparison:
            print(f"    交付分变化: {record.comparison.get('delivery_score_delta', 0):+.1f}")
            print(f"    工作流选择变化: {record.comparison.get('workflow_selection_accuracy_delta', 0):+.1f}")
            print(f"    输出完整度变化: {record.comparison.get('output_completeness_delta', 0):+.1f}")

    final_status = experiment.get_status()
    print(f"\n最终状态:")
    print(f"  基线交付分: {final_status.get('baseline_delivery_score', 'N/A')}")
    print(f"  当前交付分: {final_status.get('current_delivery_score', 'N/A')}")
    print(f"  实验总数:   {final_status.get('log_summary', {}).get('total_experiments', 0)}")
    print(f"  改进次数:   {final_status.get('log_summary', {}).get('improvements', 0)}")
    print(f"  采纳次数:   {final_status.get('log_summary', {}).get('kept_changes', 0)}")

    return experiment


def run_single_modification(project_root: Path, mod_id: str):
    print_separator(f"SKILL 单项修改实验: {mod_id}")
    experiment = SkillExperiment(project_root)

    baseline = experiment.set_baseline()
    print_metrics(baseline, "修改前")

    from autoresearch.skill_research.strategies import get_modification
    mod = get_modification(mod_id)
    if not mod:
        print(f"未找到修改策略: {mod_id}")
        print(f"可用策略: {list(get_all_modifications().keys())}")
        return None

    record = experiment.run_experiment(mod)
    status = "✓ 采纳" if record.kept else "✗ 回退"
    print(f"\n结果: {status}")
    if record.comparison:
        print(f"  交付分变化: {record.comparison.get('delivery_score_delta', 0):+.1f}")

    current = experiment.current_metrics
    if current:
        print_metrics(current, "修改后")

    return experiment


def list_strategies():
    print_separator("验证场景 & 修改策略")
    scenarios = get_all_scenarios()
    print("\n验证场景:")
    for sid, s in scenarios.items():
        print(f"  {sid}")
        print(f"    请求: \"{s.user_request}\"")
        print(f"    期望工作流: {s.expected_workflow}")
        print(f"    预期文件: {len(s.expected_files)}项")
        print(f"    预期属性: {len(s.expected_properties)}项")
        print(f"    质量检查: {len(s.quality_checks)}项")

    modifications = get_all_modifications()
    print("\n修改策略:")
    for mid, m in modifications.items():
        print(f"  {mid}")
        print(f"    描述: {m.description}")
        print(f"    假设: {m.hypothesis}")
        print(f"    风险: {m.risk_level}")


def main():
    project_root = Path(__file__).resolve().parent.parent

    if len(sys.argv) < 2:
        print("用法: python -m tools.run_skill_research <command> [args]")
        print()
        print("命令:")
        print("  verify              验证当前SKILL")
        print("  experiment [N]      运行N轮推荐修改实验（默认5）")
        print("  modify <mod_id>     运行单项修改实验")
        print("  list                列出所有验证场景和修改策略")
        return

    command = sys.argv[1]

    if command == "verify":
        run_verify(project_root)
    elif command == "experiment":
        max_iter = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        run_experiment(project_root, max_iter)
    elif command == "modify":
        if len(sys.argv) < 3:
            print("请指定修改策略ID，可用策略:")
            for mid in get_all_modifications():
                print(f"  {mid}")
            return
        run_single_modification(project_root, sys.argv[2])
    elif command == "list":
        list_strategies()
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
