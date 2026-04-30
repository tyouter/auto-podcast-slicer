import json
import copy
import time
from datetime import datetime
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.transcribe import TranscriptResult, TranscriptSegment
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_generator import SubtitleResult
from pipeline.subtitle_verifier import verify_subtitles
from pipeline.alignment_verifier import run_full_alignment_verification
from autoresearch.logger import ResearchLogger


PROJECT_ROOT = Path(__file__).parent.parent


def load_transcript() -> TranscriptResult:
    ctx = load_project()
    return ctx.transcript


def evaluate_config(config: PipelineConfig, transcript: TranscriptResult) -> dict:
    entries, merged = process_transcript_to_subtitles(transcript, config)

    subtitle_result = SubtitleResult(entries=entries, format="srt", source_file=transcript.source_file)

    sub_verification = verify_subtitles(subtitle_result, config)

    merged_transcript = TranscriptResult(
        segments=[TranscriptSegment(
            start_ms=m.start_ms,
            end_ms=m.end_ms,
            text=m.text,
        ) for m in merged],
        source_file=transcript.source_file,
        engine="merged",
        language="zh",
        duration_s=transcript.duration_s,
    )

    alignment_report = run_full_alignment_verification(
        merged_transcript,
        config,
    )

    critical = alignment_report.critical_count if hasattr(alignment_report, 'critical_count') else sum(1 for i in alignment_report.issues if i.get("severity") == "critical")
    warnings = sum(1 for i in alignment_report.issues if i.get("severity") == "warning")

    return {
        "subtitle_count": len(entries),
        "subtitle_score": sub_verification.score,
        "subtitle_passed": sub_verification.passed,
        "subtitle_critical": sub_verification.critical_count,
        "subtitle_warning": sub_verification.warning_count,
        "alignment_score": alignment_report.alignment_score,
        "coverage_score": alignment_report.coverage_score,
        "timing_accuracy_score": alignment_report.timing_accuracy_score,
        "continuity_score": alignment_report.continuity_score,
        "interruption_quality_score": alignment_report.interruption_quality_score,
        "alignment_passed": alignment_report.passed,
        "publishing_ready": alignment_report.publishing_ready,
        "alignment_critical": critical,
        "alignment_warning": warnings,
        "merged_count": len(merged),
        "issues_sample": alignment_report.issues[:20],
    }


def run_iteration(
    config: PipelineConfig,
    transcript: TranscriptResult,
    logger: ResearchLogger,
    iteration: int,
    modifications: dict,
    description: str,
) -> dict:
    config_before = copy.deepcopy(config.to_dict())

    for dotpath, value in modifications.items():
        config.set(dotpath, value)
        logger.info("iteration", f"[Iter {iteration}] Config: {dotpath} = {value}")

    logger.info("iteration", f"[Iter {iteration}] Evaluating: {description}")

    result = evaluate_config(config, transcript)

    logger.info("iteration", f"[Iter {iteration}] Results:", {
        "alignment_score": result["alignment_score"],
        "subtitle_score": result["subtitle_score"],
        "publishing_ready": result["publishing_ready"],
        "critical": result["alignment_critical"],
        "warnings": result["alignment_warning"],
    })

    return result


