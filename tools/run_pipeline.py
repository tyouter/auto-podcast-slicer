import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
from pipeline.config import PipelineConfig
from pipeline.ingest import ingest
from pipeline.transcribe import transcribe, parse_funasr_mixed_json, TranscriptResult
from pipeline.topic_analysis import analyze_topics
from pipeline.clip_planning import plan_clips
from pipeline.audio_processor import process_version_audio
from pipeline.subtitle_generator import generate_subtitles_from_transcript, generate_clip_subtitles
from pipeline.subtitle_verifier import verify_subtitles
from pipeline.audio_verifier import verify_audio
from pipeline.loudness_normalizer import normalize_loudness
from pipeline.video_processor import process_version_video
from pipeline.quality_checker import run_quality_check
from autoresearch.experiment import Experiment
from autoresearch.strategies import get_strategy, get_all_strategies, get_recommended_strategies
from autoresearch.metrics import compute_metrics_from_quality_report
from autoresearch.logger import ResearchLogger


def run_full_pipeline(source: Path, config: PipelineConfig | None = None) -> dict:
    if config is None:
        config = PipelineConfig()

    output_dir = config.output_dir
    logger = ResearchLogger(output_dir / "experiments")

    logger.info("pipeline", f"Starting pipeline for {source}")

    # Stage 1: Ingest
    logger.info("pipeline", "Stage 1: Ingesting media")
    ingest_result = ingest(source, config)
    audio_source = Path(ingest_result["audio_source"])
    logger.info("pipeline", f"Audio source: {audio_source}", {"duration_s": ingest_result["asset"]["duration_s"]})

    # Stage 2: Transcribe
    logger.info("pipeline", "Stage 2: Transcribing audio")
    transcript_path = output_dir / "audio" / f"{audio_source.stem}_transcript.json"
    if transcript_path.exists():
        transcript = TranscriptResult.load(transcript_path)
        logger.info("pipeline", f"Loaded existing transcript ({len(transcript.segments)} segments)")
    else:
        mixed_json = output_dir / "audio" / f"{audio_source.stem}_mixed.json"
        if mixed_json.exists():
            transcript = parse_funasr_mixed_json(mixed_json)
            logger.info("pipeline", f"Loaded FunASR mixed JSON ({len(transcript.segments)} segments)")
        else:
            transcript = transcribe(audio_source, config)
            logger.info("pipeline", f"Transcribed ({len(transcript.segments)} segments)")

    # Stage 3: Topic Analysis
    logger.info("pipeline", "Stage 3: Analyzing topics")
    analysis = analyze_topics(transcript, config)
    analysis.save(output_dir / "audio" / "topic_analysis.json")
    logger.info("pipeline", f"Found {len(analysis.topics)} topics")

    # Stage 4: Clip Planning
    logger.info("pipeline", "Stage 4: Planning clips")
    planning = plan_clips(analysis, config)
    planning.save(output_dir / "clips" / "clip_planning.json")
    logger.info("pipeline", f"Planned {len(planning.versions)} versions")

    # Stage 5: Generate full subtitles
    logger.info("pipeline", "Stage 5: Generating subtitles")
    corrections_path = PROJECT_ROOT / "config" / "corrections.yaml"
    corrections = {}
    if corrections_path.exists():
        import yaml
        with open(corrections_path, "r", encoding="utf-8") as f:
            corrections = yaml.safe_load(f) or {}

    full_subtitles = generate_subtitles_from_transcript(transcript, config, corrections)
    srt_dir = output_dir / "srt"
    srt_dir.mkdir(parents=True, exist_ok=True)
    full_subtitles.save_srt(srt_dir / f"{audio_source.stem}.srt")
    logger.info("pipeline", f"Generated {len(full_subtitles.entries)} subtitle entries")

    # Stage 6: Process each version
    all_results = {}
    for version in planning.versions:
        logger.info("pipeline", f"Processing version: {version.version_key}")

        # Audio processing
        try:
            audio_results = process_version_audio(audio_source, version, output_dir / "clips", config)
            logger.info("pipeline", f"Audio processed: {len(audio_results)} clips")
        except Exception as e:
            logger.error("pipeline", f"Audio processing failed: {e}")
            audio_results = []

        # Subtitle processing per clip
        version_srt_dir = output_dir / "clips" / version.version_key / "srt"
        version_srt_dir.mkdir(parents=True, exist_ok=True)
        for clip in version.clips:
            clip_subtitles = generate_clip_subtitles(full_subtitles, clip, config)
            clip_subtitles.save_srt(version_srt_dir / f"{clip.id}.srt")

        # Video processing (if source is video)
        video_results = []
        if ingest_result["asset"]["media_type"] == "video":
            try:
                video_results = process_version_video(source, version, output_dir / "clips", config)
                logger.info("pipeline", f"Video processed: {len(video_results)} clips")
            except Exception as e:
                logger.error("pipeline", f"Video processing failed: {e}")

        # Quality check
        version_dir = output_dir / "clips" / version.version_key
        quality_report = run_quality_check(version_dir, config, version.version_key)
        logger.info("pipeline", f"Quality: score={quality_report.overall_score:.1f}, passed={quality_report.passed}")

        all_results[version.version_key] = {
            "audio_results": [r.to_dict() for r in audio_results],
            "video_results": [r.to_dict() for r in video_results],
            "quality": quality_report.to_dict(),
        }

    # Stage 7: Loudness normalization
    logger.info("pipeline", "Stage 7: Loudness normalization")
    for version in planning.versions:
        slices_dir = output_dir / "clips" / version.version_key / "slices"
        if slices_dir.exists():
            for wav_file in slices_dir.glob("*.wav"):
                normalized_path = slices_dir / f"{wav_file.stem}_normalized.wav"
                if not normalized_path.exists():
                    try:
                        normalize_loudness(wav_file, normalized_path)
                        logger.info("pipeline", f"Normalized: {wav_file.name}")
                    except Exception as e:
                        logger.warning("pipeline", f"Normalization failed for {wav_file.name}: {e}")

    # Final summary
    summary = {
        "source": str(source),
        "timestamp": datetime.now().isoformat(),
        "versions": len(planning.versions),
        "topics": len(analysis.topics),
        "subtitle_entries": len(full_subtitles.entries),
        "results": all_results,
    }

    summary_path = output_dir / "pipeline_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("pipeline", f"Pipeline complete. Summary saved to {summary_path}")

    return summary
