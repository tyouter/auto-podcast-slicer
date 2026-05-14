import re
from dataclasses import dataclass, field, asdict
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.transcribe import TranscriptResult, TranscriptSegment
from pipeline.subtitle_generator import SubtitleEntry


@dataclass
class MergedSegment:
    start_ms: int
    end_ms: int
    text: str
    source_indices: list[int] = field(default_factory=list)
    speaker: Optional[str] = None
    is_interruption: bool = False
    interrupted_by: Optional[str] = None

    @property
    def start_s(self) -> float:
        return self.start_ms / 1000.0

    @property
    def end_s(self) -> float:
        return self.end_ms / 1000.0

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def should_merge(seg_a: TranscriptSegment, seg_b: TranscriptSegment, config: PipelineConfig) -> bool:
    gap_ms = seg_b.start_ms - seg_a.end_ms
    if gap_ms > 2000:
        return False

    combined_text = seg_a.text + seg_b.text
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', combined_text))
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 15) * config.get("pipeline.subtitle.max_lines", 2)
    if cn_chars > max_chars:
        return False

    combined_duration_ms = seg_b.end_ms - seg_a.start_ms
    max_display_ms = config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000
    if combined_duration_ms > max_display_ms:
        return False

    return True


def detect_sentence_boundary(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'[。！？.!?]$', text.strip()))


def merge_short_segments(
    segments: list[TranscriptSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda s: s.start_ms)
    min_display_ms = config.get("pipeline.subtitle.min_display_duration", 1.0) * 1000
    max_display_ms = config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 15) * config.get("pipeline.subtitle.max_lines", 2)
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
    max_speed = reading_speed * 1.5

    merged = []
    current_start = sorted_segs[0].start_ms
    current_end = sorted_segs[0].end_ms
    current_text = sorted_segs[0].text.strip()
    current_indices = [0]

    for i in range(1, len(sorted_segs)):
        seg = sorted_segs[i]
        gap_ms = seg.start_ms - current_end
        combined_text = current_text + seg.text.strip()
        combined_cn_chars = len(re.findall(r'[\u4e00-\u9fff]', combined_text))
        combined_duration_ms = seg.end_ms - current_start
        combined_speed = combined_cn_chars / (combined_duration_ms / 1000) if combined_duration_ms > 0 else 0

        can_merge = (
            gap_ms <= 2000
            and combined_cn_chars <= max_chars
            and combined_duration_ms <= max_display_ms
            and combined_speed <= max_speed
        )

        current_duration_ms = current_end - current_start
        current_cn_chars = len(re.findall(r'[\u4e00-\u9fff]', current_text))

        force_break = (
            detect_sentence_boundary(current_text)
            and current_duration_ms >= min_display_ms
            and current_cn_chars >= 4
            and (current_cn_chars / (current_duration_ms / 1000) if current_duration_ms > 0 else 0) <= max_speed
        )

        if can_merge and not force_break:
            if gap_ms > 0:
                pass
            current_text = current_text + seg.text.strip()
            current_end = seg.end_ms
            current_indices.append(i)
        else:
            merged.append(MergedSegment(
                start_ms=current_start,
                end_ms=current_end,
                text=current_text.strip(),
                source_indices=current_indices[:],
            ))

            current_start = seg.start_ms
            current_end = seg.end_ms
            current_text = seg.text.strip()
            current_indices = [i]

    merged.append(MergedSegment(
        start_ms=current_start,
        end_ms=current_end,
        text=current_text.strip(),
        source_indices=current_indices[:],
    ))

    return merged


def split_long_merged_segment(
    segment: MergedSegment,
    config: PipelineConfig,
) -> list[MergedSegment]:
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 15) * config.get("pipeline.subtitle.max_lines", 2)
    max_display_ms = config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000

    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', segment.text))
    duration_ms = segment.duration_ms

    if cn_chars <= max_chars and duration_ms <= max_display_ms:
        return [segment]

    text = segment.text
    duration_per_char = duration_ms / max(1, len(text))

    split_points = []
    for m in re.finditer(r'[。！？；，、]', text):
        split_points.append(m.end())

    if not split_points:
        mid = len(text) // 2
        split_points = [mid]

    result = []
    current_text_start = 0

    for sp in split_points:
        chunk = text[current_text_start:sp]
        chunk_chars = len(re.findall(r'[\u4e00-\u9fff]', chunk))
        if chunk_chars >= 4:
            chunk_duration_ms = int(len(chunk) * duration_per_char)
            result.append(MergedSegment(
                start_ms=segment.start_ms + int(current_text_start * duration_per_char),
                end_ms=segment.start_ms + int(sp * duration_per_char),
                text=chunk.strip(),
                source_indices=segment.source_indices[:],
            ))
            current_text_start = sp

    remaining = text[current_text_start:]
    if remaining.strip():
        remaining_chars = len(re.findall(r'[\u4e00-\u9fff]', remaining))
        if remaining_chars >= 2:
            result.append(MergedSegment(
                start_ms=segment.start_ms + int(current_text_start * duration_per_char),
                end_ms=segment.end_ms,
                text=remaining.strip(),
                source_indices=segment.source_indices[:],
            ))
        elif result:
            result[-1].text += remaining.strip()
            result[-1].end_ms = segment.end_ms

    if not result:
        return [segment]

    return result


