from pathlib import Path
from dataclasses import dataclass

from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json, TranscriptResult
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import load_custom_errata, load_errata_from_project


@dataclass
class ProjectContext:
    config: PipelineConfig
    transcript: TranscriptResult
    entries: list
    merged: list
    custom_errata: dict


def _inject_project_verification(config: PipelineConfig):
    from pipeline.word_verifier import set_project_word_dict_extra, set_project_context_disambiguation
    from pipeline.subtitle_content import set_project_verification_config

    verification = config.verification_config
    if not verification:
        return

    word_dict_extra = verification.get("word_dict_extra", [])
    if word_dict_extra:
        set_project_word_dict_extra(word_dict_extra)

    context_disambiguation = verification.get("context_disambiguation", [])
    if context_disambiguation:
        set_project_context_disambiguation(context_disambiguation)

    set_project_verification_config(verification)


def load_project(
    config: PipelineConfig | None = None,
    project_dir: Path | str | None = None,
) -> ProjectContext:
    if config is None:
        config = PipelineConfig(project_dir=project_dir)
    elif project_dir is not None:
        raise ValueError("Provide either config or project_dir, not both")

    if config.project_dir is not None:
        load_errata_from_project(config.project_dir)
        _inject_project_verification(config)

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
