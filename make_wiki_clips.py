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
        "id": "wiki_01_origin",
        "title": "缘起：花园中的相遇",
        "chapter": "第一章 · 缘起",
        "description": "节目录制的缘起——在花园中偶然相遇，一只白颊椋鸟飞来，播客漫谈的开始",
        "start_s": 55,
        "end_s": 200,
    },
    {
        "id": "wiki_02_garden_metaphor",
        "title": "隐喻：小径分岔的花园",
        "chapter": "第二章 · 隐喻",
        "description": "博尔赫斯《小径分岔的花园》——时间分岔的核心文学隐喻，平行宇宙与无限可能",
        "start_s": 318,
        "end_s": 530,
    },
    {
        "id": "wiki_03_time_bifurcation",
        "title": "分岔：时间在这里分岔",
        "chapter": "第三章 · 分岔",
        "description": "时间不是线性的而是分岔的——所有可能性同时发生，时间分岔的哲学含义",
        "start_s": 580,
        "end_s": 780,
    },
    {
        "id": "wiki_04_possibility",
        "title": "可能性：我们产生了一个分岔",
        "chapter": "第四章 · 可能性",
        "description": "每一次选择都是一个分岔点——可能性与时间的关系，选择意味着什么",
        "start_s": 1530,
        "end_s": 1720,
    },
    {
        "id": "wiki_05_creation",
        "title": "创作：从观念出发",
        "chapter": "第五章 · 创作",
        "description": "创作是一个分岔——从观念出发，戏剧创作的信念与冲动",
        "start_s": 1860,
        "end_s": 2050,
    },
    {
        "id": "wiki_06_artist_fork",
        "title": "艺术家：一个艺术家就是一个分岔",
        "chapter": "第六章 · 艺术家",
        "description": "没有所谓的艺术，有的只是一个个艺术家——艺术创作的分岔原理",
        "start_s": 2960,
        "end_s": 3180,
    },
    {
        "id": "wiki_07_life_crossroad",
        "title": "人生：命运的分岔路口",
        "chapter": "第七章 · 人生",
        "description": "在时间点分岔处的人生选择——从分岔的节点看人生，命运的分岔路口",
        "start_s": 3340,
        "end_s": 3550,
    },
    {
        "id": "wiki_08_uncertainty",
        "title": "不确定：看得到与看不到的分岔",
        "chapter": "第八章 · 不确定",
        "description": "从分岔的视角看不确定性——看得到分岔与看不到分岔，未知的可能性",
        "start_s": 4150,
        "end_s": 4320,
    },
    {
        "id": "wiki_09_dream",
        "title": "梦境：白日梦与潜意识",
        "chapter": "第九章 · 梦境",
        "description": "利用白日梦去创作——进入无拘无束的状态，接触潜意识的世界",
        "start_s": 4950,
        "end_s": 5168,
    },
]

clips_dir = output_dir / "wiki_series"
clips_dir.mkdir(parents=True, exist_ok=True)

results = []
total_start = time.time()
generated_count = 0
skipped_count = 0

for clip in clips:
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    clip_dir = clips_dir / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Processing: {clip['chapter']} — {clip['title']}")
    print(f"  Time: {start_s}s-{end_s}s ({duration_s/60:.1f}min)")

    # 1. Audio clip (WAV)
    audio_output = clip_dir / f"{clip_id}.wav"
    if audio_source.exists() and not audio_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "pcm_s24le",
            str(audio_output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(f"  Audio WAV OK: {audio_output.stat().st_size / 1024 / 1024:.1f}MB")
        else:
            print(f"  Audio WAV FAIL: {result.stderr[:100]}")
    elif audio_output.exists():
        print(f"  Audio WAV: SKIP (exists)")

    # 2. Audio clip (MP3)
    mp3_output = clip_dir / f"{clip_id}.mp3"
    if audio_source.exists() and not mp3_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(mp3_output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode == 0:
            print(f"  Audio MP3 OK: {mp3_output.stat().st_size / 1024:.0f}KB")
        else:
            print(f"  Audio MP3 FAIL: {result.stderr[:100]}")
    elif mp3_output.exists():
        print(f"  Audio MP3: SKIP (exists)")

    # 3. Generate subtitle entries with content processing
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

    # 5. SRT subtitle
    srt_output = clip_dir / f"{clip_id}.srt"
    if not srt_output.exists():
        srt_lines = []
        for entry in processed_entries:
            srt_lines.append(str(entry["index"]))
            sh, sm, ss, sms = int(entry["start_s"] // 3600), int((entry["start_s"] % 3600) // 60), int(entry["start_s"] % 60), int((entry["start_s"] % 1) * 1000)
            eh, em, es, ems = int(entry["end_s"] // 3600), int((entry["end_s"] % 3600) // 60), int(entry["end_s"] % 60), int((entry["end_s"] % 1) * 1000)
            srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}")
            srt_lines.append(entry["text"])
            srt_lines.append("")
        with open(srt_output, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        print(f"  SRT OK")
    else:
        print(f"  SRT: SKIP (exists)")

    # 6. Video with ASS subtitles (4K source → 1080p output)
    if video_source.exists():
        video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
        if video_sub_output.exists():
            print(f"  Video+Sub: SKIP (exists)")
            skipped_count += 1
        else:
            ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
            vf_chain = f"subtitles='{ass_path_escaped}',scale=1920:1080"
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
                print(f"  Video+Sub OK: {video_sub_output.stat().st_size / 1024 / 1024:.1f}MB")
                generated_count += 1
            else:
                print(f"  Video+Sub FAIL: {result.stderr[:200]}")

    # 7. Vertical video for short-form platforms (9:16)
    #    Strategy: scale entire frame to fit width, fill remaining height with blurred background
    if video_source.exists():
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
            print(f"  Vertical OK: {video_vert_output.stat().st_size / 1024 / 1024:.1f}MB")
        else:
            print(f"  Vertical FAIL: {result.stderr[:200]}")

    metadata = {
        "id": clip_id,
        "title": clip["title"],
        "chapter": clip["chapter"],
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
    "project": "小径分岔的花园 — Wiki知识结构混剪系列",
    "source": "C0257",
    "total_clips": len(results),
    "generated_count": generated_count,
    "skipped_count": skipped_count,
    "total_time_s": round(total_time, 1),
    "chapters": [r["chapter"] for r in results],
    "clips": results,
}

with open(clips_dir / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"DONE: {len(results)} clips in {clips_dir}")
print(f"Generated: {generated_count}, Skipped: {skipped_count}")
print(f"Total time: {total_time:.1f}s")
print(f"\nWiki知识结构混剪系列：")
for r in results:
    print(f"  {r['chapter']} — {r['title']} ({r['duration_s']/60:.1f}min, {r['subtitle_count']}条字幕)")