def ensure_minimum_duration(
    segments: list[MergedSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    min_display_ms = int(config.get("pipeline.subtitle.min_display_duration", 1.0) * 1000)
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 18) * config.get("pipeline.subtitle.max_lines", 2)
    max_display_ms = int(config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000)
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
    max_speed = reading_speed * 1.5

    if not segments:
        return segments

    result = []
    i = 0
    while i < len(segments):
        seg = segments[i]

        if seg.duration_ms >= min_display_ms:
            result.append(seg)
            i += 1
        else:
            # Try merging backward first
            if result and _can_merge_pair_seg(result[-1], seg, max_chars, max_display_ms, max_speed):
                prev = result[-1]
                result[-1] = MergedSegment(
                    start_ms=prev.start_ms,
                    end_ms=seg.end_ms,
                    text=prev.text + seg.text,
                    source_indices=prev.source_indices + seg.source_indices,
                )
            # Try merging forward
            elif i + 1 < len(segments) and _can_merge_pair_seg(seg, segments[i + 1], max_chars, max_display_ms, max_speed):
                next_seg = segments[i + 1]
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=next_seg.end_ms,
                    text=seg.text + next_seg.text,
                    source_indices=seg.source_indices + next_seg.source_indices,
                ))
                i += 2
                continue
            # Extend into gap
            elif i + 1 < len(segments):
                gap_ms = segments[i + 1].start_ms - seg.end_ms
                min_gap_ms = int(config.get("pipeline.subtitle.min_gap_duration", 0.067) * 1000)
                if gap_ms > min_gap_ms * 2:
                    # Plenty of gap - extend to full min_duration, leaving min_gap
                    extend_ms = min(int(gap_ms - min_gap_ms), min_display_ms - seg.duration_ms)
                elif gap_ms > 0:
                    extend_ms = min(int(gap_ms // 2), min_display_ms - seg.duration_ms)
                else:
                    extend_ms = 0
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms + extend_ms,
                    text=seg.text,
                    source_indices=seg.source_indices[:],
                ))
            # Last segment - pad to minimum
            else:
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=seg.start_ms + min_display_ms,
                    text=seg.text,
                    source_indices=seg.source_indices[:],
                ))
            i += 1

    return result

def extend_for_readability(
    segments: list[MergedSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
    max_speed = reading_speed * 1.5
    min_display_ms = config.get("pipeline.subtitle.min_display_duration", 1.0) * 1000

    sorted_segs = sorted(segments, key=lambda s: s.start_ms)
    result = []

    for i, seg in enumerate(sorted_segs):
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', seg.text))
        if cn_chars == 0:
            result.append(seg)
            continue

        duration_s = seg.duration_ms / 1000
        actual_speed = cn_chars / duration_s if duration_s > 0 else 999

        if actual_speed > max_speed:
            min_duration_for_speed = cn_chars / max_speed
            min_duration_ms = int(min_duration_for_speed * 1000)
            min_duration_ms = max(min_duration_ms, int(min_display_ms))

            new_end_ms = seg.start_ms + min_duration_ms

            if i + 1 < len(sorted_segs):
                next_start = sorted_segs[i + 1].start_ms
                min_gap_ms = 67
                max_end = next_start - min_gap_ms
                new_end_ms = min(new_end_ms, max_end)

            if new_end_ms > seg.end_ms:
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=new_end_ms,
                    text=seg.text,
                    source_indices=seg.source_indices[:],
                ))
            else:
                result.append(seg)
        else:
            result.append(seg)

    return result


