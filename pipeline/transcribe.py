import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from pipeline.config import PipelineConfig


@dataclass
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None
    confidence: float = 1.0

    @property
    def start_s(self) -> float:
        return self.start_ms / 1000.0

    @property
    def end_s(self) -> float:
        return self.end_ms / 1000.0

    @property
    def duration_s(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0


@dataclass
class TranscriptResult:
    segments: list[TranscriptSegment] = field(default_factory=list)
    source_file: str = ""
    engine: str = ""
    language: str = "zh"
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "engine": self.engine,
            "language": self.language,
            "duration_s": self.duration_s,
            "segment_count": len(self.segments),
            "segments": [asdict(s) for s in self.segments],
        }

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptResult":
        segments = [TranscriptSegment(**s) for s in data.get("segments", [])]
        return cls(
            segments=segments,
            source_file=data.get("source_file", ""),
            engine=data.get("engine", ""),
            language=data.get("language", "zh"),
            duration_s=data.get("duration_s", 0.0),
        )

    @classmethod
    def load(cls, path: Path) -> "TranscriptResult":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def transcribe_funasr(audio_path: Path, config: PipelineConfig) -> TranscriptResult:
    cfg = config.get("pipeline.transcribe.funasr", {})
    model = cfg.get("model", "paraformer-zh")

    try:
        from funasr import AutoModel
        auto_model = AutoModel(model=model)
        result = auto_model.generate(input=str(audio_path), batch_size_s=300)
    except ImportError:
        result = _run_funasr_cli(audio_path, model)

    segments = []
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "timestamp" in item:
                for ts in item["timestamp"]:
                    segments.append(TranscriptSegment(
                        start_ms=int(ts[0]),
                        end_ms=int(ts[1]),
                        text=ts[2] if len(ts) > 2 else item.get("text", ""),
                    ))
            elif isinstance(item, dict) and "text" in item:
                segments.append(TranscriptSegment(
                    start_ms=0,
                    end_ms=0,
                    text=item["text"],
                ))

    return TranscriptResult(
        segments=segments,
        source_file=str(audio_path),
        engine="funasr",
        language="zh",
    )


def _run_funasr_cli(audio_path: Path, model: str) -> list:
    cmd = [
        "python", "-c",
        f"from funasr import AutoModel; m=AutoModel(model='{model}'); print(m.generate(input='{audio_path}', batch_size_s=300))"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"FunASR transcription failed: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else []


def transcribe_whisper(audio_path: Path, config: PipelineConfig) -> TranscriptResult:
    cfg = config.get("pipeline.transcribe.whisper", {})
    model_name = cfg.get("model", "large-v3")
    language = cfg.get("language", "zh")

    try:
        from faster_whisper import WhisperModel
        device = "cuda" if _cuda_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(
            str(audio_path), language=language, vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments = []
        for seg in segments_iter:
            segments.append(TranscriptSegment(
                start_ms=int(seg.start * 1000),
                end_ms=int(seg.end * 1000),
                text=seg.text.strip(),
                confidence=seg.avg_logprob if hasattr(seg, "avg_logprob") else 1.0,
            ))

        return TranscriptResult(
            segments=segments,
            source_file=str(audio_path),
            engine="whisper",
            language=info.language,
            duration_s=info.duration,
        )
    except ImportError:
        return _run_whisper_cli(audio_path, model_name, language)


def _run_whisper_cli(audio_path: Path, model: str, language: str) -> TranscriptResult:
    cmd = [
        "whisper", str(audio_path),
        "--model", model,
        "--language", language,
        "--output_format", "json",
        "--output_dir", str(audio_path.parent),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Whisper transcription failed: {result.stderr}")

    json_path = audio_path.with_suffix(".json")
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        segments = []
        for seg in data.get("segments", []):
            segments.append(TranscriptSegment(
                start_ms=int(seg["start"] * 1000),
                end_ms=int(seg["end"] * 1000),
                text=seg["text"].strip(),
            ))
        return TranscriptResult(
            segments=segments,
            source_file=str(audio_path),
            engine="whisper",
            language=language,
        )
    return TranscriptResult(source_file=str(audio_path), engine="whisper", language=language)


def parse_funasr_mixed_json(json_path: Path) -> TranscriptResult:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    duration_s = 0.0

    if isinstance(data, dict):
        duration_s = data.get("duration", 0)
        seg_list = data.get("segments", [])
        if isinstance(seg_list, list):
            for item in seg_list:
                if isinstance(item, dict):
                    start = item.get("start", item.get("begin", 0))
                    end = item.get("end", 0)
                    text = item.get("text", item.get("sentence", ""))
                    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and text:
                        start_ms = int(start * 1000)
                        end_ms = int(end * 1000)
                        segments.append(TranscriptSegment(
                            start_ms=start_ms,
                            end_ms=end_ms,
                            text=text.strip(),
                        ))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                start = item.get("start", item.get("begin", 0))
                end = item.get("end", 0)
                text = item.get("text", item.get("sentence", ""))
                if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                    start_ms = int(start * 1000) if start < 100000 else int(start)
                    end_ms = int(end * 1000) if end < 100000 else int(end)
                    segments.append(TranscriptSegment(
                        start_ms=start_ms,
                        end_ms=end_ms,
                        text=text.strip() if text else "",
                    ))
    return TranscriptResult(
        segments=segments,
        source_file=str(json_path),
        engine="funasr_mixed",
        language="zh",
        duration_s=duration_s,
    )


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def transcribe(audio_path: Path, config: PipelineConfig) -> TranscriptResult:
    engine = config.get("pipeline.transcribe.engine", "funasr")

    if engine == "whisper":
        result = transcribe_whisper(audio_path, config)
    else:
        result = transcribe_funasr(audio_path, config)

    output_dir = config.output_dir / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    result.save(output_dir / f"{audio_path.stem}_transcript.json")

    return result
