import json
import subprocess
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path("D:/boke/garden in parallel - autoresearch/output/garden_forking_paths")
VIDEO_SOURCE = Path("D:/boke/garden post factory/C0257.MP4")
TRANSCRIPT_PATH = Path("D:/boke/garden post factory/C0257_full_mixed.json")

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    generate_ass_with_rounded_bg,
)
from pipeline.config import PipelineConfig

config = PipelineConfig()
corrections_path = Path("config/corrections.yaml")
custom_errata = load_custom_errata(corrections_path)

print("Loading transcript for cut-point analysis...")
transcript = parse_funasr_mixed_json(TRANSCRIPT_PATH)
entries, merged = process_transcript_to_subtitles(transcript, config)
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
