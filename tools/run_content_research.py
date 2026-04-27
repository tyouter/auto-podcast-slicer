import json
import re
import time
import copy
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict

from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json, TranscriptResult, TranscriptSegment
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_generator import SubtitleEntry
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    normalize_to_simplified_chinese,
    apply_custom_errata,
    clean_subtitle_text,
    add_punctuation_smart,
    enforce_single_line,
    format_subtitle_single_line,
    validate_subtitle_content,
    ContentValidationResult,
    TRADITIONAL_ONLY,
    ERRATA_AUTHORS,
    ERRATA_WORKS,
    ERRATA_IDIOMS,
    ERRATA_COMMON,
    COMMON_VARIANTS,
)
from pipeline.alignment_verifier import (
    run_full_alignment_verification,
    AlignmentReport,
)
from pipeline.subtitle_verifier import verify_subtitles, SubtitleVerificationResult
from pipeline.subtitle_generator import SubtitleResult


@dataclass
class IterationResult:
    iteration: int
    timestamp: str
    direction: str
    content_score: float
    alignment_score: float
    timing_score: float
    total_score: float
    content_passed: bool
    alignment_passed: bool
    timing_passed: bool
    all_passed: bool
    critical_issues: int
    warnings: int
    accuracy_rate: float = 100.0
    content_issues: list = field(default_factory=list)
    alignment_issues: list = field(default_factory=list)
    timing_issues: list = field(default_factory=list)
    actions_taken: list = field(default_factory=list)
    config_snapshot: dict = field(default_factory=dict)


