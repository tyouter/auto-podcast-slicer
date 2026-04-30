import json
import subprocess
import re
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.subtitle_content import process_subtitle_content, generate_ass_with_rounded_bg

ctx = load_project()
config = ctx.config
custom_errata = ctx.custom_errata
transcript = ctx.transcript
entries = ctx.entries
merged = ctx.merged

OUTPUT_DIR = config.output_dir / "garden_forking_paths"
VIDEO_SOURCE = config.source_video

HIGHLIGHTS_CLIPS = config.get_clips("highlights")
PHILOSOPHY_CLIPS = config.get_clips("philosophy")
DIALOGUE_CLIPS = config.get_clips("dialogue")
WIKI_CLIPS = config.get_clips("deep_thinking")
IMMERSIVE_CLIPS = config.get_clips("immersive")

print(f"Loaded {len(entries)} subtitle entries")


def find_entry_at_time(t_s):
    for entry in entries:
        s = entry.start_ms / 1000
        e = entry.end_ms / 1000
        if s <= t_s <= e:
            return entry
    return None


def find_nearest_sentence_start(t_s, direction="after"):
    best = None
    best_dist = float("inf")
    for entry in entries:
        s = entry.start_ms / 1000
        text = entry.text.strip()
        if direction == "after" and s >= t_s:
            dist = s - t_s
            if dist < best_dist:
                best_dist = dist
                best = entry
        elif direction == "before" and s <= t_s:
            dist = t_s - s
            if dist < best_dist:
                best_dist = dist
                best = entry
    return best


def find_hook_time(hook_text, search_start, search_end):
    for entry in entries:
        s = entry.start_ms / 1000
        e = entry.end_ms / 1000
        if s >= search_start and e <= search_end:
            if hook_text in entry.text:
                return s
    return None


def is_sentence_complete(text):
    text = text.strip()
    if not text:
        return False
    endings = "。！？；：…—"
    if text[-1] in endings:
        return True
    if text.endswith("的") or text.endswith("了") or text.endswith("吧") or text.endswith("啊"):
        return True
    if text.endswith("我") or text.endswith("你") or text.endswith("他"):
        return False
    return True


def re_extract_audio_from_video(clip_id, clip_dir, start_s, end_s):
    wav_output = clip_dir / f"{clip_id}.wav"
    mp3_output = clip_dir / f"{clip_id}.mp3"
    duration_s = end_s - start_s

    if wav_output.exists():
        wav_output.unlink()
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s), "-to", str(end_s),
        "-i", str(VIDEO_SOURCE),
        "-vn",
        "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
        "-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2",
        str(wav_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    status = "OK" if result.returncode == 0 else f"FAIL: {result.stderr[:200]}"
    print(f"    WAV (48kHz stereo): {status}")

    if mp3_output.exists():
        mp3_output.unlink()
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s), "-to", str(end_s),
        "-i", str(VIDEO_SOURCE),
        "-vn",
        "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(mp3_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    status = "OK" if result.returncode == 0 else f"FAIL: {result.stderr[:200]}"
    print(f"    MP3 (192k 48kHz stereo): {status}")


