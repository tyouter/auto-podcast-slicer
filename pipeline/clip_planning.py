import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.topic_analysis import TopicAnalysisResult, TopicSegment


@dataclass
class ClipDefinition:
    id: str
    title: str
    start_ms: int
    end_ms: int
    first_line: str = ""
    last_line: str = ""
    opening_type: str = ""
    ending_type: str = ""
    topic_ids: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    description: str = ""

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
class MaterialDefinition:
    id: str
    material_type: str
    category: str
    start_ms: int
    end_ms: int
    label: str = ""
    source_clip_id: str = ""

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0


@dataclass
class VersionPlan:
    version_key: str
    version_name: str
    theme: str
    positioning: str
    clips: list[ClipDefinition] = field(default_factory=list)
    openings: list[MaterialDefinition] = field(default_factory=list)
    transitions: list[MaterialDefinition] = field(default_factory=list)
    endings: list[MaterialDefinition] = field(default_factory=list)
    estimated_duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "version_key": self.version_key,
            "version_name": self.version_name,
            "theme": self.theme,
            "positioning": self.positioning,
            "clips": [asdict(c) for c in self.clips],
            "openings": [asdict(m) for m in self.openings],
            "transitions": [asdict(m) for m in self.transitions],
            "endings": [asdict(m) for m in self.endings],
            "estimated_duration_s": self.estimated_duration_s,
            "clip_count": len(self.clips),
        }

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


@dataclass
class ClipPlanningResult:
    versions: list[VersionPlan] = field(default_factory=list)
    source_file: str = ""
    total_topics: int = 0

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "total_topics": self.total_topics,
            "version_count": len(self.versions),
            "versions": [v.to_dict() for v in self.versions],
        }

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def select_clips_for_topic(
    topic: TopicSegment,
    config: PipelineConfig,
) -> list[ClipDefinition]:
    min_dur = config.get("pipeline.clip_planning.min_clip_duration", 120) * 1000
    max_dur = config.get("pipeline.clip_planning.max_clip_duration", 900) * 1000
    optimal_dur = config.get("pipeline.clip_planning.optimal_clip_duration", 300) * 1000

    clips = []
    topic_duration = topic.end_ms - topic.start_ms

    if topic_duration >= min_dur:
        clip = ClipDefinition(
            id=f"clip_{topic.id}",
            title=topic.title,
            start_ms=topic.start_ms,
            end_ms=topic.end_ms,
            first_line=topic.segments[0].get("text", "")[:50] if topic.segments else "",
            last_line=topic.segments[-1].get("text", "")[:50] if topic.segments else "",
            topic_ids=[topic.id],
            keywords=topic.keywords,
            description=topic.summary[:100],
        )
        clips.append(clip)
    elif topic_duration > 0:
        clip = ClipDefinition(
            id=f"clip_{topic.id}",
            title=topic.title,
            start_ms=topic.start_ms,
            end_ms=topic.end_ms,
            first_line=topic.segments[0].get("text", "")[:50] if topic.segments else "",
            last_line=topic.segments[-1].get("text", "")[:50] if topic.segments else "",
            topic_ids=[topic.id],
            keywords=topic.keywords,
            description=topic.summary[:100],
        )
        clips.append(clip)

    return clips


def extract_materials_from_clip(
    clip: ClipDefinition,
    config: PipelineConfig,
) -> tuple[list[MaterialDefinition], list[MaterialDefinition], list[MaterialDefinition]]:
    opening_types = config.get("pipeline.clip_planning.opening_types", [])
    ending_types = config.get("pipeline.clip_planning.ending_types", [])

    openings = []
    endings = []
    transitions = []

    opening_dur_ms = min(30000, clip.duration_s * 0.1 * 1000)
    if opening_dur_ms > 5000:
        openings.append(MaterialDefinition(
            id=f"opening_{clip.id}",
            material_type="opening",
            category=opening_types[0] if opening_types else "golden_quote",
            start_ms=clip.start_ms,
            end_ms=clip.start_ms + int(opening_dur_ms),
            label=f"开场_{clip.title}",
            source_clip_id=clip.id,
        ))

    ending_dur_ms = min(20000, clip.duration_s * 0.08 * 1000)
    if ending_dur_ms > 3000:
        endings.append(MaterialDefinition(
            id=f"ending_{clip.id}",
            material_type="ending",
            category=ending_types[0] if ending_types else "summary",
            start_ms=clip.end_ms - int(ending_dur_ms),
            end_ms=clip.end_ms,
            label=f"结尾_{clip.title}",
            source_clip_id=clip.id,
        ))

    return openings, transitions, endings


def group_topics_into_versions(
    topics: list[TopicSegment],
    config: PipelineConfig,
) -> list[list[TopicSegment]]:
    min_clips = config.get("pipeline.clip_planning.min_clips_per_version", 2)
    max_clips = config.get("pipeline.clip_planning.max_clips_per_version", 5)

    if not topics:
        return []

    keyword_groups = {}
    for topic in topics:
        primary_kw = topic.keywords[0] if topic.keywords else "其他"
        if primary_kw not in keyword_groups:
            keyword_groups[primary_kw] = []
        keyword_groups[primary_kw].append(topic)

    versions = []
    current_group = []

    for kw, kw_topics in keyword_groups.items():
        for topic in kw_topics:
            current_group.append(topic)
            if len(current_group) >= max_clips:
                versions.append(current_group)
                current_group = []

    remaining = [t for kw_topics in keyword_groups.values() for t in kw_topics
                 if not any(t in v for v in versions)]
    if remaining:
        for topic in remaining:
            current_group.append(topic)
            if len(current_group) >= max_clips:
                versions.append(current_group)
                current_group = []

    if current_group:
        if len(current_group) >= min_clips:
            versions.append(current_group)
        elif versions:
            versions[-1].extend(current_group)
        else:
            versions.append(current_group)

    return versions


def plan_clips(analysis: TopicAnalysisResult, config: PipelineConfig) -> ClipPlanningResult:
    topic_groups = group_topics_into_versions(analysis.topics, config)

    versions = []
    for i, group in enumerate(topic_groups):
        all_clips = []
        all_openings = []
        all_transitions = []
        all_endings = []

        for topic in group:
            clips = select_clips_for_topic(topic, config)
            all_clips.extend(clips)
            for clip in clips:
                openings, transitions, endings = extract_materials_from_clip(clip, config)
                all_openings.extend(openings)
                all_transitions.extend(transitions)
                all_endings.extend(endings)

        primary_keywords = list(set(kw for t in group for kw in t.keywords[:2]))
        theme_name = "、".join(primary_keywords[:3]) if primary_keywords else f"版本{i + 1}"

        version = VersionPlan(
            version_key=f"v{i + 1}_{theme_name}",
            version_name=theme_name,
            theme=theme_name,
            positioning=f"基于{len(all_clips)}个切片的{theme_name}主题版本",
            clips=all_clips,
            openings=all_openings,
            transitions=all_transitions,
            endings=all_endings,
            estimated_duration_s=sum(c.duration_s for c in all_clips),
        )
        versions.append(version)

    return ClipPlanningResult(
        versions=versions,
        source_file=analysis.source_file,
        total_topics=len(analysis.topics),
    )