class SubtitleContentResearch:
    def __init__(self, config: PipelineConfig, output_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.experiments_dir = output_dir / "experiments"
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.iterations: list[IterationResult] = []
        self.max_iterations = 30
        self.corrections_path = Path("config/corrections.yaml")
        self.custom_errata = load_custom_errata(self.corrections_path)
        self._transcript = None

    def load_transcript(self) -> TranscriptResult:
        if self._transcript is None:
            mixed_json_path = Path("D:/boke/garden post factory/C0257_full_mixed.json")
            self._transcript = parse_funasr_mixed_json(mixed_json_path)
        return self._transcript

    def process_entries_with_content(
        self, entries: list[SubtitleEntry], max_chars: int = 18
    ) -> list[SubtitleEntry]:
        processed = []
        for i, entry in enumerate(entries):
            next_text = entries[i + 1].text if i + 1 < len(entries) else ""
            gap_ms = entries[i + 1].start_ms - entry.end_ms if i + 1 < len(entries) else 0
            gap_s = gap_ms / 1000.0
            is_last = (i == len(entries) - 1)
            duration_s = entry.duration_s

            processed_text = process_subtitle_content(
                text=entry.text,
                duration_s=duration_s,
                next_text=next_text,
                gap_s=gap_s,
                max_chars=max_chars,
                is_last=is_last,
                custom_errata=self.custom_errata,
            )

            processed.append(SubtitleEntry(
                index=entry.index,
                start_ms=entry.start_ms,
                end_ms=entry.end_ms,
                text=processed_text,
            ))
        return processed

    def validate_content(self, entries: list[SubtitleEntry]) -> ContentValidationResult:
        entry_dicts = [
            {"index": e.index, "text": e.text, "start_ms": e.start_ms, "end_ms": e.end_ms}
            for e in entries
        ]
        render_style = {
            "font_name": self.config.get("pipeline.subtitle.render_style.font_name", "Noto Sans SC"),
            "font_color": self.config.get("pipeline.subtitle.render_style.font_color", "white"),
            "mode": self.config.get("pipeline.subtitle.render_style.mode", "frosted_glass_dark"),
            "bg_opacity": self.config.get("pipeline.subtitle.render_style.bg_opacity", 0.60),
        }
        return validate_subtitle_content(entry_dicts, max_chars=18, render_style=render_style, strip_punctuation=True)

    def validate_timing(self, entries: list[SubtitleEntry]) -> SubtitleVerificationResult:
        subtitle_result = SubtitleResult(entries=entries)
        return verify_subtitles(subtitle_result, self.config)

    def validate_alignment(self, transcript: TranscriptResult) -> AlignmentReport:
        return run_full_alignment_verification(transcript, self.config)

    def run_single_iteration(
        self,
        transcript: TranscriptResult,
        entries: list[SubtitleEntry],
        iteration: int,
        direction: str,
    ) -> IterationResult:
        timestamp = datetime.now().isoformat()

        content_result = self.validate_content(entries)
        timing_result = self.validate_timing(entries)
        alignment_result = self.validate_alignment(transcript)

        content_score = content_result.score
        alignment_score = alignment_result.alignment_score
        timing_score = timing_result.score
        accuracy_rate = content_result.accuracy_rate

        total_score = (
            content_score * 0.40
            + alignment_score * 0.35
            + timing_score * 0.25
        )

        critical_issues = (
            content_result.critical_count
            + timing_result.critical_count
            + sum(1 for i in alignment_result.issues if i.get("severity") == "critical")
        )
        warnings = (
            content_result.warning_count
            + timing_result.warning_count
            + sum(1 for i in alignment_result.issues if i.get("severity") == "warning")
        )

        all_passed = (
            content_result.passed
            and timing_result.passed
            and alignment_result.passed
            and critical_issues == 0
        )

        return IterationResult(
            iteration=iteration,
            timestamp=timestamp,
            direction=direction,
            content_score=round(content_score, 1),
            alignment_score=round(alignment_score, 1),
            timing_score=round(timing_score, 1),
            total_score=round(total_score, 1),
            accuracy_rate=round(accuracy_rate, 4),
            content_passed=content_result.passed,
            alignment_passed=alignment_result.passed,
            timing_passed=timing_result.passed,
            all_passed=all_passed,
            critical_issues=critical_issues,
            warnings=warnings,
            content_issues=content_result.to_dict()["issues"],
            alignment_issues=alignment_result.issues[:20],
            timing_issues=timing_result.to_dict()["issues"],
        )

    def analyze_and_fix(self, result: IterationResult, config: PipelineConfig) -> list[str]:
        actions = []

        content_issue_types = set(i["issue_type"] for i in result.content_issues)
        timing_issue_types = set(i["issue_type"] for i in result.timing_issues)

        if "reading_speed_too_fast" in timing_issue_types:
            current_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
            config.set("pipeline.subtitle.reading_speed_cn", current_speed + 0.5)
            actions.append(f"提高阅读速度标准至{current_speed + 0.5}字/秒")

        if "gap_too_short" in timing_issue_types:
            current_gap = config.get("pipeline.subtitle.min_gap_duration", 0.067)
            if current_gap > 0.03:
                config.set("pipeline.subtitle.min_gap_duration", max(0.033, current_gap - 0.02))
                actions.append(f"降低最小间隔至{max(0.033, current_gap - 0.02):.3f}s")

        if "duration_too_short" in timing_issue_types:
            current_min = config.get("pipeline.subtitle.min_display_duration", 1.0)
            config.set("pipeline.subtitle.min_display_duration", max(0.8, current_min - 0.1))
            actions.append(f"降低最短显示时长至{max(0.8, current_min - 0.1):.1f}s")

        if "line_too_long" in timing_issue_types or "line_too_long" in content_issue_types:
            current_max = config.get("pipeline.subtitle.max_chars_per_line_cn", 18)
            config.set("pipeline.subtitle.max_chars_per_line_cn", max(14, current_max - 1))
            actions.append(f"减少最大行字数至{max(14, current_max - 1)}")

        if "english_punctuation" in content_issue_types:
            actions.append("英文标点替换为中文标点")

        if "line_start_forbidden" in content_issue_types:
            actions.append("修复行首禁则违规")

        if "no_punctuation" in content_issue_types:
            actions.append("添加标点断句")

        if "meaningless_filler" in content_issue_types:
            actions.append("清理无意义重复词")

        if "context_anomaly" in content_issue_types:
            actions.append("修正上下文异常")

        if not actions:
            actions.append("微调参数")

        return actions

    def run_research(self) -> dict:
        print("=" * 70)
        print("字幕内容规范性 Auto Research 迭代验证")
        print("=" * 70)

        transcript = self.load_transcript()

        entries, merged = process_transcript_to_subtitles(transcript, self.config)
        print(f"\n转录段数: {len(transcript.segments)}")
        print(f"初始字幕条数: {len(entries)}")

        entries = self.process_entries_with_content(entries, max_chars=18)

        best_score = 0
        best_entries = entries[:]
        stagnation_count = 0

        for iteration in range(1, self.max_iterations + 1):
            print(f"\n{'─' * 50}")
            print(f"迭代 #{iteration}")
            print(f"{'─' * 50}")

            result = self.run_single_iteration(transcript, entries, iteration, "subtitle_content")
            self.iterations.append(result)

            print(f"  内容得分: {result.content_score}")
            print(f"  对齐得分: {result.alignment_score}")
            print(f"  时序得分: {result.timing_score}")
            print(f"  总分: {result.total_score}")
            print(f"  字幕准确率: {result.accuracy_rate:.3f}%")
            print(f"  严重问题: {result.critical_issues}")
            print(f"  警告: {result.warnings}")
            print(f"  全部通过: {result.all_passed}")

            if result.total_score > best_score:
                best_score = result.total_score
                best_entries = entries[:]
                stagnation_count = 0
            else:
                stagnation_count += 1

            if result.all_passed:
                print(f"\n✓ 第{iteration}轮迭代全部通过！")
                break

            if stagnation_count >= 5:
                print(f"\n⚠ 连续{stagnation_count}轮无改善，尝试激进策略...")
                stagnation_count = 0

            actions = self.analyze_and_fix(result, self.config)
            print(f"  采取行动: {actions}")

            entries, merged = process_transcript_to_subtitles(transcript, self.config)
            entries = self.process_entries_with_content(entries, max_chars=18)

        final_result = self.iterations[-1] if self.iterations else None

        report = {
            "research_type": "subtitle_content_validation",
            "timestamp": datetime.now().isoformat(),
            "total_iterations": len(self.iterations),
            "best_score": best_score,
            "final_passed": final_result.all_passed if final_result else False,
            "iterations_summary": [
                {
                    "iteration": r.iteration,
                    "total_score": r.total_score,
                    "content_score": r.content_score,
                    "timing_score": r.timing_score,
                    "alignment_score": r.alignment_score,
                    "critical_issues": r.critical_issues,
                    "warnings": r.warnings,
                    "all_passed": r.all_passed,
                }
                for r in self.iterations
            ],
            "iterations_detail": [asdict(r) for r in self.iterations],
            "summary": {
                "initial_score": self.iterations[0].total_score if self.iterations else 0,
                "final_score": final_result.total_score if final_result else 0,
                "best_score": best_score,
                "improvement": round(
                    (final_result.total_score - self.iterations[0].total_score), 1
                ) if self.iterations and final_result else 0,
                "critical_issues_remaining": final_result.critical_issues if final_result else 0,
                "warnings_remaining": final_result.warnings if final_result else 0,
            },
        }

        report_path = self.experiments_dir / "subtitle_content_research_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 70}")
        print(f"研究完成: {len(self.iterations)} 轮迭代")
        print(f"初始分数: {report['summary']['initial_score']}")
        print(f"最终分数: {report['summary']['final_score']}")
        print(f"最佳分数: {best_score}")
        print(f"改善幅度: {report['summary']['improvement']}")
        print(f"剩余严重问题: {report['summary']['critical_issues_remaining']}")
        print(f"剩余警告: {report['summary']['warnings_remaining']}")
        print(f"报告已保存: {report_path}")

        return report


