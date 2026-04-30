from pathlib import Path
from dataclasses import dataclass

from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json, TranscriptResult
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import load_custom_errata


@dataclass
class ProjectContext:
    config: PipelineConfig
    transcript: TranscriptResult
    entries: list
    merged: list
    custom_errata: dict


def load_project(config: PipelineConfig | None = None) -> ProjectContext:
    if config is None:
        config = PipelineConfig()

    transcript = parse_funasr_mixed_json(config.source_transcript)
    entries, merged = process_transcript_to_subtitles(transcript, config)
    custom_errata = load_custom_errata(config.source_corrections)

    return ProjectContext(
        config=config,
        transcript=transcript,
        entries=entries,
        merged=merged,
        custom_errata=custom_errata,
    )
