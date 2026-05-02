import gc
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from pipeline.config import PipelineConfig
from pipeline.subtitle_content import process_subtitle_content, generate_ass_with_rounded_bg


@dataclass
class ClipProcessResult:
    clip_id: str
    output_dir: Path
    duration_s: float
    subtitle_count: int = 0
    audio_wav_ok: bool = False
    audio_mp3_ok: bool = False
    ass_ok: bool = False
    srt_ok: bool = False
    video_sub_ok: bool = False
    video_vertical_ok: bool = False
    metadata_ok: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "clip_id": self.clip_id,
            "duration_s": round(self.duration_s, 2),
            "subtitle_count": self.subtitle_count,
            "audio_wav_ok": self.audio_wav_ok,
            "audio_mp3_ok": self.audio_mp3_ok,
            "ass_ok": self.ass_ok,
            "srt_ok": self.srt_ok,
            "video_sub_ok": self.video_sub_ok,
            "video_vertical_ok": self.video_vertical_ok,
            "metadata_ok": self.metadata_ok,
        }
        if self.errors:
            d["errors"] = self.errors
        return d


def extract_clip_entries(
    entries: list,
    start_s: float,
    end_s: float,
) -> list[dict]:
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
    return clip_entries_raw


def process_clip_subtitles(
    clip_entries_raw: list[dict],
    custom_errata: dict | None = None,
    max_chars: int = 18,
    strip_punctuation: bool = True,
) -> list[dict]:
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
            max_chars=max_chars,
            is_last=is_last,
            custom_errata=custom_errata,
            strip_punctuation=strip_punctuation,
        )
        processed_entries.append({
            "index": i + 1,
            "start_s": raw["start_s"],
            "end_s": raw["end_s"],
            "text": processed_text,
        })
    return processed_entries


def merge_short_entries(
    processed_entries: list[dict],
    max_chars: int = 18,
    min_duration_s: float = 1.0,
    extend_duration_s: float = 1.2,
) -> list[dict]:
    merged_entries = []
    for entry in processed_entries:
        dur = entry["end_s"] - entry["start_s"]
        if dur <= min_duration_s:
            if merged_entries:
                prev = merged_entries[-1]
                combined = prev["text"] + entry["text"]
                if len(combined) <= max_chars:
                    prev["end_s"] = entry["end_s"]
                    prev["text"] = combined
                else:
                    prev["end_s"] = min(prev["end_s"], prev["start_s"] + extend_duration_s)
                    entry["end_s"] = entry["start_s"] + extend_duration_s
                    merged_entries.append(entry)
            else:
                entry["end_s"] = entry["start_s"] + extend_duration_s
                merged_entries.append(entry)
        else:
            merged_entries.append(entry)
    for idx, e in enumerate(merged_entries):
        e["index"] = idx + 1
    for i in range(len(merged_entries) - 1):
        if merged_entries[i]["end_s"] > merged_entries[i + 1]["start_s"]:
            merged_entries[i]["end_s"] = merged_entries[i + 1]["start_s"] - 0.04
            if merged_entries[i]["end_s"] - merged_entries[i]["start_s"] < 0.5:
                merged_entries[i]["end_s"] = merged_entries[i + 1]["start_s"] - 0.01
    return merged_entries


def generate_audio(
    audio_source: Path,
    start_s: float,
    end_s: float,
    output_dir: Path,
    clip_id: str,
    fade_in_s: float = 0.05,
    fade_out_s: float = 0.1,
    skip_existing: bool = True,
) -> tuple[bool, bool]:
    duration_s = end_s - start_s
    wav_ok = False
    mp3_ok = False

    wav_output = output_dir / f"{clip_id}.wav"
    if audio_source.exists():
        if not skip_existing or not wav_output.exists():
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_source),
                "-ss", str(start_s), "-to", str(end_s),
                "-af", f"afade=t=in:st=0:d={fade_in_s},afade=t=out:st={duration_s - fade_out_s}:d={fade_out_s}",
                "-ar", "48000", "-ac", "2",
                "-c:a", "pcm_s24le", str(wav_output),
            ]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        wav_ok = wav_output.exists()

    mp3_output = output_dir / f"{clip_id}.mp3"
    if audio_source.exists():
        if not skip_existing or not mp3_output.exists():
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_source),
                "-ss", str(start_s), "-to", str(end_s),
                "-af", f"afade=t=in:st=0:d={fade_in_s},afade=t=out:st={duration_s - fade_out_s}:d={fade_out_s}",
                "-c:a", "libmp3lame", "-b:a", "192k",
                str(mp3_output),
            ]
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        mp3_ok = mp3_output.exists()

    return wav_ok, mp3_ok


