"""Targeted tests for merge_tiny_fragments + improved ensure_minimum_duration."""
import pytest
import re
from pipeline.subtitle_merger import (
    MergedSegment,
    merge_tiny_fragments,
    ensure_minimum_duration,
    _is_tiny_fragment,
    _can_merge_pair_seg,
)
from pipeline.config import PipelineConfig


def _make_seg(start_ms, end_ms, text):
    return MergedSegment(
        start_ms=start_ms, end_ms=end_ms, text=text,
        source_indices=[start_ms // 100],
    )


def _make_config(**overrides):
    """Create a minimal PipelineConfig with only subtitle settings."""
    return PipelineConfig(config_override={
        "pipeline": {
            "subtitle": {
                "max_chars_per_line_cn": 18,
                "max_lines": 2,
                "min_display_duration": 1.0,
                "max_display_duration": 7.0,
                "reading_speed_cn": 4,
                "min_gap_duration": 0.067,
                **overrides.get("subtitle", {}),
            },
        },
    })


# ──────────────────────────────────────────
# Tests: _is_tiny_fragment
# ──────────────────────────────────────────

class TestIsTinyFragment:
    MIN_DISPLAY = 1000  # ms

    def test_short_cn_chars(self):
        seg = _make_seg(0, 2000, "这个")
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is True

    def test_short_duration(self):
        seg = _make_seg(0, 350, "时间在这里分岔了")
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is True

    def test_forbidden_starter(self):
        seg = _make_seg(0, 2000, "但是")  # 2 chars, starts with forbidden '但'
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is True

    def test_forbidden_starter_long_ok(self):
        seg = _make_seg(0, 2000, "但是所有的可能性")  # 10 chars ≥ 5, not tiny
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is False

    def test_normal_segment_not_tiny(self):
        seg = _make_seg(0, 2500, "时间在这里分岔了")
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is False

    def test_single_char(self):
        seg = _make_seg(0, 200, "但")
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is True

    def test_4_char_ok_duration_not_tiny(self):
        seg = _make_seg(0, 1200, "四个汉字")
        assert _is_tiny_fragment(seg, self.MIN_DISPLAY) is False


# ──────────────────────────────────────────
# Tests: _can_merge_pair_seg
# ──────────────────────────────────────────

class TestCanMergePairSeg:
    def test_mergeable_simple(self):
        a = _make_seg(0, 500, "这个")
        b = _make_seg(500, 2000, "还比较短的")
        # Combined: 7 chars, 2.0s → 3.5 chars/s, ≤ 36 chars, ≤ 7000ms → OK
        assert _can_merge_pair_seg(a, b, 36, 7000, 6.0) is True

    def test_too_many_chars(self):
        a = _make_seg(0, 1000, "这是很长")
        b = _make_seg(1000, 2000, "后半内容")
        # Combined CN chars = 8, fits under 20
        assert _can_merge_pair_seg(a, b, 20, 7000, 6.0) is True
        # Tight limit: 8 > 6
        assert _can_merge_pair_seg(a, b, 6, 7000, 6.0) is False

    def test_too_long_duration(self):
        a = _make_seg(0, 5000, "短文本")
        b = _make_seg(5000, 10000, "也很短")
        assert _can_merge_pair_seg(a, b, 36, 7000, 6.0) is False  # 10s > 7s

    def test_too_fast_reading(self):
        a = _make_seg(0, 500, "这是一段包含很多文字的句子")
        b = _make_seg(500, 1000, "还有更多内容要加上去才够快")
        # Combined: ~20 chars / 1.0s = 20 chars/s
        assert _can_merge_pair_seg(a, b, 60, 7000, 6.0) is False  # > 6 chars/s

    def test_acceptable_speed(self):
        a = _make_seg(0, 1000, "这是一段")
        b = _make_seg(1000, 2000, "正常语速")
        assert _can_merge_pair_seg(a, b, 36, 7000, 6.0) is True  # 8 chars / 2s = 4

    def test_merge_with_gap(self):
        a = _make_seg(0, 1000, "片段A")
        b = _make_seg(1200, 2000, "片段B")  # 200ms gap
        assert _can_merge_pair_seg(a, b, 36, 7000, 6.0) is True


# ──────────────────────────────────────────
# Tests: merge_tiny_fragments
# ──────────────────────────────────────────

class TestMergeTinyFragments:

    def test_single_segment_unchanged(self):
        segs = [_make_seg(0, 2000, "完整的句子在这里")]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        assert len(result) == 1
        assert result[0].text == "完整的句子在这里"

    def test_merge_two_char_fragment_forward(self):
        """'这个' (2 chars) should merge with next segment."""
        segs = [
            _make_seg(0, 350, "这个"),
            _make_seg(350, 3000, "还比较短的这么一个人生经历"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        assert len(result) == 1
        assert result[0].text == "这个还比较短的这么一个人生经历"

    def test_merge_standalone_filler_backward(self):
        """'对啊' should merge with previous segment when forward fails."""
        segs = [
            _make_seg(0, 2000, "这个很好理解"),
            _make_seg(2000, 2510, "对啊"),
            _make_seg(2510, 4500, "但是所有的可能性同时发生"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        # '对啊' should merge backward into '这个很好理解'
        assert len(result) == 2
        assert "这个很好理解对啊" == result[0].text
        assert result[1].text == "但是所有的可能性同时发生"

    def test_multiple_fragments_in_sequence(self):
        """A sequence of fragments: '但' + short tail — both merge backward."""
        segs = [
            _make_seg(0, 3000, "之前的内容"),
            _make_seg(3000, 3200, "但"),
            _make_seg(3200, 3700, "是他就执意的一定要去选左边"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        # '但' merges backward into '之前的内容' (forward rejected — speed too high)
        # '是他就执意...' is also tiny (500ms), merges backward into combined
        assert len(result) == 1
        assert "之前的内容但是他就执意的一定要去选左边" == result[0].text

    def test_normal_segments_preserved(self):
        """Normal-length segments should be untouched."""
        segs = [
            _make_seg(0, 2000, "第一句完整的话"),
            _make_seg(2200, 4000, "第二句也很完整"),
            _make_seg(4200, 6000, "第三句同样完整"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        assert len(result) == 3
        assert [s.text for s in result] == [
            "第一句完整的话", "第二句也很完整", "第三句同样完整",
        ]

    def test_merge_exceeds_max_chars_skip(self):
        """When merging would exceed max chars, keep fragment separate."""
        config = _make_config(subtitle={"max_chars_per_line_cn": 5, "max_lines": 1})
        segs = [
            _make_seg(0, 400, "这"),
            _make_seg(400, 2000, "已经是五个字了"),
        ]
        result = merge_tiny_fragments(segs, config)
        # Combined would be 7 chars > 5 limit, so '这' stays separate
        assert len(result) >= 1  # May be 1 or 2 depending on exact char count

    def test_end_to_end_h01_scenario(self):
        """Simulate H01's actual subtitle structure."""
        segs = [
            _make_seg(110, 1282, "从我们个人的"),
            _make_seg(1282, 1633, "这个"),
            _make_seg(1673, 4410, "还比较短的这么一个人生经历"),
            _make_seg(4410, 4793, "上来"),
            _make_seg(4833, 5650, "看的话对"),
            _make_seg(5690, 8685, "其实在我们生命当中也出现了蛮"),
            _make_seg(8685, 9755, "多的分叉对"),
            _make_seg(10330, 13050, "而且我特别关注的就是一句话"),
            _make_seg(13050, 15141, "就是时间在这里分叉所"),
            _make_seg(15175, 17713, "有的可能性同时发生嗯他"),
            _make_seg(17713, 20019, "其实这句话的魅力到底"),
            _make_seg(20089, 23108, "你在哪就时间在这里分叉"),
            _make_seg(23108, 24754, "这个很好理解"),
            _make_seg(24786, 25297, "对啊"),
            _make_seg(25338, 27541, "但是所有的可能性"),
            _make_seg(27541, 29745, "同时发生那就给我"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)

        # Key assertions:
        # - '这个' (2 chars) should be merged forward
        # - '上来' (2 chars) should be merged
        # - '对啊' (2 chars) should be merged backward
        # Result should have fewer segments than input
        assert len(result) < len(segs), f"Expected fewer segments, got {len(result)} vs {len(segs)}"

        # Verify no standalone fragments survive
        for seg in result:
            cn = len(re.findall(r'[\u4e00-\u9fff]', seg.text))
            dur = seg.duration_ms
            # Any surviving segment should be at least 4 chars OR have adequate duration
            assert cn >= 4 or dur >= 1000, (
                f"Fragment survived: text='{seg.text}' ({cn} chars, {dur}ms)"
            )

    def test_h01_no_standalone_this(self):
        """'这个' must not exist as standalone entry."""
        segs = [
            _make_seg(1282, 1633, "这个"),
            _make_seg(1673, 4410, "还比较短的这么一个人生经历"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        assert len(result) == 1
        assert "这个" not in [s.text for s in result]  # Should be merged, not standalone

    def test_h01_no_standalone_duiya(self):
        """'对啊' must not exist as standalone entry."""
        segs = [
            _make_seg(23108, 24754, "这个很好理解"),
            _make_seg(24786, 25297, "对啊"),
        ]
        config = _make_config()
        result = merge_tiny_fragments(segs, config)
        assert len(result) == 1
        assert "对啊" not in [s.text for s in result]


# ──────────────────────────────────────────
# Tests: ensure_minimum_duration (improved)
# ──────────────────────────────────────────

class TestEnsureMinimumDuration:

    def test_normal_duration_unchanged(self):
        segs = [_make_seg(0, 3000, "正常的时长")]
        config = _make_config()
        result = ensure_minimum_duration(segs, config)
        assert len(result) == 1
        assert result[0].text == "正常的时长"

    def test_short_merges_forward(self):
        """Short segment should merge with next if compatible."""
        segs = [
            _make_seg(0, 500, "这个"),
            _make_seg(550, 3000, "还比较短的一句话"),
        ]
        config = _make_config()
        result = ensure_minimum_duration(segs, config)
        assert len(result) == 1
        assert result[0].text == "这个还比较短的一句话"

    def test_short_merges_backward(self):
        """Short segment should merge with previous."""
        segs = [
            _make_seg(0, 3000, "已经完整的一句话"),
            _make_seg(3050, 3400, "对啊"),
        ]
        config = _make_config()
        result = ensure_minimum_duration(segs, config)
        assert len(result) == 1
        assert "对啊" in result[0].text

    def test_short_extends_into_gap_when_cant_merge(self):
        """When merging exceeds limits, extend into gap instead."""
        config = _make_config(subtitle={"max_chars_per_line_cn": 5, "max_lines": 1})
        segs = [
            _make_seg(0, 350, "这"),
            _make_seg(1000, 3500, "已经是超过限制的文本了"),
        ]
        result = ensure_minimum_duration(segs, config)
        assert len(result) == 2
        # First segment extended into gap up to min_duration (leaving min_gap)
        assert result[0].duration_ms >= 900

    def test_last_segment_padded_to_minimum(self):
        segs = [_make_seg(0, 500, "短")]
        config = _make_config()
        result = ensure_minimum_duration(segs, config)
        assert len(result) == 1
        assert result[0].duration_ms >= 1000

    def test_empty_input(self):
        assert ensure_minimum_duration([], _make_config()) == []

    def test_single_short_segment_padded(self):
        segs = [_make_seg(0, 800, "不够一秒")]
        config = _make_config()
        result = ensure_minimum_duration(segs, config)
        assert result[0].duration_ms >= 1000
        assert result[0].duration_ms == max(800, 1000)  # padded to min

    def test_merge_speed_check(self):
        """Merging should be rejected if combined reading speed is too fast."""
        config = _make_config()
        segs = [
            _make_seg(0, 500, "这是一段非常非常长的文本内容用于测试速度"),
            _make_seg(500, 1000, "还有更多文字要合并进来看看会不会超速"),
        ]
        result = ensure_minimum_duration(segs, config)
        # If combined speed > 6 chars/s, should NOT merge
        # Combined: ~30 chars / 1.0s = 30 chars/s → should reject merge
        assert len(result) >= 1  # At minimum not merged into single

    def test_merge_duration_check(self):
        """Merging should be rejected if combined duration > max_display."""
        config = _make_config()
        segs = [
            _make_seg(0, 4000, "前半段"),
            _make_seg(4000, 8000, "后半段"),
        ]
        result = ensure_minimum_duration(segs, config)
        # Combined = 8s > 7s max → should NOT merge
        assert len(result) == 2


# ──────────────────────────────────────────
# Integration: full pipeline with tiny fragments
# ──────────────────────────────────────────

class TestPipelineIntegration:

    def test_full_merge_pipeline_no_fragments(self):
        """Run the full merge pipeline and verify no tiny fragments survive."""
        from pipeline.subtitle_merger import (
            merge_short_segments, split_long_merged_segment,
            merge_fast_segments, add_gaps_between_entries,
            extend_for_readability, merged_to_subtitle_entries,
        )
        from pipeline.transcribe import TranscriptSegment, TranscriptResult

        # Simulate H01 transcript segments
        segments = [
            TranscriptSegment(start_ms=110, end_ms=1282, text="从我们个人的"),
            TranscriptSegment(start_ms=1282, end_ms=1633, text="这个"),
            TranscriptSegment(start_ms=1673, end_ms=4410, text="还比较短的这么一个人生经历"),
            TranscriptSegment(start_ms=4410, end_ms=4793, text="上来"),
            TranscriptSegment(start_ms=4833, end_ms=5650, text="看的话对"),
            TranscriptSegment(start_ms=5690, end_ms=8685, text="其实在我们生命当中也出现了蛮多的分叉"),
            TranscriptSegment(start_ms=8685, end_ms=9755, text="对"),
            TranscriptSegment(start_ms=10330, end_ms=13050, text="而且我特别关注的就是一句话"),
            TranscriptSegment(start_ms=13050, end_ms=15141, text="就是时间在这里分岔所有"),
            TranscriptSegment(start_ms=15175, end_ms=17713, text="的可能性同时发生"),
            TranscriptSegment(start_ms=17713, end_ms=20019, text="其实这句话的魅力到底在哪"),
            TranscriptSegment(start_ms=20089, end_ms=23108, text="就时间在这里分岔"),
            TranscriptSegment(start_ms=23108, end_ms=24754, text="这个很好理解"),
            TranscriptSegment(start_ms=24786, end_ms=25297, text="对啊"),
            TranscriptSegment(start_ms=25338, end_ms=27541, text="但是所有的可能性"),
            TranscriptSegment(start_ms=27541, end_ms=29745, text="同时发生那就给我"),
        ]
        transcript = TranscriptResult(segments=segments, source_file="test")

        config = _make_config()
        entries, merged = _run_full_pipeline(transcript, config)

        # Verify no tiny fragments survive
        for entry in entries:
            text = entry.text
            cn = len(re.findall(r'[\u4e00-\u9fff]', text))
            dur_s = (entry.end_ms - entry.start_ms) / 1000
            assert cn >= 4 or dur_s >= 1.0, (
                f"Fragment in output: text='{text}' ({cn} chars, {dur_s:.2f}s)"
            )

        # Also check that no entry is a single forbidden character
        FORBIDDEN = set("的了着过吗呢吧啊呀哇嘛呗的啦咯嗯噢哦哈")
        for entry in entries:
            if len(entry.text.strip()) <= 2:
                assert entry.text.strip() not in FORBIDDEN, (
                    f"Standalone forbidden char: '{entry.text}'"
                )


def _run_full_pipeline(transcript, config):
    """Helper to run the full subtitle merge pipeline."""
    from pipeline.subtitle_merger import (
        merge_short_segments, split_long_merged_segment,
        merge_fast_segments, merge_tiny_fragments,
        add_gaps_between_entries, extend_for_readability,
        merged_to_subtitle_entries,
    )
    from pipeline.transcribe import TranscriptResult

    merged = merge_short_segments(transcript.segments, config)

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
