import argparse
import time
import json
from pathlib import Path

from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.clip_processor import process_series


def main():
    parser = argparse.ArgumentParser(description="Unified clip processing CLI")
    parser.add_argument("--project", "-p", help="Project directory path", default=None)
    parser.add_argument("--series", "-s", help="Series name(s) to process (comma-separated, default: all)", default=None)
    parser.add_argument("--no-vertical", action="store_true", help="Skip vertical video generation")
    parser.add_argument("--no-srt", action="store_true", help="Skip SRT generation")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--max-chars", type=int, default=18, help="Max characters per subtitle line")
    parser.add_argument("--list-series", action="store_true", help="List available series and exit")
    args = parser.parse_args()

    ctx = load_project(project_dir=args.project)
    config = ctx.config
    entries = ctx.entries
    custom_errata = ctx.custom_errata
    audio_source = config.source_audio
    video_source = config.source_video
    output_dir = config.output_dir

    all_clips = config.get_all_clips()

    if args.list_series:
        print(f"Project: {config.project_name}")
        print(f"Available series:")
        for name, clips in all_clips.items():
            print(f"  {name}: {len(clips)} clips")
        return

    if not all_clips:
        print("No clip series found in project configuration.")
        return

    series_filter = None
    if args.series:
        series_filter = set(s.strip() for s in args.series.split(","))

    print(f"Project: {config.project_name}")
    print(f"Loaded {len(entries)} subtitle entries")
    print(f"Output: {output_dir.resolve()}")
    print("=" * 70)

    total_generated = 0
    total_skipped = 0
    t0 = time.time()

    for series_name, clips in all_clips.items():
        if series_filter and series_name not in series_filter:
            continue

        series_dir = output_dir / series_name
        print(f"\n{'=' * 60}")
        print(f"Series: {series_name} ({len(clips)} clips)")
        print(f"{'=' * 60}")

        results = process_series(
            clips=clips,
            series_dir=series_dir,
            entries=entries,
            audio_source=audio_source,
            video_source=video_source,
            custom_errata=custom_errata,
            make_vertical=not args.no_vertical,
            make_srt=not args.no_srt,
            skip_existing=not args.force,
            max_chars=args.max_chars,
            series_name=series_name,
            project_name=config.project_name,
            source_id=config.project_name,
        )

        for r in results:
            if r.errors:
                print(f"  {r.clip_id}: FAIL - {r.errors}")
                total_skipped += 1
            else:
                print(f"  {r.clip_id}: OK ({r.duration_s/60:.1f}min, {r.subtitle_count} subs)")
                total_generated += 1

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"DONE: {total_generated} clips generated, {total_skipped} skipped")
    print(f"Total time: {elapsed:.1f}s")
    print(f"Output: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
