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

print("Loading transcript...")
transcript = parse_funasr_mixed_json(mixed_json_path)
entries, merged = process_transcript_to_subtitles(transcript, config)
print(f"Loaded {len(entries)} subtitle entries")


def process_clip(clip, clip_dir, make_vertical=True, make_srt=True):
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    clip_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Processing: {clip_id} — {clip.get('title', '')} ({duration_s/60:.1f}min)")

    audio_output = clip_dir / f"{clip_id}.wav"
    if audio_source.exists() and not audio_output.exists():
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_source),
            "-ss", str(start_s), "-to", str(end_s),
            "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={duration_s - 0.1}:d=0.1",
            "-c:a", "pcm_s24le",
            str(audio_output),
        ]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if audio_output.exists():
            print(f"    WAV OK")
        else:
            print(f"    WAV FAIL")

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
        if mp3_output.exists():
            print(f"    MP3 OK")

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
    print(f"    ASS OK: {len(processed_entries)} entries")

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
            with open(srt_output, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_lines))
            print(f"    SRT OK")

    if video_source.exists():
        video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
        if not video_sub_output.exists():
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
                print(f"    Video+Sub OK: {video_sub_output.stat().st_size / 1024 / 1024:.1f}MB")
            else:
                print(f"    Video+Sub FAIL: {result.stderr[:200]}")

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
                print(f"    Vertical OK: {video_vert_output.stat().st_size / 1024 / 1024:.1f}MB")
            else:
                print(f"    Vertical FAIL: {result.stderr[:200]}")

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
    if "chapter" in clip:
        metadata["chapter"] = clip["chapter"]
    if "hook" in clip:
        metadata["hook"] = clip["hook"]
    with open(clip_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


HIGHLIGHTS_CLIPS = [
    {
        "id": "H01_time_bifurcates",
        "title": "时间不是线性的，是分岔的",
        "series": "高光",
        "description": "时间在这里分岔了——从博尔赫斯到时间哲学的核心洞见",
        "start_s": 1580,
        "end_s": 1610,
        "hook": "时间在这里分岔了",
        "domain": "时间哲学",
    },
    {
        "id": "H02_no_art_only_artists",
        "title": "没有所谓的艺术，有的只是一个个艺术家",
        "series": "高光",
        "description": "用分岔原理解释艺术创作——每个艺术家就是一个分岔",
        "start_s": 3030,
        "end_s": 3055,
        "hook": "没有所谓的艺术，有的只是一个个艺术家",
        "domain": "艺术与AI",
    },
    {
        "id": "H03_every_choice_is_fork",
        "title": "每一次选择，都是一个分岔点",
        "series": "高光",
        "description": "我们产生了一个分岔——可能性与选择的关系",
        "start_s": 530,
        "end_s": 565,
        "hook": "我们产生了一个分岔",
        "domain": "可能性",
    },
    {
        "id": "H04_fate_crossroad",
        "title": "命运的分岔路口",
        "series": "高光",
        "description": "在某个关键的时间节点，命运在此分岔",
        "start_s": 3340,
        "end_s": 3380,
        "hook": "在某个关键的时间节点",
        "domain": "人生",
    },
    {
        "id": "H05_simultaneous_possibilities",
        "title": "所有可能性同时发生",
        "series": "高光",
        "description": "不是选择，而是同时存在——时间分岔的本质",
        "start_s": 1530,
        "end_s": 1565,
        "hook": "所有可能性同时发生",
        "domain": "可能性",
    },
    {
        "id": "H06_invisible_forks",
        "title": "看得到与看不到的分岔",
        "series": "高光",
        "description": "还有分岔吗？看不到的分岔——不确定性的哲学",
        "start_s": 4150,
        "end_s": 4185,
        "hook": "还有分岔吗",
        "domain": "不确定性",
    },
]

PHILOSOPHY_CLIPS = [
    {
        "id": "P01_borges_and_time",
        "title": "博尔赫斯与时间分岔",
        "series": "哲思",
        "description": "文学如何预言了物理学的多世界诠释——博尔赫斯《小径分岔的花园》的深层解读",
        "start_s": 640,
        "end_s": 780,
        "hook": "博尔赫斯写了一个关于时间分岔的故事",
        "domain": "文学",
    },
    {
        "id": "P02_time_bifurcation_deep",
        "title": "时间在这里分岔",
        "series": "哲思",
        "description": "时间的非线性本质——深入讨论时间分岔的哲学含义",
        "start_s": 1580,
        "end_s": 1700,
        "hook": "时间在这里分岔了",
        "domain": "时间哲学",
    },
    {
        "id": "P03_possibility_means",
        "title": "可能性意味着什么",
        "series": "哲思",
        "description": "选择与可能性的关系——每一次选择都是一个分岔点",
        "start_s": 530,
        "end_s": 680,
        "hook": "可能性到底意味着什么",
        "domain": "可能性",
    },
    {
        "id": "P04_artist_as_fork",
        "title": "艺术家就是分岔",
        "series": "哲思",
        "description": "AI时代的艺术创作分岔——没有所谓的艺术，有的只是一个个艺术家",
        "start_s": 3030,
        "end_s": 3180,
        "hook": "一个艺术家就是一个分岔",
        "domain": "艺术与AI",
    },
    {
        "id": "P05_life_fork_deep",
        "title": "从分岔节点看人生",
        "series": "哲思",
        "description": "命运的偶然与必然——在时间点分岔处的人生选择",
        "start_s": 3340,
        "end_s": 3500,
        "hook": "从分岔的节点看人生",
        "domain": "人生",
    },
    {
        "id": "P06_uncertainty_deep",
        "title": "不确定的分岔",
        "series": "哲思",
        "description": "已知与未知的边界——看得到分岔与看不到分岔",
        "start_s": 4150,
        "end_s": 4280,
        "hook": "看得到分岔与看不到分岔",
        "domain": "不确定性",
    },
]

DIALOGUE_CLIPS = [
    {
        "id": "D01_identity_collision",
        "title": "你怎么定义自己？",
        "series": "精彩对话",
        "description": "导演vs产品经理——身份标签的碰撞与反思",
        "start_s": 424,
        "end_s": 530,
        "hook": "你怎么定义自己",
    },
    {
        "id": "D02_naming_the_show",
        "title": "这个节目叫什么？",
        "series": "精彩对话",
        "description": "节目命名的即兴讨论——小径分岔的花园如何诞生",
        "start_s": 318,
        "end_s": 420,
        "hook": "我们这个节目名称叫什么",
    },
    {
        "id": "D03_bird_arrives",
        "title": "白颊椋鸟来了",
        "series": "精彩对话",
        "description": "自然介入的奇妙时刻——一只鸟飞来，与分岔主题的偶然呼应",
        "start_s": 57,
        "end_s": 94,
        "hook": "你看那有一只鸟过来",
    },
    {
        "id": "D04_no_certain_ending",
        "title": "不追求确定的结局",
        "series": "精彩对话",
        "description": "探索型vs设计型——这个节目不追求确定的结局",
        "start_s": 100,
        "end_s": 215,
        "hook": "他不追求一个确定的结局",
    },
    {
        "id": "D05_daydream_creation",
        "title": "利用白日梦去创作",
        "series": "精彩对话",
        "description": "关于创作方法的深度对话——进入无拘无束的状态",
        "start_s": 4950,
        "end_s": 5100,
        "hook": "利用白日梦去创作",
    },
]

WIKI_CLIPS = [
    {
        "id": "wiki_01_origin",
        "title": "缘起：花园中的相遇",
        "chapter": "第一章 · 缘起",
        "series": "深度思考",
        "description": "节目录制的缘起——在花园中偶然相遇，一只白颊椋鸟飞来，播客漫谈的开始",
        "start_s": 55,
        "end_s": 200,
    },
    {
        "id": "wiki_02_garden_metaphor",
        "title": "隐喻：小径分岔的花园",
        "chapter": "第二章 · 隐喻",
        "series": "深度思考",
        "description": "博尔赫斯《小径分岔的花园》——时间分岔的核心文学隐喻，平行宇宙与无限可能",
        "start_s": 318,
        "end_s": 530,
    },
    {
        "id": "wiki_03_time_bifurcation",
        "title": "分岔：时间在这里分岔",
        "chapter": "第三章 · 分岔",
        "series": "深度思考",
        "description": "时间不是线性的而是分岔的——所有可能性同时发生，时间分岔的哲学含义",
        "start_s": 580,
        "end_s": 780,
    },
    {
        "id": "wiki_04_possibility",
        "title": "可能性：我们产生了一个分岔",
        "chapter": "第四章 · 可能性",
        "series": "深度思考",
        "description": "每一次选择都是一个分岔点——可能性与时间的关系，选择意味着什么",
        "start_s": 1530,
        "end_s": 1720,
    },
    {
        "id": "wiki_05_creation",
        "title": "创作：从观念出发",
        "chapter": "第五章 · 创作",
        "series": "深度思考",
        "description": "创作是一个分岔——从观念出发，戏剧创作的信念与冲动",
        "start_s": 1860,
        "end_s": 2050,
    },
    {
        "id": "wiki_06_artist_fork",
        "title": "艺术家：一个艺术家就是一个分岔",
        "chapter": "第六章 · 艺术家",
        "series": "深度思考",
        "description": "没有所谓的艺术，有的只是一个个艺术家——艺术创作的分岔原理",
        "start_s": 2960,
        "end_s": 3180,
    },
    {
        "id": "wiki_07_life_crossroad",
        "title": "人生：命运的分岔路口",
        "chapter": "第七章 · 人生",
        "series": "深度思考",
        "description": "在时间点分岔处的人生选择——从分岔的节点看人生，命运的分岔路口",
        "start_s": 3340,
        "end_s": 3550,
    },
    {
        "id": "wiki_08_uncertainty",
        "title": "不确定：看得到与看不到的分岔",
        "chapter": "第八章 · 不确定",
        "series": "深度思考",
        "description": "从分岔的视角看不确定性——看得到分岔与看不到分岔，未知的可能性",
        "start_s": 4150,
        "end_s": 4320,
    },
    {
        "id": "wiki_09_dream",
        "title": "梦境：白日梦与潜意识",
        "chapter": "第九章 · 梦境",
        "series": "深度思考",
        "description": "利用白日梦去创作——进入无拘无束的状态，接触潜意识的世界",
        "start_s": 4950,
        "end_s": 5168,
    },
]

IMMERSIVE_CLIPS = [
    {
        "id": "immersive_p1",
        "title": "花园漫谈·上",
        "series": "沉浸式场域",
        "description": "开场、鸟鸣、节目缘起、博尔赫斯——花园中的完整对话上半场",
        "start_s": 55,
        "end_s": 1800,
    },
    {
        "id": "immersive_p2",
        "title": "花园漫谈·下",
        "series": "沉浸式场域",
        "description": "时间分岔、创作、人生、梦境——花园中的完整对话下半场",
        "start_s": 1800,
        "end_s": 5168,
    },
]


def run_workflow2():
    print("\n" + "=" * 60)
    print("WORKFLOW 2: 内容原子化 — 短视频系列")
    print("=" * 60)

    project_dir = output_dir / "garden_forking_paths" / "short_videos"
    all_results = []

    for series_name, clips in [("highlights", HIGHLIGHTS_CLIPS), ("philosophy", PHILOSOPHY_CLIPS), ("dialogue", DIALOGUE_CLIPS)]:
        series_dir = project_dir / series_name
        print(f"\n--- Series: {series_name} ({len(clips)} clips) ---")

        series_results = []
        for clip in clips:
            clip_dir = series_dir / clip["id"]
            result = process_clip(clip, clip_dir, make_vertical=True, make_srt=True)
            series_results.append(result)

        summary = {
            "series": series_name,
            "total_clips": len(series_results),
            "clips": series_results,
        }
        with open(series_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        all_results.extend(series_results)
        print(f"\n  {series_name}: {len(series_results)} clips done")

    return all_results


def run_workflow3():
    print("\n" + "=" * 60)
    print("WORKFLOW 3: 知识混剪 — 深度思考系列")
    print("=" * 60)

    project_dir = output_dir / "garden_forking_paths" / "long_videos" / "deep_thinking"
    results = []

    for clip in WIKI_CLIPS:
        clip_dir = project_dir / clip["id"]
        result = process_clip(clip, clip_dir, make_vertical=True, make_srt=True)
        results.append(result)

    summary = {
        "project": "小径分岔的花园 — 深度思考系列",
        "source": "C0257",
        "total_clips": len(results),
        "chapters": [r.get("chapter", "") for r in results],
        "clips": results,
    }
    with open(project_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return results


def run_workflow1_immersive():
    print("\n" + "=" * 60)
    print("WORKFLOW 1 (变体): 沉浸式场域 — 长视频最小干预剪辑")
    print("=" * 60)

    project_dir = output_dir / "garden_forking_paths" / "long_videos" / "immersive"
    results = []

    for clip in IMMERSIVE_CLIPS:
        clip_id = clip["id"]
        start_s = clip["start_s"]
        end_s = clip["end_s"]
        duration_s = end_s - start_s

        clip_dir = project_dir / clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  Processing: {clip_id} — {clip['title']} ({duration_s/60:.1f}min)")

        audio_output = clip_dir / f"{clip_id}.wav"
        if audio_source.exists() and not audio_output.exists():
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_source),
                "-ss", str(start_s), "-to", str(end_s),
                "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={duration_s - 1.0}:d=1.0",
                "-c:a", "pcm_s24le",
                str(audio_output),
            ]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            print(f"    WAV OK" if audio_output.exists() else "    WAV FAIL")

        mp3_output = clip_dir / f"{clip_id}.mp3"
        if audio_source.exists() and not mp3_output.exists():
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_source),
                "-ss", str(start_s), "-to", str(end_s),
                "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={duration_s - 1.0}:d=1.0",
                "-c:a", "libmp3lame", "-b:a", "192k",
                str(mp3_output),
            ]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            print(f"    MP3 OK" if mp3_output.exists() else "    MP3 FAIL")

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
            bg_alpha=56,
            text_color="FFFFFF",
            corner_radius=24,
            padding_h=40,
            padding_v=20,
            margin_v=90,
        )
        with open(ass_output, "w", encoding="utf-8") as f:
            f.write(ass_content)
        print(f"    ASS OK: {len(processed_entries)} entries (semi-transparent for immersive)")

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
            with open(srt_output, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_lines))
            print(f"    SRT OK")

        if video_source.exists():
            video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
            if not video_sub_output.exists():
                ass_path_escaped = str(ass_output).replace("\\", "/").replace(":", "\\:")
                vf_chain = f"subtitles='{ass_path_escaped}',scale=1920:1080"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_s), "-to", str(end_s),
                    "-i", str(video_source),
                    "-vf", vf_chain,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    str(video_sub_output),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
                if result.returncode == 0:
                    print(f"    Video+Sub OK: {video_sub_output.stat().st_size / 1024 / 1024:.1f}MB")
                else:
                    print(f"    Video+Sub FAIL: {result.stderr[:200]}")

        metadata = {
            "id": clip_id,
            "title": clip["title"],
            "series": clip["series"],
            "description": clip["description"],
            "start_s": start_s,
            "end_s": end_s,
            "duration_s": duration_s,
            "subtitle_count": len(processed_entries),
            "editing_style": "minimal_intervention",
        }
        with open(clip_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        results.append(metadata)

    summary = {
        "project": "小径分岔的花园 — 沉浸式场域系列",
        "source": "C0257",
        "total_clips": len(results),
        "clips": results,
    }
    with open(project_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return results


def run_workflow4():
    print("\n" + "=" * 60)
    print("WORKFLOW 4: 全平台出品")
    print("=" * 60)

    from pipeline.exporter import export_for_platform, export_audio_only

    project_dir = output_dir / "garden_forking_paths"
    platforms_dir = project_dir / "platforms"
    platforms = ["bilibili", "douyin", "youtube", "xiaoyuzhou", "apple_podcasts", "archive"]

    all_videos = []
    for search_dir in [
        project_dir / "short_videos" / "highlights",
        project_dir / "short_videos" / "philosophy",
        project_dir / "short_videos" / "dialogue",
        project_dir / "long_videos" / "deep_thinking",
        project_dir / "long_videos" / "immersive",
    ]:
        if search_dir.exists():
            for mp4_file in sorted(search_dir.rglob("*_subtitled.mp4")):
                all_videos.append(mp4_file)
            for mp4_file in sorted(search_dir.rglob("*_vertical.mp4")):
                all_videos.append(mp4_file)

    print(f"\nFound {len(all_videos)} videos to export")

    export_results = []
    for video_path in all_videos:
        clip_id = video_path.stem.replace("_subtitled", "").replace("_vertical", "")
        is_vertical = "_vertical" in video_path.stem

        for platform in platforms:
            if platform == "douyin" and not is_vertical:
                continue
            if platform in ("bilibili", "youtube") and is_vertical:
                continue
            if platform in ("xiaoyuzhou", "apple_podcasts"):
                audio_result = export_audio_only(
                    video_path,
                    platforms_dir / platform,
                    platform,
                    config,
                )
                export_results.append(audio_result.to_dict())
                continue
            if platform == "archive" and is_vertical:
                continue

            srt_path = video_path.parent / f"{clip_id}.srt"
            subtitle_path = srt_path if srt_path.exists() else None

            result = export_for_platform(
                video_path,
                platforms_dir / platform,
                platform,
                config,
                subtitle_path,
            )
            export_results.append(result.to_dict())
            status = "OK" if result.success else f"FAIL: {result.issues}"
            print(f"  {clip_id} → {platform}: {status}")

    with open(platforms_dir / "export_report.json", "w", encoding="utf-8") as f:
        json.dump(export_results, f, ensure_ascii=False, indent=2)

    return export_results


def run_workflow5():
    print("\n" + "=" * 60)
    print("WORKFLOW 5: 素材库打包")
    print("=" * 60)

    project_dir = output_dir / "garden_forking_paths"

    copyright_text = """# 版权声明

## 原始素材
- 录制日期：2024年
- 参与者：于传奇（青年编剧/导演）、任（产品经理/打工人）
- 录制地点：花园户外场景

## 内容版权
- 对话内容：参与者共有
- 字幕文本：基于ASR转录+人工勘误，制作者所有
- 视频剪辑：制作者所有

## 音乐/音效
- 无额外音乐或音效使用
- 环境音（鸟鸣、风声）为录制现场自然采集

## 授权协议
- 本作品采用 CC BY-NC-SA 4.0 协议
- 允许非商业性使用、分享、改编，需注明出处
- 改编作品需采用相同协议

## 原始素材来源
- 视频源文件：C0257.MP4 (4K 3840x2160, H.264, 25fps)
- 音频源文件：C0257_mixed_normalized.wav (48kHz, 24bit)
- 转录文件：C0257_full_mixed.json (FunASR)
"""
    with open(project_dir / "COPYRIGHT.md", "w", encoding="utf-8") as f:
        f.write(copyright_text)
    print("  COPYRIGHT.md OK")

    release_cards = []

    all_clips = []
    for clips_list, series_name in [
        (HIGHLIGHTS_CLIPS, "高光"),
        (PHILOSOPHY_CLIPS, "哲思"),
        (DIALOGUE_CLIPS, "精彩对话"),
        (WIKI_CLIPS, "深度思考"),
        (IMMERSIVE_CLIPS, "沉浸式场域"),
    ]:
        for clip in clips_list:
            all_clips.append({**clip, "series_name": series_name})

    for clip in all_clips:
        clip_id = clip["id"]
        series = clip.get("series_name", clip.get("series", ""))
        title = clip.get("title", "")

        tags_bilibili = ["哲学", "博尔赫斯", "时间", "播客", "小径分岔的花园"]
        if "domain" in clip:
            tags_bilibili.insert(0, clip["domain"])
        tags_douyin = [f"#{t}" for t in tags_bilibili[:4]]
        tags_youtube = ["philosophy", "borges", "time", "podcast", "garden of forking paths"]

        card = {
            "id": clip_id,
            "series": series,
            "title": title,
            "subtitle_bilibili": f"{title} | 小径分岔的花园",
            "subtitle_douyin": f"{title} {' '.join(tags_douyin[:3])}",
            "subtitle_youtube": f"{title} | Garden of Forking Paths",
            "description": clip.get("description", ""),
            "tags_bilibili": tags_bilibili,
            "tags_douyin": tags_douyin,
            "tags_youtube": tags_youtube,
            "cover_spec": "1920x1080 (B站) / 1080x1920 (抖音)",
            "suggested_post_time": "20:00-22:00",
            "cta": "完整版对话见主页「小径分岔的花园」",
        }
        release_cards.append(card)

    with open(project_dir / "RELEASE_CARDS.json", "w", encoding="utf-8") as f:
        json.dump(release_cards, f, ensure_ascii=False, indent=2)
    print(f"  RELEASE_CARDS.json OK: {len(release_cards)} cards")

    project_summary = {
        "project": "小径分岔的花园 — 完整视频企划",
        "source": "C0257",
        "source_video": "3840x2160, H.264, 25fps, 5168s",
        "series": {
            "short_videos": {
                "highlights": {"count": len(HIGHLIGHTS_CLIPS), "type": "高光", "duration_range": "15-60s"},
                "philosophy": {"count": len(PHILOSOPHY_CLIPS), "type": "哲思", "duration_range": "1-3min"},
                "dialogue": {"count": len(DIALOGUE_CLIPS), "type": "精彩对话", "duration_range": "30s-2min"},
            },
            "long_videos": {
                "deep_thinking": {"count": len(WIKI_CLIPS), "type": "深度思考", "chapters": 9},
                "immersive": {"count": len(IMMERSIVE_CLIPS), "type": "沉浸式场域", "parts": 2},
            },
        },
        "platforms": ["bilibili", "douyin", "youtube", "xiaoyuzhou", "apple_podcasts", "archive"],
        "total_clips": len(all_clips),
        "release_cards": len(release_cards),
    }
    with open(project_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(project_summary, f, ensure_ascii=False, indent=2)
    print("  summary.json OK")

    return release_cards


if __name__ == "__main__":
    total_start = time.time()

    wf2_results = run_workflow2()
    print(f"\nWorkflow 2 done: {len(wf2_results)} short video clips")

    wf3_results = run_workflow3()
    print(f"\nWorkflow 3 done: {len(wf3_results)} wiki chapters")

    wf1_results = run_workflow1_immersive()
    print(f"\nWorkflow 1 (immersive) done: {len(wf1_results)} immersive parts")

    wf4_results = run_workflow4()
    print(f"\nWorkflow 4 done: {len(wf4_results)} platform exports")

    wf5_results = run_workflow5()
    print(f"\nWorkflow 5 done: {len(wf5_results)} release cards")

    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"ALL DONE in {total_time/60:.1f} minutes")
    print(f"  Short videos: {len(wf2_results)}")
    print(f"  Wiki chapters: {len(wf3_results)}")
    print(f"  Immersive parts: {len(wf1_results)}")
    print(f"  Platform exports: {len(wf4_results)}")
    print(f"  Release cards: {len(wf5_results)}")