def generate_ass(
    processed_entries: list[dict],
    output_path: Path,
    video_width: int = 3840,
    video_height: int = 2160,
    font_name: str = "Noto Sans SC",
    font_size: int = 104,
    bg_color: str = "1A1A1A",
    bg_alpha: int = 38,
    text_color: str = "FFFFFF",
    corner_radius: int = 24,
    padding_h: int = 40,
    padding_v: int = 20,
    margin_v: int = 90,
) -> bool:
    ass_content = generate_ass_with_rounded_bg(
        entries=processed_entries,
        video_width=video_width,
        video_height=video_height,
        font_name=font_name,
        font_size=font_size,
        bg_color=bg_color,
        bg_alpha=bg_alpha,
        text_color=text_color,
        corner_radius=corner_radius,
        padding_h=padding_h,
        padding_v=padding_v,
        margin_v=margin_v,
    )
    output_path.write_text(ass_content, encoding="utf-8")
    return output_path.exists()


def generate_srt(
    processed_entries: list[dict],
    output_path: Path,
    skip_existing: bool = True,
) -> bool:
    if skip_existing and output_path.exists():
        return True
    srt_lines = []
    for e in processed_entries:
        srt_lines.append(str(e["index"]))
        sh, sm, ss, sms = int(e["start_s"] // 3600), int((e["start_s"] % 3600) // 60), int(e["start_s"] % 60), int((e["start_s"] % 1) * 1000)
        eh, em, es, ems = int(e["end_s"] // 3600), int((e["end_s"] % 3600) // 60), int(e["end_s"] % 60), int((e["end_s"] % 1) * 1000)
        srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}")
        srt_lines.append(e["text"])
        srt_lines.append("")
    output_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return output_path.exists()


def generate_video_subtitled(
    video_source: Path,
    ass_path: Path,
    start_s: float,
    end_s: float,
    output_path: Path,
    skip_existing: bool = True,
    codec: str = "libx264",
    preset: str = "medium",
    crf: int = 20,
    audio_bitrate: str = "192k",
    timeout_s: int = 600,
) -> bool:
    if not video_source.exists():
        return False
    if skip_existing and output_path.exists():
        return True
    ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    vf_chain = f"subtitles='{ass_path_escaped}'"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s), "-to", str(end_s),
        "-i", str(video_source),
        "-vf", vf_chain,
        "-c:v", codec, "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-ac", "2",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        if output_path.exists():
            output_path.unlink()
        return False
    gc.collect()
    return result.returncode == 0 and output_path.exists()


def generate_video_vertical(
    video_source: Path,
    ass_path: Path,
    start_s: float,
    end_s: float,
    output_path: Path,
    skip_existing: bool = True,
    codec: str = "libx264",
    preset: str = "medium",
    video_bitrate: str = "5000k",
    audio_bitrate: str = "128k",
    timeout_s: int = 600,
) -> bool:
    if not video_source.exists():
        return False
    if skip_existing and output_path.exists():
        return True
    if output_path.exists():
        output_path.unlink()
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
        "-i", str(video_source),
        "-vf", vf_chain,
        "-c:v", codec, "-preset", preset, "-b:v", video_bitrate,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000", "-ac", "2",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        if output_path.exists():
            output_path.unlink()
        return False
    gc.collect()
    return result.returncode == 0 and output_path.exists()