def merge_fast_segments(
    segments: list[MergedSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
    max_speed = reading_speed * 1.5
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 15) * config.get("pipeline.subtitle.max_lines", 2)
    max_display_ms = config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000

    if not segments:
        return segments

    sorted_segs = sorted(segments, key=lambda s: s.start_ms)
    result = []
    i = 0

    while i < len(sorted_segs):
        seg = sorted_segs[i]
        cn_chars = len(re.findall(r'[\u4e00-\u9fff]', seg.text))
        duration_s = seg.duration_ms / 1000
        speed = cn_chars / duration_s if duration_s > 0 else 0

        if speed > max_speed and i + 1 < len(sorted_segs):
            next_seg = sorted_segs[i + 1]
            combined_text = seg.text + next_seg.text
            combined_chars = len(re.findall(r'[\u4e00-\u9fff]', combined_text))
            combined_duration_ms = next_seg.end_ms - seg.start_ms
            combined_speed = combined_chars / (combined_duration_ms / 1000) if combined_duration_ms > 0 else 0

            if combined_chars <= max_chars and combined_duration_ms <= max_display_ms and combined_speed <= max_speed:
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=next_seg.end_ms,
                    text=combined_text,
                    source_indices=seg.source_indices + next_seg.source_indices,
                ))
                i += 2
                continue
            elif i > 0 and result:
                prev_seg = result[-1]
                combined_text_prev = prev_seg.text + seg.text
                combined_chars_prev = len(re.findall(r'[\u4e00-\u9fff]', combined_text_prev))
                combined_duration_ms_prev = seg.end_ms - prev_seg.start_ms
                combined_speed_prev = combined_chars_prev / (combined_duration_ms_prev / 1000) if combined_duration_ms_prev > 0 else 0

                if combined_chars_prev <= max_chars and combined_duration_ms_prev <= max_display_ms and combined_speed_prev <= max_speed:
                    result[-1] = MergedSegment(
                        start_ms=prev_seg.start_ms,
                        end_ms=seg.end_ms,
                        text=combined_text_prev,
                        source_indices=prev_seg.source_indices + seg.source_indices,
                    )
                    i += 1
                    continue

        result.append(seg)
        i += 1

    return result


def _is_tiny_fragment(seg: MergedSegment, min_display_ms: int) -> bool:
    """Check if a segment is too small to stand alone.
    
    A tiny fragment is one that:
    - Has ≤3 CJK characters, or
    - Duration < 1.0s, or
    - Starts with a forbidden line-start character (suggesting it's a tail of previous segment)
    """
    FORBIDDEN_STARTERS = '的了着过吗呢吧啊呀哇嘛呗的啦咯嗯噢哦哈但是因为所以如果虽然然后不过'
    
    text = seg.text.strip()
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    duration_ms = seg.duration_ms
    
    if cn_chars <= 3:
        return True
    if duration_ms < min_display_ms:
        return True
    # Forbidden starter only matters when the segment is short (≤5 chars total)
    if cn_chars <= 5 and text and text[0] in FORBIDDEN_STARTERS:
        return True
    return False


def _can_merge_pair_seg(
    seg_a: MergedSegment,
    seg_b: MergedSegment,
    max_chars: int,
    max_display_ms: int,
    max_speed: float,
) -> bool:
    """Check if two adjacent segments can be merged."""
    combined_text = seg_a.text + seg_b.text
    combined_cn_chars = len(re.findall(r'[\u4e00-\u9fff]', combined_text))
    combined_duration_ms = seg_b.end_ms - seg_a.start_ms
    
    if combined_cn_chars > max_chars:
        return False
    if combined_duration_ms > max_display_ms:
        return False
    if combined_duration_ms > 0:
        combined_speed = combined_cn_chars / (combined_duration_ms / 1000)
        if combined_speed > max_speed:
            return False
    return True