class FullPipelineResearch:
    def __init__(self, config: PipelineConfig, output_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.experiments_dir = output_dir / "experiments"
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_research = SubtitleContentResearch(config, output_dir)

    def run_full_validation(self) -> dict:
        print("=" * 70)
        print("全量 Pipeline 验证 — 音视频制成品达标检查")
        print("=" * 70)

        transcript = self.subtitle_research.load_transcript()
        entries, merged = process_transcript_to_subtitles(transcript, self.config)
        entries = self.subtitle_research.process_entries_with_content(entries, max_chars=18)

        print("\n[1/4] 字幕内容验证...")
        content_result = self.subtitle_research.validate_content(entries)
        print(f"  内容得分: {content_result.score}")
        print(f"  字幕准确率: {content_result.accuracy_rate:.3f}%")
        print(f"  通过: {content_result.passed}")
        print(f"  严重: {content_result.critical_count}, 警告: {content_result.warning_count}")

        print("\n[2/4] 字幕时序验证...")
        timing_result = self.subtitle_research.validate_timing(entries)
        print(f"  时序得分: {timing_result.score}")
        print(f"  通过: {timing_result.passed}")

        print("\n[3/4] 对齐验证...")
        alignment_result = self.subtitle_research.validate_alignment(transcript)
        print(f"  对齐得分: {alignment_result.alignment_score}")
        print(f"  发布就绪: {alignment_result.publishing_ready}")

        print("\n[4/4] 音频验证...")
        audio_results = []
        clips_dir = self.output_dir / "clips_fencha"
        if clips_dir.exists():
            from pipeline.audio_verifier import verify_audio
            for audio_file in clips_dir.rglob("*.wav"):
                verification = verify_audio(audio_file, self.config)
                audio_results.append(verification.to_dict())
                print(f"  {audio_file.name}: 得分={verification.score:.1f}, 通过={verification.passed}")

        all_critical = (
            content_result.critical_count
            + timing_result.critical_count
            + sum(1 for i in alignment_result.issues if i.get("severity") == "critical")
            + sum(1 for ar in audio_results for i in ar.get("issues", []) if i.get("severity") == "critical")
        )

        all_passed = (
            content_result.passed
            and timing_result.passed
            and alignment_result.passed
            and all(ar.get("passed", False) for ar in audio_results)
            and all_critical == 0
        )

        overall_score = (
            content_result.score * 0.30
            + timing_result.score * 0.20
            + alignment_result.alignment_score * 0.25
            + (sum(ar.get("score", 0) for ar in audio_results) / max(1, len(audio_results))) * 0.25
        )

        report = {
            "validation_type": "full_pipeline",
            "timestamp": datetime.now().isoformat(),
            "overall_score": round(overall_score, 1),
            "all_passed": all_passed,
            "total_critical_issues": all_critical,
            "content_validation": content_result.to_dict(),
            "timing_validation": timing_result.to_dict(),
            "alignment_validation": alignment_result.to_dict(),
            "audio_validation": audio_results,
            "recommendations": self._generate_recommendations(
                content_result, timing_result, alignment_result, audio_results
            ),
        }

        report_path = self.experiments_dir / "full_pipeline_validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 70}")
        print(f"全量验证完成")
        print(f"总分: {overall_score:.1f}")
        print(f"全部通过: {all_passed}")
        print(f"严重问题: {all_critical}")
        print(f"报告: {report_path}")

        return report

    def _generate_recommendations(
        self,
        content_result: ContentValidationResult,
        timing_result: SubtitleVerificationResult,
        alignment_result: AlignmentReport,
        audio_results: list,
    ) -> list[str]:
        recs = []

        if not content_result.passed:
            critical_types = set(i.issue_type for i in content_result.issues if i.severity == "critical")
            if "traditional_chinese_detected" in critical_types:
                recs.append("【紧急】字幕中仍存在繁体字，需加强繁简转换")
            if "errata_violation" in critical_types:
                recs.append("【紧急】字幕中存在勘误词，需添加纠错规则")
            if "multi_line_subtitle" in critical_types:
                recs.append("【紧急】字幕存在多行，需强制单行处理")

        if not timing_result.passed:
            recs.append("字幕时序验证未通过，需调整显示时长或阅读速度参数")

        if not alignment_result.publishing_ready:
            recs.append("字幕对齐未达发布标准，需优化时间戳精度")

        for ar in audio_results:
            if not ar.get("passed", True):
                for issue in ar.get("issues", []):
                    if issue.get("severity") == "critical":
                        recs.append(f"音频问题: {issue.get('description', '')}")

        if not recs:
            recs.append("所有验证通过，音视频制成品达标，可进入发布流程")

        return recs

    def run_iterative_research(self) -> dict:
        print("\n" + "=" * 70)
        print("阶段一：字幕内容规范性迭代")
        print("=" * 70)
        subtitle_report = self.subtitle_research.run_research()

        print("\n" + "=" * 70)
        print("阶段二：全量 Pipeline 验证")
        print("=" * 70)
        full_report = self.run_full_validation()

        retry_count = 0
        max_retries = 3
        while not full_report["all_passed"] and retry_count < max_retries:
            retry_count += 1
            print(f"\n" + "=" * 70)
            print(f"阶段二-{retry_count}：修复后第{retry_count}次验证")
            print("=" * 70)
            full_report = self.run_full_validation()

        combined = {
            "research_type": "comprehensive_subtitle_and_pipeline",
            "timestamp": datetime.now().isoformat(),
            "subtitle_content_research": {
                "total_iterations": subtitle_report["total_iterations"],
                "best_score": subtitle_report["best_score"],
                "final_passed": subtitle_report["final_passed"],
                "summary": subtitle_report["summary"],
            },
            "full_pipeline_validation": {
                "overall_score": full_report["overall_score"],
                "all_passed": full_report["all_passed"],
                "total_critical_issues": full_report["total_critical_issues"],
                "recommendations": full_report["recommendations"],
            },
            "final_status": "PASSED" if full_report["all_passed"] else "NEEDS_WORK",
        }

        combined_path = self.experiments_dir / "comprehensive_research_report.json"
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)

        return combined


def main():
    config = PipelineConfig()
    output_dir = config.output_dir

    research = FullPipelineResearch(config, output_dir)
    result = research.run_iterative_research()

    print(f"\n{'=' * 70}")
    print(f"最终状态: {result['final_status']}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