def write_metadata(
    clip: dict,
    processed_entries: list[dict],
    output_dir: Path,
    extra_fields: dict | None = None,
) -> bool:
    clip_id = clip["id"]
    metadata = {
        "id": clip_id,
        "title": clip.get("title", ""),
        "series": clip.get("series", ""),
        "description": clip.get("description", ""),
        "start_s": clip["start_s"],
        "end_s": clip["end_s"],
        "duration_s": clip["end_s"] - clip["start_s"],
        "subtitle_count": len(processed_entries),
    }
    for key in ("domain", "chapter", "hook"):
        if key in clip:
            metadata[key] = clip[key]
    if extra_fields:
        metadata.update(extra_fields)
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def process_clip(
    clip: dict,
    clip_dir: Path,
    entries: list,
    audio_source: Path,
    video_source: Path,
    custom_errata: dict | None = None,
    make_vertical: bool = True,
    make_srt: bool = True,
    skip_existing: bool = True,
    max_chars: int = 18,
    strip_punctuation: bool = True,
    ass_style: dict | None = None,
    fade_in_s: float = 0.05,
    fade_out_s: float = 0.1,
    extra_metadata: dict | None = None,
) -> ClipProcessResult:
    clip_id = clip["id"]
    start_s = clip["start_s"]
    end_s = clip["end_s"]
    duration_s = end_s - start_s

    clip_dir.mkdir(parents=True, exist_ok=True)
    result = ClipProcessResult(
        clip_id=clip_id,
        output_dir=clip_dir,
        duration_s=duration_s,
    )

    wav_ok, mp3_ok = generate_audio(
        audio_source, start_s, end_s, clip_dir, clip_id,
        fade_in_s=fade_in_s, fade_out_s=fade_out_s,
        skip_existing=skip_existing,
    )
    result.audio_wav_ok = wav_ok
    result.audio_mp3_ok = mp3_ok

    clip_entries_raw = extract_clip_entries(entries, start_s, end_s)
    processed_entries = process_clip_subtitles(
        clip_entries_raw, custom_errata, max_chars, strip_punctuation,
    )
    processed_entries = merge_short_entries(processed_entries, max_chars)

    style = ass_style or {}
    ass_output = clip_dir / f"{clip_id}.ass"
    result.ass_ok = generate_ass(processed_entries, ass_output, **style)
    result.subtitle_count = len(processed_entries)

    if make_srt:
        srt_output = clip_dir / f"{clip_id}.srt"
        result.srt_ok = generate_srt(processed_entries, srt_output, skip_existing)

    if video_source.exists():
        video_sub_output = clip_dir / f"{clip_id}_subtitled.mp4"
        result.video_sub_ok = generate_video_subtitled(
            video_source, ass_output, start_s, end_s, video_sub_output,
            skip_existing=skip_existing,
        )

        if make_vertical:
            video_vert_output = clip_dir / f"{clip_id}_vertical.mp4"
            result.video_vertical_ok = generate_video_vertical(
                video_source, ass_output, start_s, end_s, video_vert_output,
            )

    result.metadata_ok = write_metadata(clip, processed_entries, clip_dir, extra_metadata)

    return result


def process_series(
    clips: list[dict],
    series_dir: Path,
    entries: list,
    audio_source: Path,
    video_source: Path,
    custom_errata: dict | None = None,
    make_vertical: bool = True,
    make_srt: bool = True,
    skip_existing: bool = True,
    max_chars: int = 18,
    strip_punctuation: bool = True,
    ass_style: dict | None = None,
    fade_in_s: float = 0.05,
    fade_out_s: float = 0.1,
    series_name: str = "",
    project_name: str = "",
    source_id: str = "",
) -> list[ClipProcessResult]:
    series_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for clip in clips:
        clip_dir = series_dir / clip["id"]
        try:
            r = process_clip(
                clip, clip_dir, entries, audio_source, video_source,
                custom_errata=custom_errata,
                make_vertical=make_vertical,
                make_srt=make_srt,
                skip_existing=skip_existing,
                max_chars=max_chars,
                strip_punctuation=strip_punctuation,
                ass_style=ass_style,
                fade_in_s=fade_in_s,
                fade_out_s=fade_out_s,
            )
            results.append(r)
        except Exception as e:
            results.append(ClipProcessResult(
                clip_id=clip["id"],
                output_dir=clip_dir,
                duration_s=clip["end_s"] - clip["start_s"],
                errors=[str(e)],
            ))

    summary = {
        "project": project_name,
        "series": series_name,
        "source": source_id,
        "total_clips": len(results),
        "generated": sum(1 for r in results if not r.errors),
        "skipped": sum(1 for r in results if r.errors),
        "clips": [r.to_dict() for r in results],
    }
    summary_path = series_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return results