def regenerate_subtitles(clip_id, clip_dir, start_s, end_s):
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
    with open(ass_output, "w", encoding="utf-8") as f:
        f.write(ass_content)

    srt_output = clip_dir / f"{clip_id}.srt"
    srt_lines = []
    for e in processed_entries:
        srt_lines.append(str(e["index"]))
        sh, sm, ss, sms = int(e["start_s"] // 3600), int((e["start_s"] % 3600) // 60), int(e["start_s"] % 60), int((e["start_s"] % 1) * 1000)
        eh, em, es, ems = int(e["end_s"] // 3600), int((e["end_s"] % 3600) // 60), int(e["end_s"] % 60), int((e["end_s"] % 1) * 1000)
        srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}")
        srt_lines.append(e["text"])
        srt_lines.append("")
    with open(srt_output, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    print(f"    Subtitles: {len(processed_entries)} entries")
    return processed_entries


def regenerate_video(clip_id, clip_dir, start_s, end_s, make_vertical=True):
    ass_output = clip_dir / f"{clip_id}.ass"
    duration_s = end_s - start_s

    video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
    if video_sub_output.exists():
        video_sub_output.unlink()
    ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
    vf_chain = f"subtitles='{ass_path_escaped}',scale=1920:1080"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s), "-to", str(end_s),
        "-i", str(VIDEO_SOURCE),
        "-vf", vf_chain,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(video_sub_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    status = "OK" if result.returncode == 0 else f"FAIL: {result.stderr[:200]}"
    print(f"    Video (CRF18): {status}")

    if make_vertical:
        video_vert_output = clip_dir / f"{clip_id}_vertical.mp4"
        if video_vert_output.exists():
            video_vert_output.unlink()
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
            "-i", str(VIDEO_SOURCE),
            "-vf", vf_chain,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            str(video_vert_output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        status = "OK" if result.returncode == 0 else f"FAIL: {result.stderr[:200]}"
        print(f"    Vertical: {status}")


def update_metadata(clip_dir, clip):
    metadata_path = clip_dir / "metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    metadata["start_s"] = clip["start_s"]
    metadata["end_s"] = clip["end_s"]
    metadata["duration_s"] = clip["end_s"] - clip["start_s"]
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def fix_clip(clip, clip_dir, make_vertical=True):
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    print(f"\n  Fixing: {clip_id} — {clip.get('title', '')} ({duration_s/60:.1f}min)")

    re_extract_audio_from_video(clip_id, clip_dir, start_s, end_s)
    regenerate_subtitles(clip_id, clip_dir, start_s, end_s)
    regenerate_video(clip_id, clip_dir, start_s, end_s, make_vertical=make_vertical)
    update_metadata(clip_dir, clip)


def adjust_clip_for_hook(clip):
    clip_id = clip["id"]
    hook = clip.get("hook", "")
    orig_start = clip["start_s"]
    orig_end = clip["end_s"]

    if not hook:
        return clip

    hook_time = find_hook_time(hook, max(0, orig_start - 30), orig_end)
    if hook_time is None:
        print(f"    Hook '{hook}' not found in range, keeping original cut")
        return clip

    if hook_time > orig_start + 3:
        new_start = hook_time
        print(f"    Hook adjusted: start {orig_start}s -> {new_start}s (hook found at {hook_time}s)")
        clip = {**clip, "start_s": new_start}

    return clip


def adjust_clip_for_completeness(clip):
    clip_id = clip["id"]
    orig_end = clip["end_s"]

    end_entry = find_entry_at_time(orig_end)
    if end_entry is None:
        nearest = find_nearest_sentence_start(orig_end, "before")
        if nearest:
            new_end = nearest.end_ms / 1000
            if new_end < orig_end:
                print(f"    End adjusted: {orig_end}s -> {new_end}s (nearest sentence end)")
                clip = {**clip, "end_s": new_end}
    else:
        text = end_entry.text.strip()
        if not is_sentence_complete(text):
            next_entry = None
            for entry in entries:
                s = entry.start_ms / 1000
                if s > orig_end and s < orig_end + 15:
                    next_entry = entry
                    break
            if next_entry:
                new_end = next_entry.end_ms / 1000
                print(f"    End extended: {orig_end}s -> {new_end}s (sentence completion)")
                clip = {**clip, "end_s": new_end}
            else:
                print(f"    End incomplete but no next entry found within 15s, keeping original")

    return clip


def fix_archive_exports():
    print("\n" + "=" * 60)
    print("FIX 4: Archive master re-export (ProRes 422 + PCM 24bit MOV)")
    print("=" * 60)

    archive_dir = OUTPUT_DIR / "platforms" / "archive"
    if not archive_dir.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)

    all_clips = []
    for clips_list in [HIGHLIGHTS_CLIPS, PHILOSOPHY_CLIPS, DIALOGUE_CLIPS, WIKI_CLIPS, IMMERSIVE_CLIPS]:
        all_clips.extend(clips_list)

    for clip in all_clips:
        clip_id = clip["id"]
        start_s = clip["start_s"]
        end_s = clip["end_s"]

        output_path = archive_dir / f"{clip_id}_subtitled_archive.mov"

        if output_path.exists():
            output_path.unlink()

        ass_path = OUTPUT_DIR
        for search_dir in [
            OUTPUT_DIR / "short_videos" / "highlights" / clip_id,
            OUTPUT_DIR / "short_videos" / "philosophy" / clip_id,
            OUTPUT_DIR / "short_videos" / "dialogue" / clip_id,
            OUTPUT_DIR / "long_videos" / "deep_thinking" / clip_id,
            OUTPUT_DIR / "long_videos" / "immersive" / clip_id,
        ]:
            candidate = search_dir / f"{clip_id}.ass"
            if candidate.exists():
                ass_path = candidate
                break

        if not ass_path.exists():
            print(f"  {clip_id}: ASS not found, skipping")
            continue

        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf_chain = f"subtitles='{ass_path_escaped}',scale=1920:1080"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_s), "-to", str(end_s),
            "-i", str(VIDEO_SOURCE),
            "-vf", vf_chain,
            "-c:v", "prores_ks", "-profile:v", "3",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            size_mb = output_path.stat().st_size / 1024 / 1024
            print(f"  {clip_id}: ProRes 422 MOV OK ({size_mb:.1f}MB)")
        else:
            print(f"  {clip_id}: ProRes FAIL - {result.stderr[:200]}")
            fallback_path = archive_dir / f"{clip_id}_subtitled_archive.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_s), "-to", str(end_s),
                "-i", str(VIDEO_SOURCE),
                "-vf", vf_chain,
                "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                "-pix_fmt", "yuv420p",
                "-c:a", "pcm_s24le", "-ar", "48000", "-ac", "2",
                str(fallback_path),
            ]
            result2 = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result2.returncode == 0:
                print(f"  {clip_id}: H.264 HQ fallback OK")