def run_autoresearch_loop(max_iterations: int = 50) -> dict:
    config = PipelineConfig()
    transcript = load_transcript()
    output_dir = config.output_dir / "experiments"
    logger = ResearchLogger(output_dir)

    logger.info("autoresearch", "Starting auto-research loop for subtitle-audio alignment")

    baseline = evaluate_config(config, transcript)
    logger.info("autoresearch", "Baseline results:", {
        "alignment_score": baseline["alignment_score"],
        "subtitle_score": baseline["subtitle_score"],
        "publishing_ready": baseline["publishing_ready"],
        "critical": baseline["alignment_critical"],
        "warnings": baseline["alignment_warning"],
    })

    print(f"\n{'='*70}")
    print(f"BASELINE: alignment={baseline['alignment_score']:.1f}, subtitle={baseline['subtitle_score']:.1f}, "
          f"critical={baseline['alignment_critical']}, warnings={baseline['alignment_warning']}, "
          f"publishing_ready={baseline['publishing_ready']}")
    print(f"{'='*70}\n")

    best_score = baseline["alignment_score"]
    best_config = copy.deepcopy(config.to_dict())
    best_result = baseline
    history = [{"iteration": 0, **baseline}]

    strategies = [
        {
            "name": "wider_max_display_10s",
            "description": "放宽最大显示时间到10秒，允许更多合并",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 10.0,
            },
        },
        {
            "name": "wider_max_display_12s",
            "description": "放宽最大显示时间到12秒",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 12.0,
            },
        },
        {
            "name": "increase_max_chars_18",
            "description": "增加每行字数到18字，允许更多合并",
            "modifications": {
                "pipeline.subtitle.max_chars_per_line_cn": 18,
            },
        },
        {
            "name": "increase_max_chars_20",
            "description": "增加每行字数到20字",
            "modifications": {
                "pipeline.subtitle.max_chars_per_line_cn": 20,
            },
        },
        {
            "name": "increase_max_chars_22",
            "description": "增加每行字数到22字",
            "modifications": {
                "pipeline.subtitle.max_chars_per_line_cn": 22,
            },
        },
        {
            "name": "combo_max10_chars18",
            "description": "组合: 最长10s + 18字/行",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 10.0,
                "pipeline.subtitle.max_chars_per_line_cn": 18,
            },
        },
        {
            "name": "combo_max10_chars20",
            "description": "组合: 最长10s + 20字/行",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 10.0,
                "pipeline.subtitle.max_chars_per_line_cn": 20,
            },
        },
        {
            "name": "combo_max12_chars20",
            "description": "组合: 最长12s + 20字/行",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 12.0,
                "pipeline.subtitle.max_chars_per_line_cn": 20,
            },
        },
        {
            "name": "combo_max12_chars22",
            "description": "组合: 最长12s + 22字/行",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 12.0,
                "pipeline.subtitle.max_chars_per_line_cn": 22,
            },
        },
        {
            "name": "combo_max15_chars22",
            "description": "组合: 最长15s + 22字/行",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 15.0,
                "pipeline.subtitle.max_chars_per_line_cn": 22,
            },
        },
        {
            "name": "combo_max10_chars18_speed3.5",
            "description": "组合: 最长10s + 18字/行 + 3.5字/秒",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 10.0,
                "pipeline.subtitle.max_chars_per_line_cn": 18,
                "pipeline.subtitle.reading_speed_cn": 3.5,
            },
        },
        {
            "name": "combo_max12_chars20_speed3.5",
            "description": "组合: 最长12s + 20字/行 + 3.5字/秒",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 12.0,
                "pipeline.subtitle.max_chars_per_line_cn": 20,
                "pipeline.subtitle.reading_speed_cn": 3.5,
            },
        },
        {
            "name": "combo_max15_chars25_speed3",
            "description": "组合: 最长15s + 25字/行 + 3字/秒 (宽松)",
            "modifications": {
                "pipeline.subtitle.max_display_duration": 15.0,
                "pipeline.subtitle.max_chars_per_line_cn": 25,
                "pipeline.subtitle.reading_speed_cn": 3,
            },
        },
    ]

    iteration = 0
    for strategy in strategies:
        if iteration >= max_iterations:
            break

        iteration += 1
        config = PipelineConfig()

        result = run_iteration(
            config, transcript, logger,
            iteration, strategy["modifications"], strategy["description"],
        )

        result["strategy"] = strategy["name"]
        result["iteration"] = iteration
        history.append(result)

        score = result["alignment_score"]
        warnings = result["alignment_warning"]
        critical = result["alignment_critical"]
        improved = score > best_score or (score == best_score and critical < best_result.get("alignment_critical", 999)) or (score == best_score and critical == best_result.get("alignment_critical", 0) and warnings < best_result.get("alignment_warning", 999))

        status = "IMPROVED" if improved else "NO CHANGE" if score == best_score else "REGRESSED"
        print(f"\n[Iter {iteration}] {strategy['name']}: alignment={score:.1f} (best={best_score:.1f}) "
              f"critical={result['alignment_critical']} warnings={result['alignment_warning']} "
              f"publishing={result['publishing_ready']} → {status}")

        if improved:
            best_score = score
            best_config = copy.deepcopy(config.to_dict())
            best_result = result
            logger.info("autoresearch", f"[Iter {iteration}] NEW BEST: {score:.1f}")

    if best_score >= baseline["alignment_score"]:
        config = PipelineConfig()
        for dotpath, value in best_config.items():
            pass
        config._data = best_config

    print(f"\n{'='*70}")
    print(f"AUTORESEARCH COMPLETE")
    print(f"{'='*70}")
    print(f"Baseline alignment score: {baseline['alignment_score']:.1f}")
    print(f"Best alignment score: {best_score:.1f}")
    print(f"Improvement: {best_score - baseline['alignment_score']:.1f}")
    print(f"Publishing ready: {best_result['publishing_ready']}")
    print(f"Total iterations: {iteration}")

    report_path = output_dir / "autoresearch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "baseline": baseline,
            "best_result": best_result,
            "improvement": best_score - baseline["alignment_score"],
            "iterations": iteration,
            "history": history,
        }, f, ensure_ascii=False, indent=2, default=str)

    return {
        "baseline_score": baseline["alignment_score"],
        "best_score": best_score,
        "improvement": best_score - baseline["alignment_score"],
        "publishing_ready": best_result["publishing_ready"],
        "iterations": iteration,
    }


if __name__ == "__main__":
    result = run_autoresearch_loop()
    print(json.dumps(result, ensure_ascii=False, indent=2))
