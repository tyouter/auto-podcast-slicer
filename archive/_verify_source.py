import json
import subprocess
import time
from pathlib import Path
from pipeline.loader import load_project
from pipeline.subtitle_content import process_subtitle_content, generate_ass_with_rounded_bg

ctx = load_project()
config = ctx.config
entries = ctx.entries
custom_errata = ctx.custom_errata
video_source = config.source_video
audio_source = config.source_audio

HIGHLIGHTS = config.get_clips("highlights")
test_clip = HIGHLIGHTS[0]

print(f"=== 验证测试: {test_clip['id']} ===")
print(f"  标题: {test_clip.get('title', '')}")
print(f"  时间: {test_clip['start_s']}s - {test_clip['end_s']}s")

test_dir = Path("output/_verify_test") / test_clip["id"]
test_dir.mkdir(parents=True, exist_ok=True)

clip_id = test_clip["id"]
start_s = test_clip["start_s"]
end_s = test_clip["end_s"]
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
print(f"  ASS OK: {len(processed_entries)} entries")

# Test 1: 横版 (4K, no scale, CRF=20)
print("\n--- Test 1: 横版4K (CRF=20, no scale) ---")
video_sub_output = test_dir / f"{clip_id}_subtitled.mp4"
if video_sub_output.exists():
    video_sub_output.unlink()
ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
vf_chain = f"subtitles='{ass_path_escaped}'"
t0 = time.time()
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
t1 = time.time()
if result.returncode == 0:
    sz = video_sub_output.stat().st_size / 1024 / 1024
    print(f"  OK: {sz:.1f}MB, {t1-t0:.0f}s")
else:
    print(f"  FAIL: {result.stderr[:300]}")

# Test 2: 竖版 (1080x1920, -b:v 5000k)
print("\n--- Test 2: 竖版 (CBR 5000k) ---")
video_vert_output = test_dir / f"{clip_id}_vertical.mp4"
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
t0 = time.time()
cmd = [
    "ffmpeg", "-y",
    "-ss", str(start_s), "-to", str(end_s),
    "-i", str(video_source),
    "-vf", vf_chain,
    "-c:v", "libx264", "-preset", "medium", "-b:v", "5000k",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
    str(video_vert_output),
]
result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
t1 = time.time()
if result.returncode == 0:
    sz = video_vert_output.stat().st_size / 1024 / 1024
    print(f"  OK: {sz:.1f}MB, {t1-t0:.0f}s")
else:
    print(f"  FAIL: {result.stderr[:300]}")

# Verify with ffprobe
print("\n=== ffprobe 验证 ===")
for label, mp4 in [("横版", video_sub_output), ("竖版", video_vert_output)]:
    if not mp4.exists():
        print(f"  {label}: MISSING")
        continue
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration,bit_rate,pix_fmt,r_frame_rate",
         "-show_entries", "format=bit_rate,duration",
         "-of", "json", str(mp4)],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(r.stdout)
    streams = {}
    fmt = data.get("format", {})
    for s in data.get("streams", []):
        streams[s.get("codec_type")] = s
    v = streams.get("video", {})
    a = streams.get("audio", {})
    fmt_bitrate = int(fmt.get("bit_rate", 0)) / 1000
    print(f"  {label}:")
    print(f"    分辨率: {v.get('width')}x{v.get('height')}")
    print(f"    编码: {v.get('codec_name')} {v.get('pix_fmt')}")
    print(f"    帧率: {v.get('r_frame_rate')}")
    print(f"    码率: {fmt_bitrate:.0f}kbps")
    print(f"    时长: {fmt.get('duration')}s")
    print(f"    音频: {a.get('codec_name')} {a.get('sample_rate')}Hz")

print("\n=== 验证完成 ===")
