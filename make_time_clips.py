import json
import time
import subprocess
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    generate_ass_with_rounded_bg,
    get_frosted_glass_ffmpeg_filter,
)

config = PipelineConfig()
output_dir = config.output_dir

mixed_json_path = Path("D:/boke/garden post factory/C0257_full_mixed.json")
audio_source = Path("D:/boke/garden post factory/C0257_mixed_normalized.wav")
video_source = Path("D:/boke/garden post factory/C0257.MP4")
corrections_path = Path("config/corrections.yaml")

custom_errata = load_custom_errata(corrections_path)

transcript = parse_funasr_mixed_json(mixed_json_path)
entries, merged = process_transcript_to_subtitles(transcript, config)

clips = [
    {
        "id": "time_01_garden_intro",
        "title": "小径分岔的花园：时间在这里分岔",
        "start_s": 580,
        "end_s": 750,
        "description": "从博尔赫斯《小径分岔的花园》引入时间分岔的概念，平行时空与所有可能性同时发生",
    },
    {
        "id": "time_02_simultaneous",
        "title": "所有可能性同时发生：时间的分岔点",
        "start_s": 1530,
        "end_s": 1720,
        "description": "深入讨论可能性同时发生，时间分岔的本质——不是选择，而是同时存在",
    },
    {
        "id": "time_03_time_and_possibility",
        "title": "可能性与时间：分岔到底意味着什么",
        "start_s": 1860,
        "end_s": 2050,
        "description": "可能性到底和时间有什么关系？选择可能性时的分岔意味着什么",
    },
    {
        "id": "time_04_different_paths",
        "title": "不同的路径：时间分岔中的选择",
        "start_s": 2960,
        "end_s": 3160,
        "description": "他们选择了不同的路径，所有可能性同时发生，关键时间节点上的分岔",
    },
    {
        "id": "time_05_critical_node",
        "title": "关键时间节点：命运的分岔路口",
        "start_s": 3450,
        "end_s": 3650,
        "description": "某个关键的时间节点，命运在此分岔，过去与未来的交汇",
    },
]

clips_dir = output_dir / "clips_time_bifurcation"
clips_dir.mkdir(parents=True, exist_ok=True)

results = []
total_start = time.time()
skipped_count = 0
generated_count = 0

for clip in clips:
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    clip_dir = clips_dir / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing: {clip['title']} [{duration_s/60:.1f}min]")

    # 1. Audio clip (WAV) - skip if exists
    audio_output = clip_dir / f"{clip_id}.wav"
    if audio_source.exists() and not audio_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "pcm_s24le",
            str(audio_output)
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        print(f"  Audio WAV OK: {audio_output.stat().st_size / 1024 / 1024:.1f}MB")
    elif audio_output.exists():
        print(f"  Audio WAV: SKIP (exists)")

    # 2. Audio clip (MP3) - skip if exists
    mp3_output = clip_dir / f"{clip_id}.mp3"
    if audio_source.exists() and not mp3_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(mp3_output)
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        print(f"  Audio MP3 OK: {mp3_output.stat().st_size / 1024:.0f}KB")
    elif mp3_output.exists():
        print(f"  Audio MP3: SKIP (exists)")

    # 3. Generate subtitle entries with content processing (punctuation stripped)
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

    # 4. Generate ASS with rounded rectangle background
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
    with open(ass_output, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"  ASS OK: {len(processed_entries)} entries")

    # 5. Video with ASS subtitles
    if video_source.exists():
        video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
        if video_sub_output.exists():
            print(f"  Video+Sub: SKIP (exists)")
            skipped_count += 1
        else:
            ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
            vf_chain = f"subtitles='{ass_path_escaped}'"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_s), "-to", str(end_s),
                "-i", str(video_source),
                "-vf", vf_chain,
                "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                str(video_sub_output)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result.returncode == 0:
                print(f"  Video+Sub OK: {video_sub_output.stat().st_size / 1024 / 1024:.1f}MB")
                generated_count += 1
            else:
                print(f"  Video+Sub FAIL: {result.stderr[:200]}")

    metadata = {
        "id": clip_id,
        "title": clip["title"],
        "description": clip["description"],
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": duration_s,
        "subtitle_count": len(processed_entries),
    }
    with open(clip_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    results.append(metadata)

total_time = time.time() - total_start

summary = {
    "project": "时间分岔 — 完整切片集",
    "source": "C0257",
    "total_clips": len(results),
    "generated_count": generated_count,
    "skipped_count": skipped_count,
    "total_time_s": round(total_time, 1),
    "clips": results,
}

with open(clips_dir / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'=' * 60}")
print(f"DONE: {len(results)} clips in {clips_dir}")
print(f"Generated: {generated_count}, Skipped: {skipped_count}")
print(f"Total time: {total_time:.1f}s")
for r in results:
    print(f"  {r['id']}: {r['title']} ({r['duration_s'] / 60:.1f}min)")
