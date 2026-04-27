import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.transcribe import TranscriptResult, TranscriptSegment
from pipeline.clip_planning import ClipDefinition


@dataclass
class SubtitleEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def start_s(self) -> float:
        return self.start_ms / 1000.0

    @property
    def end_s(self) -> float:
        return self.end_ms / 1000.0

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0

    def to_srt(self) -> str:
        start_h = self.start_ms // 3600000
        start_m = (self.start_ms % 3600000) // 60000
        start_s = (self.start_ms % 60000) // 1000
        start_ms = self.start_ms % 1000

        end_h = self.end_ms // 3600000
        end_m = (self.end_ms % 3600000) // 60000
        end_s = (self.end_ms % 60000) // 1000
        end_ms = self.end_ms % 1000

        return (
            f"{self.index}\n"
            f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
            f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}\n"
            f"{self.text}\n"
        )

    def to_ass_dialogue(self, style: str = "Default") -> str:
        start_h = self.start_ms // 3600000
        start_m = (self.start_ms % 3600000) // 60000
        start_s = (self.start_ms % 60000) // 1000
        start_cs = (self.start_ms % 1000) // 10

        end_h = self.end_ms // 3600000
        end_m = (self.end_ms % 3600000) // 60000
        end_s = (self.end_ms % 60000) // 1000
        end_cs = (self.end_ms % 1000) // 10

        return (
            f"Dialogue: 0,{start_h}:{start_m:02d}:{start_s:02d}.{start_cs:02d},"
            f"{end_h}:{end_m:02d}:{end_s:02d}.{end_cs:02d},{style},,0,0,0,,{self.text}"
        )