def merge_tiny_fragments(
    segments: list[MergedSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    """Force-merge short fragments (≤3 chars or <1s) into adjacent segments.
    
    This is a safety-net pass that runs after all other merging to catch
    fragments that escape the main merger. Standalone words like "这个",
    "上来", "对啊", "但" should never appear as independent subtitle entries.
    """
    if len(segments) < 2:
        return segments
    
    min_display_ms = int(config.get("pipeline.subtitle.min_display_duration", 1.0) * 1000)
    max_chars = config.get("pipeline.subtitle.max_chars_per_line_cn", 18) * config.get("pipeline.subtitle.max_lines", 2)
    max_display_ms = int(config.get("pipeline.subtitle.max_display_duration", 7.0) * 1000)
    reading_speed = config.get("pipeline.subtitle.reading_speed_cn", 4)
    max_speed = reading_speed * 1.5
    
    result = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        
        if not _is_tiny_fragment(seg, min_display_ms):
            result.append(seg)
            i += 1
            continue
        
        # Try merging backward first for sentence-ending fragments
        prefer_backward = seg.text and seg.text[-1] in '啊呀哇嘛呗啦咯嗯噢哦哈对呢吧吗'
        merged = False
        
        if prefer_backward and result:
            prev_seg = result[-1]
            if _can_merge_pair_seg(prev_seg, seg, max_chars, max_display_ms, max_speed):
                result[-1] = MergedSegment(
                    start_ms=prev_seg.start_ms,
                    end_ms=seg.end_ms,
                    text=prev_seg.text + seg.text,
                    source_indices=prev_seg.source_indices + seg.source_indices,
                )
                i += 1
                merged = True
        
        if merged:
            continue
        
        # Try merging forward (with next segment)
        if i + 1 < len(segments):
            next_seg = segments[i + 1]
            if _can_merge_pair_seg(seg, next_seg, max_chars, max_display_ms, max_speed):
                result.append(MergedSegment(
                    start_ms=seg.start_ms,
                    end_ms=next_seg.end_ms,
                    text=seg.text + next_seg.text,
                    source_indices=seg.source_indices + next_seg.source_indices,
                ))
                i += 2
                merged = True
        
        if merged:
            continue
        
        # Try merging backward (with previous segment)
        if result:
            prev_seg = result[-1]
            if _can_merge_pair_seg(prev_seg, seg, max_chars, max_display_ms, max_speed):
                result[-1] = MergedSegment(
                    start_ms=prev_seg.start_ms,
                    end_ms=seg.end_ms,
                    text=prev_seg.text + seg.text,
                    source_indices=prev_seg.source_indices + seg.source_indices,
                )
                i += 1
                continue
        
        # Can't merge either direction — keep as-is (ensure_minimum_duration will extend it later)
        result.append(seg)
        i += 1
    
    return result


def add_gaps_between_entries(
    segments: list[MergedSegment],
    config: PipelineConfig,
) -> list[MergedSegment]:
    min_gap_ms = int(config.get("pipeline.subtitle.min_gap_duration", 0.067) * 1000)

    if not segments or min_gap_ms <= 0:
        return segments

    sorted_segs = sorted(segments, key=lambda s: s.start_ms)
    result = []

    for i, seg in enumerate(sorted_segs):
        duration_ms = seg.duration_ms
        min_display_ms = int(config.get("pipeline.subtitle.min_display_duration", 1.0) * 1000)

        if i < len(sorted_segs) - 1:
            next_start = sorted_segs[i + 1].start_ms
            gap = next_start - seg.end_ms

            if gap < min_gap_ms:
                available = duration_ms - min_display_ms
                trim_ms = min(min_gap_ms // 2, available // 2) if available > 0 else 0
                if trim_ms > 0:
                    result.append(MergedSegment(
                        start_ms=seg.start_ms,
                        end_ms=seg.end_ms - trim_ms,
                        text=seg.text,
                        source_indices=seg.source_indices[:],
                    ))
                else:
                    result.append(seg)
            else:
                result.append(seg)
        else:
            result.append(seg)

    return result


def merged_to_subtitle_entries(segments: list[MergedSegment]) -> list[SubtitleEntry]:
    entries = []
    for i, seg in enumerate(segments):
        entries.append(SubtitleEntry(
            index=i + 1,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=seg.text,
        ))
    return entries


def process_transcript_to_subtitles(
    transcript: TranscriptResult,
    config: PipelineConfig,
) -> tuple[list[SubtitleEntry], list[MergedSegment]]:
    segments = sorted(transcript.segments, key=lambda s: s.start_ms)

    merged = merge_short_segments(segments, config)

    final_merged = []
    for seg in merged:
        split = split_long_merged_segment(seg, config)
        final_merged.extend(split)

    final_merged = ensure_minimum_duration(final_merged, config)
    final_merged = merge_fast_segments(final_merged, config)
    final_merged = merge_tiny_fragments(final_merged, config)
    final_merged = add_gaps_between_entries(final_merged, config)
    final_merged = extend_for_readability(final_merged, config)

    entries = merged_to_subtitle_entries(final_merged)

    return entries, final_merged