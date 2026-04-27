import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional
from pipeline.config import PipelineConfig
from pipeline.transcribe import TranscriptResult, TranscriptSegment


@dataclass
class TopicSegment:
    id: str
    title: str
    start_ms: int
    end_ms: int
    keywords: list[str] = field(default_factory=list)
    summary: str = ""
    coherence_score: float = 0.0
    segments: list[dict] = field(default_factory=list)

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
    def duration_min(self) -> float:
        return self.duration_s / 60.0


@dataclass
class TopicAnalysisResult:
    topics: list[TopicSegment] = field(default_factory=list)
    source_file: str = ""
    total_duration_s: float = 0.0
    silence_points: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "total_duration_s": self.total_duration_s,
            "topic_count": len(self.topics),
            "topics": [asdict(t) for t in self.topics],
            "silence_points": self.silence_points,
        }

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def detect_silence_points(transcript: TranscriptResult, config: PipelineConfig) -> list[dict]:
    threshold_db = config.get("pipeline.topic_analysis.silence_threshold_db", -40)
    min_duration = config.get("pipeline.topic_analysis.silence_min_duration", 1.5)

    gaps = []
    segments = sorted(transcript.segments, key=lambda s: s.start_ms)
    for i in range(1, len(segments)):
        gap_ms = segments[i].start_ms - segments[i - 1].end_ms
        if gap_ms >= min_duration * 1000:
            gaps.append({
                "start_ms": segments[i - 1].end_ms,
                "end_ms": segments[i].start_ms,
                "duration_ms": gap_ms,
                "position_s": segments[i - 1].end_ms / 1000.0,
            })

    return gaps


def segment_by_silence_and_coherence(
    transcript: TranscriptResult,
    silence_points: list[dict],
    config: PipelineConfig,
) -> list[list[TranscriptSegment]]:
    min_duration = config.get("pipeline.topic_analysis.min_segment_duration", 60) * 1000
    max_duration = config.get("pipeline.topic_analysis.max_segment_duration", 600) * 1000

    segments = sorted(transcript.segments, key=lambda s: s.start_ms)
    if not segments:
        return []

    silence_positions = {sp["start_ms"] for sp in silence_points}

    groups = []
    current_group = [segments[0]]

    for i in range(1, len(segments)):
        gap_ms = segments[i].start_ms - segments[i - 1].end_ms
        group_duration = sum(s.end_ms - s.start_ms for s in current_group)

        should_split = False
        if segments[i - 1].end_ms in silence_positions and group_duration >= min_duration:
            should_split = True
        if group_duration >= max_duration:
            should_split = True

        if should_split and group_duration >= min_duration:
            groups.append(current_group)
            current_group = [segments[i]]
        else:
            current_group.append(segments[i])

    if current_group:
        groups.append(current_group)

    return groups


def extract_keywords_from_text(text: str) -> list[str]:
    stop_words = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
        "看", "好", "自己", "这", "他", "她", "它", "那", "这个", "那个", "什么",
        "怎么", "为什么", "因为", "所以", "但是", "然后", "如果", "就是", "其实",
        "对", "吧", "啊", "嗯", "哦", "嘛", "呢", "哈", "呀", "哎", "唉",
    }
    words = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
    freq = {}
    for w in words:
        if w not in stop_words and len(w) >= 2:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:10]]


def generate_topic_title(segments: list[TranscriptSegment], keywords: list[str]) -> str:
    if keywords:
        return keywords[0]
    if segments:
        first_text = segments[0].text[:20]
        return first_text + ("..." if len(segments[0].text) > 20 else "")
    return "未命名主题"


def compute_coherence(segments: list[TranscriptSegment], keywords: list[str]) -> float:
    if not segments or not keywords:
        return 0.0

    total_text = " ".join(s.text for s in segments)
    keyword_hits = sum(1 for kw in keywords if kw in total_text)
    total_chars = len(total_text)

    if total_chars == 0:
        return 0.0

    keyword_density = keyword_hits / len(keywords) if keywords else 0
    length_score = min(1.0, len(segments) / 10)

    return min(1.0, keyword_density * 0.7 + length_score * 0.3)


def analyze_topics(transcript: TranscriptResult, config: PipelineConfig) -> TopicAnalysisResult:
    silence_points = detect_silence_points(transcript, config)
    groups = segment_by_silence_and_coherence(transcript, silence_points, config)

    topics = []
    for i, group in enumerate(groups):
        if not group:
            continue

        all_text = " ".join(s.text for s in group)
        keywords = extract_keywords_from_text(all_text)
        title = generate_topic_title(group, keywords)
        coherence = compute_coherence(group, keywords)

        topic = TopicSegment(
            id=f"topic_{i + 1:03d}",
            title=title,
            start_ms=group[0].start_ms,
            end_ms=group[-1].end_ms,
            keywords=keywords[:5],
            summary=all_text[:200] + ("..." if len(all_text) > 200 else ""),
            coherence_score=round(coherence, 3),
            segments=[{"start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text} for s in group],
        )
        topics.append(topic)

    total_duration = topics[-1].end_ms / 1000.0 if topics else 0.0

    return TopicAnalysisResult(
        topics=topics,
        source_file=transcript.source_file,
        total_duration_s=total_duration,
        silence_points=silence_points,
    )