def fix_immersive_vertical():
    print("\n" + "=" * 60)
    print("FIX 5: Immersive series vertical video")
    print("=" * 60)

    for clip in IMMERSIVE_CLIPS:
        clip_id = clip["id"]
        clip_dir = OUTPUT_DIR / "long_videos" / "immersive" / clip_id
        start_s = clip["start_s"]
        end_s = clip["end_s"]

        vert_output = clip_dir / f"{clip_id}_vertical.mp4"
        if vert_output.exists():
            print(f"  {clip_id}: vertical already exists, skipping")
            continue

        ass_path = clip_dir / f"{clip_id}.ass"
        if not ass_path.exists():
            print(f"  {clip_id}: ASS not found, skipping")
            continue

        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
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
            "-i", str(VIDEO_SOURCE),
            "-vf", vf_chain,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            str(vert_output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            size_mb = vert_output.stat().st_size / 1024 / 1024
            print(f"  {clip_id}: Vertical OK ({size_mb:.1f}MB)")
        else:
            print(f"  {clip_id}: Vertical FAIL - {result.stderr[:200]}")


if __name__ == "__main__":
    print("=" * 60)
    print("AUTORESEARCH OPTIMIZATION — Quality Audit Fix")
    print("=" * 60)

    all_clips_with_dirs = []

    for clips_list, series_path in [
        (HIGHLIGHTS_CLIPS, "short_videos/highlights"),
        (PHILOSOPHY_CLIPS, "short_videos/philosophy"),
        (DIALOGUE_CLIPS, "short_videos/dialogue"),
    ]:
        print(f"\n{'='*60}")
        print(f"Processing: {series_path}")
        print(f"{'='*60}")

        for clip in clips_list:
            clip_dir = OUTPUT_DIR / series_path / clip["id"]
            if not clip_dir.exists():
                print(f"  {clip['id']}: directory not found, skipping")
                continue

            adjusted = adjust_clip_for_hook(clip)
            adjusted = adjust_clip_for_completeness(adjusted)

            fix_clip(adjusted, clip_dir, make_vertical=True)
            all_clips_with_dirs.append((adjusted, clip_dir))

    for clips_list, series_path in [
        (WIKI_CLIPS, "long_videos/deep_thinking"),
    ]:
        print(f"\n{'='*60}")
        print(f"Processing: {series_path}")
        print(f"{'='*60}")

        for clip in clips_list:
            clip_dir = OUTPUT_DIR / series_path / clip["id"]
            if not clip_dir.exists():
                continue

            adjusted = adjust_clip_for_completeness(clip)
            fix_clip(adjusted, clip_dir, make_vertical=True)
            all_clips_with_dirs.append((adjusted, clip_dir))

    for clips_list, series_path in [
        (IMMERSIVE_CLIPS, "long_videos/immersive"),
    ]:
        print(f"\n{'='*60}")
        print(f"Processing: {series_path}")
        print(f"{'='*60}")

        for clip in clips_list:
            clip_dir = OUTPUT_DIR / series_path / clip["id"]
            if not clip_dir.exists():
                continue

            adjusted = adjust_clip_for_completeness(clip)
            fix_clip(adjusted, clip_dir, make_vertical=False)
            all_clips_with_dirs.append((adjusted, clip_dir))

    fix_immersive_vertical()
    fix_archive_exports()

    print(f"\n{'='*60}")
    print("ALL FIXES COMPLETE")
    print(f"{'='*60}")
