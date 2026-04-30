import json
import time
import subprocess
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    generate_ass_with_rounded_bg,
    get_frosted_glass_ffmpeg_filter,
)

ctx = load_project()
config = ctx.config
entries = ctx.entries
merged = ctx.merged
transcript = ctx.transcript
custom_errata = ctx.custom_errata
audio_source = config.source_audio
video_source = config.source_video
output_dir = config.output_dir

clips = [
    {
        "id": "clip01_literature",
        "title": "文学分岔：博尔赫斯与小径分岔的花园",
        "domain": "文学",
        "start_s": 640,
        "end_s": 780,
        "description": "讨论博尔赫斯《小径分岔的花园》的文学概念，时间分岔的核心隐喻",
    },
    {
        "id": "clip02_time_philosophy",
        "title": "时间分岔：时间在这里分岔",
        "domain": "时间哲学",
        "start_s": 1580,
        "end_s": 1700,
        "description": "深入讨论时间分岔的哲学含义，时间不是线性的而是分岔的",
    },
    {
        "id": "clip03_possibility",
        "title": "可能性分岔：我们产生了一个分岔",
        "domain": "可能性",
        "start_s": 530,
        "end_s": 680,
        "description": "讨论可能性的产生，每一次选择都是一个分岔点",
    },
    {
        "id": "clip04_ai_art",
        "title": "艺术分岔：一个艺术家就是一个分岔",
        "domain": "艺术与AI",
        "start_s": 3030,
        "end_s": 3180,
        "description": "用分岔原理解释艺术创作，AI时代的艺术分岔点",
    },
    {
        "id": "clip05_life_fork",
        "title": "人生分岔：从分岔的节点看人生",
        "domain": "人生",
        "start_s": 3340,
        "end_s": 3500,
        "description": "在时间点分岔处的人生选择，命运的分岔节点",
    },
    {
        "id": "clip06_uncertainty",
        "title": "不确定分岔：没有分岔了吗",
        "domain": "不确定性",
        "start_s": 4150,
        "end_s": 4280,
        "description": "从分岔的视角看不确定性，看得到分岔与看不到分岔",
    },
]

clips_dir = output_dir / "clips_fencha"
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

    print(f"\nProcessing: {clip['title']} ({clip['domain']}) [{duration_s/60:.1f}min]")

    # 1. Audio clip - skip if exists
    audio_output = clip_dir / f"{clip_id}.wav"
    if audio_source.exists() and not audio_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "pcm_s24le",
            str(audio_output)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(f"  Audio OK: {audio_output.stat().st_size / 1024 / 1024:.1f}MB")
        else:
            print(f"  Audio FAIL: {result.stderr[:100]}")
    elif audio_output.exists():
        print(f"  Audio WAV: SKIP (exists)")

    # 2. Audio clip as MP3 - skip if exists
    mp3_output = clip_dir / f"{clip_id}.mp3"
    if audio_source.exists() and not mp3_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(mp3_output)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(f"  MP3 OK: {mp3_output.stat().st_size / 1024:.0f}KB")
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
        "domain": clip["domain"],
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
    "project": "小径分岔的花园 — 分岔主题切片集",
    "source": "C0257",
    "total_clips": len(results),
    "generated_count": generated_count,
    "skipped_count": skipped_count,
    "total_time_s": round(total_time, 1),
    "domains": list(set(r["domain"] for r in results)),
    "clips": results,
}

with open(clips_dir / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"DONE: {len(results)} clips in {clips_dir}")
print(f"Generated: {generated_count}, Skipped: {skipped_count}")
print(f"Total time: {total_time:.1f}s")
for r in results:
    print(f"  {r['id']}: {r['title']} ({r['duration_s']/60:.1f}min)")
