import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    generate_ass_with_rounded_bg,
)

config = PipelineConfig()
output_dir = config.output_dir

mixed_json_path = Path("D:/boke/garden post factory/C0257_full_mixed.json")
video_source = Path("D:/boke/garden post factory/C0257.MP4")
corrections_path = Path("config/corrections.yaml")

custom_errata = load_custom_errata(corrections_path)
transcript = parse_funasr_mixed_json(mixed_json_path)
entries, merged = process_transcript_to_subtitles(transcript, config)

clip_id = "time_03_time_and_possibility"
start_s = 1860
end_s = 2050
duration_s = end_s - start_s

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

print(f"Processed {len(processed_entries)} subtitle entries")
for e in processed_entries[:5]:
    print(f"  [{e['start_s']:.1f}-{e['end_s']:.1f}] {e['text']}")
print(f"  ...")

test_dir = output_dir / "test_debug"
test_dir.mkdir(parents=True, exist_ok=True)

ass_output = test_dir / f"{clip_id}.ass"
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
print(f"\nASS written: {ass_output}")

video_sub_output = test_dir / f"{clip_id}_subtitled.mp4"
ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
cmd = [
    "ffmpeg", "-y",
    "-ss", str(start_s), "-to", str(end_s),
    "-i", str(video_source),
    "-vf", f"subtitles='{ass_path_escaped}'",
    "-c:v", "libx264", "-preset", "medium", "-crf", "22",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
    str(video_sub_output)
]

print(f"\nGenerating test video...")
t0 = time.time()
result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
elapsed = time.time() - t0

if result.returncode == 0:
    size_mb = video_sub_output.stat().st_size / 1024 / 1024
    print(f"Video OK: {video_sub_output}")
    print(f"Size: {size_mb:.1f}MB, Time: {elapsed:.1f}s")
else:
    print(f"FAIL: {result.stderr[:500]}")

print(f"\nPlease review: {video_sub_output}")
