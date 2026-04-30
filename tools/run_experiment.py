import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
from pipeline.config import PipelineConfig
from pipeline.quality_checker import run_quality_check
from autoresearch.experiment import Experiment
from autoresearch.strategies import get_strategy, get_recommended_strategies
from autoresearch.metrics import PipelineMetrics, compute_metrics_from_quality_report
from autoresearch.logger import ResearchLogger


def run_single_experiment(
    strategy_name: str,
    source: Path | None = None,
    config: PipelineConfig | None = None,
) -> dict:
    if config is None:
        config = PipelineConfig()

    output_dir = config.output_dir
    logger = ResearchLogger(output_dir / "experiments")

    strategy = get_strategy(strategy_name)
    if not strategy:
        logger.error("experiment", f"Unknown strategy: {strategy_name}")
        return {"error": f"Unknown strategy: {strategy_name}"}

    logger.info("experiment", f"Running strategy: {strategy_name}", strategy.config_modifications)

    # Load baseline quality if exists
    baseline_report_path = output_dir / "clips" / "quality_report.json"
    baseline_metrics = None

    # Find existing quality reports
    existing_reports = list(output_dir.glob("clips/*/quality_report.json"))
    if existing_reports:
        latest_report_dir = existing_reports[0].parent
        baseline_report = run_quality_check(latest_report_dir, config, latest_report_dir.name)
        baseline_metrics = compute_metrics_from_quality_report(baseline_report)

    # Apply strategy modifications
    for dotpath, value in strategy.config_modifications.items():
        config.set(dotpath, value)
        logger.info("experiment", f"Config set: {dotpath} = {value}")

    # If source provided, run full pipeline
    if source and source.exists():
        from tools.run_pipeline import run_full_pipeline
        summary = run_full_pipeline(source, config)

        # Get new quality report
        new_reports = list(output_dir.glob("clips/*/quality_report.json"))
        if new_reports:
            latest_dir = new_reports[0].parent
            new_report = run_quality_check(latest_dir, config, latest_dir.name)
            new_metrics = compute_metrics_from_quality_report(new_report)

            from autoresearch.metrics import compare_metrics
            if baseline_metrics:
                comparison = compare_metrics(baseline_metrics, new_metrics)
                logger.info("experiment", f"Comparison: {json.dumps(comparison)}")

                if comparison["improved"]:
                    logger.info("experiment", f"IMPROVED! Score: {baseline_metrics.overall_score:.1f} → {new_metrics.overall_score:.1f}")
                    config.save(PROJECT_ROOT / "config" / "default.yaml")
                else:
                    logger.warning("experiment", f"REGRESSED. Score: {baseline_metrics.overall_score:.1f} → {new_metrics.overall_score:.1f}")

                return {
                    "strategy": strategy_name,
                    "baseline_score": baseline_metrics.overall_score,
                    "new_score": new_metrics.overall_score,
                    "improved": comparison["improved"],
                    "comparison": comparison,
                }

    return {
        "strategy": strategy_name,
        "config_modifications": strategy.config_modifications,
        "note": "Config modified. Run pipeline with source to measure impact.",
    }


def run_auto_iteration(
    source: Path,
    max_experiments: int = 10,
    config: PipelineConfig | None = None,
) -> dict:
    if config is None:
        config = PipelineConfig()

    output_dir = config.output_dir
    logger = ResearchLogger(output_dir / "experiments")
    experiment = Experiment(config, output_dir / "experiments", direction="auto_quality")

    # Run initial pipeline
    logger.info("auto_iteration", "Running initial pipeline for baseline")
    from tools.run_pipeline import run_full_pipeline
    run_full_pipeline(source, config)

    # Get baseline quality
    existing_reports = list(output_dir.glob("clips/*/quality_report.json"))
    if not existing_reports:
        logger.error("auto_iteration", "No quality reports found after initial run")
        return {"error": "No quality reports found"}

    baseline_dir = existing_reports[0].parent
    baseline_report = run_quality_check(baseline_dir, config, baseline_dir.name)
    baseline_metrics = compute_metrics_from_quality_report(baseline_report)
    experiment.set_baseline(baseline_report)

    logger.info("auto_iteration", f"Baseline score: {baseline_metrics.overall_score:.1f}")

    # Get recommended strategies
    strategies = get_recommended_strategies(baseline_metrics)
    logger.info("auto_iteration", f"Recommended {len(strategies)} strategies")

    results = []
    for i, strategy in enumerate(strategies[:max_experiments]):
        logger.info("auto_iteration", f"Experiment {i + 1}/{min(len(strategies), max_experiments)}: {strategy.strategy_name}")

        record = experiment.run_experiment(
            config_modifications=strategy.config_modifications,
            quality_report_fn=lambda cfg: _run_and_measure(source, cfg, output_dir),
            notes=f"Strategy: {strategy.strategy_name} - {strategy.description}",
        )

        results.append({
            "strategy": strategy.strategy_name,
            "improved": record.improved,
            "kept": record.kept,
        })

        logger.info("auto_iteration", f"Result: improved={record.improved}, kept={record.kept}")

    # Final summary
    status = experiment.get_status()
    logger.info("auto_iteration", f"Auto-iteration complete. {status}")

    return {
        "baseline_score": baseline_metrics.overall_score,
        "final_score": status.get("current_score"),
        "total_experiments": len(results),
        "improvements": sum(1 for r in results if r["improved"]),
        "results": results,
        "experiment_status": status,
    }


def _run_and_measure(source: Path, config: PipelineConfig, output_dir: Path) -> "QualityReport":
    from tools.run_pipeline import run_full_pipeline
    run_full_pipeline(source, config)

    reports = list(output_dir.glob("clips/*/quality_report.json"))
    if reports:
        latest_dir = reports[0].parent
        return run_quality_check(latest_dir, config, latest_dir.name)

    from pipeline.quality_checker import QualityReport
    return QualityReport()
