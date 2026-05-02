import gc
import json
import time
import subprocess
from pathlib import Path
from pipeline.loader import load_project
from pipeline.subtitle_content import process_subtitle_content, generate_ass_with_rounded_bg

ctx = load_project()
config = ctx.config
entries = ctx.entries
custom_errata = ctx.custom_errata
video_source = config.source_video

OUTPUT_DIR = Path("output/short_videos_v2")

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

def regenerate_vertical(clip, clip_dir):
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]

    ass_output = clip_dir / f"{clip_id}.ass"
    if not ass_output.exists():
        log(f"  SKIP {clip_id}: ASS not found")
        return False

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
        "-c:v", "libx264", "-preset", "medium", "-b:v", "5000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        str(video_vert_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:
        sz = video_vert_output.stat().st_size / 1024 / 1024
        log(f"  {clip_id} Vertical OK: {sz:.1f}MB")
        gc.collect()
        return True
    else:
        log(f"  {clip_id} Vertical FAIL: {result.stderr[:200]}")
        gc.collect()
        return False

t0 = time.time()
ok = 0
fail = 0

for series_name, clips in ALL_SERIES:
    series_dir = OUTPUT_DIR / series_name
    log(f"\n--- {series_name} ({len(clips)} clips) ---")
    for clip in clips:
        clip_dir = series_dir / clip["id"]
        if regenerate_vertical(clip, clip_dir):
            ok += 1
        else:
            fail += 1

elapsed = time.time() - t0
log(f"\nDONE: {ok} OK, {fail} FAIL, {elapsed:.0f}s")

with open("_vertical_regen_log.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines))