@dataclass
class SubtitleResult:
    entries: list[SubtitleEntry] = field(default_factory=list)
    format: str = "srt"
    source_file: str = ""
    clip_id: str = ""

    def to_srt(self) -> str:
        return "\n".join(entry.to_srt() for entry in self.entries)

    def to_ass(self, config: PipelineConfig) -> str:
        standards = config.standards.get("subtitle.ass", {})
        font = standards.get("default_font", "Microsoft YaHei")
        fontsize = standards.get("default_fontsize", 60)
        primary_color = standards.get("primary_color", "&H00FFFFFF")
        outline_color = standards.get("outline_color", "&H00000000")
        back_color = standards.get("back_color", "&H80000000")
        outline_width = standards.get("outline_width", 3)
        shadow_width = standards.get("shadow_width", 1)
        alignment = standards.get("alignment", 2)
        margin_v = standards.get("margin_v", 30)
        margin_l = standards.get("margin_l", 10)
        margin_r = standards.get("margin_r", 10)

        header = f"""[Script Info]
Title: {self.clip_id}
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fontsize},{primary_color},&H000000FF,{outline_color},{back_color},-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_width},{alignment},{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        dialogues = [entry.to_ass_dialogue() for entry in self.entries]
        return header + "\n".join(dialogues)

    def save_srt(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_srt())

    def save_ass(self, path: Path, config: PipelineConfig):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_ass(config))


def load_corrections(corrections_path: Path) -> dict:
    if not corrections_path.exists():
        return {}
    with open(corrections_path, "r", encoding="utf-8") as f:
        if corrections_path.suffix == ".json":
            return json.load(f)
        elif corrections_path.suffix in (".yaml", ".yml"):
            import yaml
            return yaml.safe_load(f) or {}
    return {}


def apply_text_corrections(text: str, corrections: dict) -> str:
    for wrong, correct in corrections.items():
        text = text.replace(wrong, correct)
    return text


def split_long_text(
    text: str, max_chars_per_line: int = 15, max_lines: int = 2
) -> list[str]:
    if len(text) <= max_chars_per_line:
        return [text]

    max_total = max_chars_per_line * max_lines
    if len(text) <= max_total:
        mid = len(text) // 2
        break_points = list(re.finditer(r'[，。！？、；：\u201c\u201d\u2018\u2019\uff08\uff09\s,]', text))
        best_break = mid
        for bp in break_points:
            if abs(bp.start() - mid) < abs(best_break - mid):
                best_break = bp.start() + 1
        return [text[:best_break], text[best_break:]]

    lines = []
    remaining = text
    while remaining and len(lines) < max_lines:
        if len(remaining) <= max_chars_per_line:
            lines.append(remaining)
            break
        cut_pos = max_chars_per_line
        break_points = list(re.finditer(r'[，。！？、；：\u201c\u201d\u2018\u2019\uff08\uff09\s,]', remaining[:cut_pos + 5]))
        if break_points:
            cut_pos = break_points[-1].start() + 1
        lines.append(remaining[:cut_pos])
        remaining = remaining[cut_pos:]

    return lines


def adjust_subtitle_timing(
    entries: list[SubtitleEntry], config: PipelineConfig
) -> list[SubtitleEntry]:
    std = config.standards.get("subtitle.srt", {})
    min_display = std.get("min_display_s", 1.0)
    max_display = std.get("max_display_s", 7.0)
    min_gap = std.get("min_gap_s", 0.067)
    reading_speed = std.get("reading_speed_cn_chars_per_s", 4)

    adjusted = []
    for entry in entries:
        duration = entry.duration_s
        char_count = len(entry.text)
        ideal_duration = max(min_display, char_count / reading_speed)
        ideal_duration = min(ideal_duration, max_display)

        if duration < min_display:
            new_end = entry.start_ms + int(min_display * 1000)
            entry = SubtitleEntry(
                index=entry.index,
                start_ms=entry.start_ms,
                end_ms=new_end,
                text=entry.text,
            )
        elif duration > max_display:
            new_end = entry.start_ms + int(max_display * 1000)
            entry = SubtitleEntry(
                index=entry.index,
                start_ms=entry.start_ms,
                end_ms=new_end,
                text=entry.text,
            )

        adjusted.append(entry)

    for i in range(1, len(adjusted)):
        gap_ms = adjusted[i].start_ms - adjusted[i - 1].end_ms
        if gap_ms < int(min_gap * 1000):
            new_start = adjusted[i - 1].end_ms + int(min_gap * 1000)
            adjusted[i] = SubtitleEntry(
                index=adjusted[i].index,
                start_ms=new_start,
                end_ms=adjusted[i].end_ms,
                text=adjusted[i].text,
            )

    return adjusted


def generate_subtitles_from_transcript(
    transcript: TranscriptResult,
    config: PipelineConfig,
    corrections: dict | None = None,
) -> SubtitleResult:
    std = config.standards.get("subtitle.srt", {})
    max_chars = std.get("max_chars_per_line_cn", 15)
    max_lines = std.get("max_lines", 2)
    strip_period = std.get("strip_trailing_period_cn", True)

    entries = []
    idx = 1

    for seg in transcript.segments:
        text = seg.text.strip()
        if not text:
            continue

        if corrections:
            text = apply_text_corrections(text, corrections)

        if strip_period and text.endswith("。"):
            text = text[:-1]

        lines = split_long_text(text, max_chars, max_lines)
        display_text = "\n".join(lines)

        entries.append(SubtitleEntry(
            index=idx,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=display_text,
        ))
        idx += 1

    entries = adjust_subtitle_timing(entries, config)

    return SubtitleResult(
        entries=entries,
        format="srt",
        source_file=transcript.source_file,
    )


def generate_clip_subtitles(
    full_subtitles: SubtitleResult,
    clip: ClipDefinition,
    config: PipelineConfig,
) -> SubtitleResult:
    clip_entries = []
    idx = 1

    for entry in full_subtitles.entries:
        if entry.start_ms >= clip.start_ms and entry.end_ms <= clip.end_ms:
            adjusted_start = entry.start_ms - clip.start_ms
            adjusted_end = entry.end_ms - clip.start_ms

            clip_entries.append(SubtitleEntry(
                index=idx,
                start_ms=max(0, adjusted_start),
                end_ms=max(0, adjusted_end),
                text=entry.text,
            ))
            idx += 1
        elif entry.start_ms < clip.end_ms and entry.end_ms > clip.start_ms:
            overlap_start = max(entry.start_ms, clip.start_ms) - clip.start_ms
            overlap_end = min(entry.end_ms, clip.end_ms) - clip.start_ms

            clip_entries.append(SubtitleEntry(
                index=idx,
                start_ms=max(0, overlap_start),
                end_ms=max(0, overlap_end),
                text=entry.text,
            ))
            idx += 1

    clip_entries = adjust_subtitle_timing(clip_entries, config)

    return SubtitleResult(
        entries=clip_entries,
        format="srt",
        clip_id=clip.id,
    )
