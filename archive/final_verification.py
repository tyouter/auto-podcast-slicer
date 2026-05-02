import json
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.transcribe import TranscriptResult, TranscriptSegment
from pipeline.subtitle_generator import SubtitleResult
from pipeline.alignment_verifier import run_full_alignment_verification

ctx = load_project()
config = ctx.config
entries = ctx.entries
merged = ctx.merged
transcript = ctx.transcript

subtitle_result = SubtitleResult(entries=entries, format="srt", source_file=transcript.source_file)

merged_transcript = TranscriptResult(
    segments=[TranscriptSegment(start_ms=m.start_ms, end_ms=m.end_ms, text=m.text) for m in merged],
    source_file=transcript.source_file, engine="merged", language="zh", duration_s=transcript.duration_s,
)
alignment_report = run_full_alignment_verification(merged_transcript, config)

srt_dir = config.output_dir / "srt"
srt_dir.mkdir(parents=True, exist_ok=True)
srt_path = srt_dir / "C0257_aligned.srt"
subtitle_result.save_srt(srt_path)

print("=" * 70)
print("FINAL VERIFICATION REPORT")
print("=" * 70)
print(f"\nSource: C0257_full_mixed.json ({transcript.duration_s/60:.1f} minutes)")
print(f"Raw segments: {len(transcript.segments)}")
print(f"Merged subtitle entries: {len(entries)}")
print(f"Compression ratio: {len(transcript.segments)/len(entries):.1f}x")

print(f"\n--- ALIGNMENT SCORES ---")
print(f"Overall alignment: {alignment_report.alignment_score:.1f}/100")
print(f"Coverage: {alignment_report.coverage_score:.1f}%")
print(f"Timing accuracy: {alignment_report.timing_accuracy_score:.1f}%")
print(f"Continuity: {alignment_report.continuity_score:.1f}%")
print(f"Interruption quality: {alignment_report.interruption_quality_score:.1f}%")

print(f"\n--- PUBLISHING STATUS ---")
print(f"Alignment passed: {alignment_report.passed}")
print(f"Publishing ready: {alignment_report.publishing_ready}")
print(f"Critical issues: {sum(1 for i in alignment_report.issues if i.get('severity') == 'critical')}")
print(f"Warnings: {sum(1 for i in alignment_report.issues if i.get('severity') == 'warning')}")
print(f"Info: {sum(1 for i in alignment_report.issues if i.get('severity') == 'info')}")

issue_types = {}
for issue in alignment_report.issues:
    t = issue.get("issue_type", "unknown")
    s = issue.get("severity", "unknown")
    key = f"{s}:{t}"
    issue_types[key] = issue_types.get(key, 0) + 1

print(f"\n--- ISSUE BREAKDOWN ---")
for key, count in sorted(issue_types.items(), key=lambda x: -x[1]):
    print(f"  {key}: {count}")

print(f"\n--- SRT OUTPUT ---")
print(f"Saved to: {srt_path}")
print(f"File size: {srt_path.stat().st_size / 1024:.1f} KB")

durations = [e.duration_s for e in entries]
print(f"\n--- DURATION DISTRIBUTION ---")
print(f"  Min: {min(durations):.2f}s | Max: {max(durations):.2f}s | Avg: {sum(durations)/len(durations):.2f}s")
print(f"  1-3s: {sum(1 for d in durations if 1 <= d < 3)} | 3-5s: {sum(1 for d in durations if 3 <= d < 5)} | 5-7s: {sum(1 for d in durations if 5 <= d < 7)} | >7s: {sum(1 for d in durations if d >= 7)}")

report_path = config.output_dir / "final_verification_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump({
        "alignment": alignment_report.to_dict(),
        "stats": {"raw_segments": len(transcript.segments), "merged_entries": len(entries), "duration_s": transcript.duration_s},
    }, f, ensure_ascii=False, indent=2, default=str)
print(f"\nFull report saved to: {report_path}")
