import gc
import json
import time
import subprocess
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.subtitle_content import process_subtitle_content, generate_ass_with_rounded_bg

ctx = load_project()
config = ctx.config
entries = ctx.entries
merged = ctx.merged
custom_errata = ctx.custom_errata
transcript = ctx.transcript
audio_source = config.source_audio
video_source = config.source_video

OUTPUT_DIR = Path("output/short_videos_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HIGHLIGHTS = config.get_clips("highlights")
PHILOSOPHY = config.get_clips("philosophy")
DIALOGUE = config.get_clips("dialogue")

ALL_SERIES = [
    ("高光", HIGHLIGHTS),
    ("哲思", PHILOSOPHY),
    ("精彩对话", DIALOGUE),
]

log_lines = []
def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)

log(f"Loaded {len(entries)} subtitle entries")
log(f"Series: 高光({len(HIGHLIGHTS)}), 哲思({len(PHILOSOPHY)}), 精彩对话({len(DIALOGUE)})")
log(f"Output: {OUTPUT_DIR.resolve()}")
log("=" * 70)


def process_clip(clip, clip_dir, make_vertical=True, make_srt=True):
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    clip_dir.mkdir(parents=True, exist_ok=True)
    log(f"\n  Processing: {clip_id} — {clip.get('title', '')} ({duration_s/60:.1f}min)")

    audio_output = clip_dir / f"{clip_id}.wav"
    if audio_source.exists() and not audio_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s24le", str(audio_output),
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        log(f"    WAV {'OK' if audio_output.exists() else 'FAIL'}")

    mp3_output = clip_dir / f"{clip_id}.mp3"
    if audio_source.exists() and not mp3_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(mp3_output),
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        log(f"    MP3 {'OK' if mp3_output.exists() else 'FAIL'}")

    clip_entries_raw = []
    for entry in entries:
        entry_start_s = entry.start_ms / 1000
        entry_end_s = entry.end_ms / 1000
        if entry_start_s >= start_s and entry_end_s <= end_s:
            adjusted_start = entry_start_s - start_s
            adjusted_end = entry_end_s - start_s
        elif entry_start_s < end_s and entry_end_s > start_s:
            adjusted_start = max(entry_start_s, start_s) - start_s
            adjusted_end = min(entry_end_s, end_s) - start_s
        else:
            continue
        clip_entries_raw.append({
            "index": 0,
            "start_s": adjusted_start,
            "end_s": adjusted_end,
            "text": entry.text,
            "duration_s": adjusted_end - adjusted_start,
        })

    processed_entries = []
    for i, raw in enumerate(clip_entries_raw):
        next_text = clip_entries_raw[i + 1]["text"] if i + 1 < len(clip_entries_raw) else ""
        gap_s = (clip_entries_raw[i + 1]["start_s"] - raw["end_s"]) if i + 1 < len(clip_entries_raw) else 0
        is_last = (i == len(clip_entries_raw) - 1)
        processed_text = process_subtitle_content(
            text=raw["text"],
            duration_s=raw["duration_s"],
            next_text=next_text,
            gap_s=gap_s,
            max_chars=18,
            is_last=is_last,
            custom_errata=custom_errata,
            strip_punctuation=True,
        )
        processed_entries.append({
            "index": i + 1,
            "start_s": raw["start_s"],
            "end_s": raw["end_s"],
            "text": processed_text,
        })

    ass_output = clip_dir / f"{clip_id}.ass"
    ass_content = generate_ass_with_rounded_bg(
        entries=processed_entries,
        video_width=3840,
        video_height=2160,
        font_name="Noto Sans SC",
        font_size=104,
        bg_color="1A1A1A",
        bg_alpha=38,
        text_color="FFFFFF",
        corner_radius=24,
        padding_h=40,
        padding_v=20,
        margin_v=90,
    )
    ass_output.write_text(ass_content, encoding="utf-8")
    log(f"    ASS OK: {len(processed_entries)} entries")

    if make_srt:
        srt_output = clip_dir / f"{clip_id}.srt"
        if not srt_output.exists():
            srt_lines = []
            for e in processed_entries:
                srt_lines.append(str(e["index"]))
                sh, sm, ss, sms = int(e["start_s"] // 3600), int((e["start_s"] % 3600) // 60), int(e["start_s"] % 60), int((e["start_s"] % 1) * 1000)
                eh, em, es, ems = int(e["end_s"] // 3600), int((e["end_s"] % 3600) // 60), int(e["end_s"] % 60), int((e["end_s"] % 1) * 1000)
                srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}")
                srt_lines.append(e["text"])
                srt_lines.append("")
            srt_output.write_text("\n".join(srt_lines), encoding="utf-8")
            log(f"    SRT OK")

    if video_source.exists():
        video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
        if not video_sub_output.exists():
            ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
            vf_chain = f"subtitles='{ass_path_escaped}'"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_s), "-to", str(end_s),
                "-i", str(video_source),
                "-vf", vf_chain,
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                str(video_sub_output),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result.returncode == 0:
                log(f"    Video+Sub OK: {video_sub_output.stat().st_size / 1024 / 1024:.1f}MB")
            else:
                log(f"    Video+Sub FAIL: {result.stderr[:200]}")
            gc.collect()

        if make_vertical:
            video_vert_output = clip_dir / f"{clip_id}_vertical.mp4"
            if video_vert_output.exists():
                video_vert_output.unlink()
            ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
            vf_chain = (
                f"subtitles='{ass_path_escaped}',"
                f"split[bg][fg];"
                f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40[blurred];"
                f"[fg]scale=1080:-2[scaled];"
                f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
            )
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_s), "-to", str(end_s),
                "-i", str(video_source),
                "-vf", vf_chain,
                "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                str(video_vert_output),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result.returncode == 0:
                log(f"    Vertical OK: {video_vert_output.stat().st_size / 1024 / 1024:.1f}MB")
            else:
                log(f"    Vertical FAIL: {result.stderr[:200]}")
            gc.collect()

    metadata = {
        "id": clip_id,
        "title": clip.get("title", ""),
        "series": clip.get("series", ""),
        "description": clip.get("description", ""),
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": duration_s,
        "subtitle_count": len(processed_entries),
    }
    if "domain" in clip:
        metadata["domain"] = clip["domain"]
    if "hook" in clip:
        metadata["hook"] = clip["hook"]
    (clip_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return metadata


total_generated = 0
total_skipped = 0
t0 = time.time()

for series_name, clips in ALL_SERIES:
    series_dir = OUTPUT_DIR / series_name
    series_dir.mkdir(parents=True, exist_ok=True)

    log(f"\n{'=' * 60}")
    log(f"系列：{series_name} ({len(clips)} 条)")
    log(f"{'=' * 60}")

    for clip in clips:
        clip_id = clip["id"]
        clip_dir = series_dir / clip_id

        try:
            process_clip(clip, clip_dir, make_vertical=True, make_srt=True)
            total_generated += 1
        except Exception as e:
            log(f"    FAIL: {e}")
            total_skipped += 1

elapsed = time.time() - t0

log(f"\n{'=' * 70}")
log(f"DONE: {total_generated} clips generated, {total_skipped} skipped")
log(f"Total time: {elapsed:.1f}s")
log(f"Output: {OUTPUT_DIR.resolve()}")

summary = {
    "project": "garden_forking_paths_short_videos_v2",
    "series": [
        {"name": "高光", "count": len(HIGHLIGHTS)},
        {"name": "哲思", "count": len(PHILOSOPHY)},
        {"name": "精彩对话", "count": len(DIALOGUE)},
    ],
    "total_clips": total_generated + total_skipped,
    "generated": total_generated,
    "skipped": total_skipped,
    "elapsed_s": round(elapsed, 1),
    "source": "C0257",
}
summary_path = OUTPUT_DIR / "summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
log(f"Summary: {summary_path}")

with open("_rebuild_log.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))
