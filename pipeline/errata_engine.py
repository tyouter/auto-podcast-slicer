import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def load_errata_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def flatten_errata(errata_data: dict) -> dict:
    flat = {}
    for category in ("authors", "works", "idioms", "common", "variants",
                     "asr_phonetic", "asr_noise"):
        section = errata_data.get(category, {})
        if isinstance(section, dict):
            flat.update(section)
    return flat


def load_asr_phonetic_patterns(errata_data: dict) -> list[tuple[str, str]]:
    raw = errata_data.get("asr_phonetic_patterns", [])
    result = []
    for item in raw:
        if isinstance(item, dict) and "pattern" in item and "replacement" in item:
            result.append((item["pattern"], item["replacement"]))
    return result


def load_semantic_patterns(errata_data: dict) -> list[tuple[str, Optional[str], Optional[str]]]:
    raw = errata_data.get("semantic_patterns", [])
    result = []
    for item in raw:
        if isinstance(item, dict) and "pattern" in item:
            correction = item.get("correction")
            description = item.get("description")
            result.append((item["pattern"], correction, description))
    return result


@dataclass
class ErrataConfig:
    flat_errata: dict = field(default_factory=dict)
    asr_phonetic_patterns: list[tuple[str, str]] = field(default_factory=list)
    semantic_patterns: list[tuple[str, Optional[str], Optional[str]]] = field(default_factory=list)
    _raw_data: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_project_dir(cls, project_dir: Path) -> "ErrataConfig":
        errata_path = project_dir / "errata.yaml"
        data = load_errata_yaml(errata_path)
        if not data:
            return cls()
        flat = flatten_errata(data)
        asr_patterns = load_asr_phonetic_patterns(data)
        semantic_pats = load_semantic_patterns(data)
        return cls(
            flat_errata=flat,
            asr_phonetic_patterns=asr_patterns,
            semantic_patterns=semantic_pats,
            _raw_data=data,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ErrataConfig":
        flat = flatten_errata(data)
        asr_patterns = load_asr_phonetic_patterns(data)
        semantic_pats = load_semantic_patterns(data)
        return cls(
            flat_errata=flat,
            asr_phonetic_patterns=asr_patterns,
            semantic_patterns=semantic_pats,
            _raw_data=data,
        )


def apply_errata(text: str, errata: dict) -> str:
    for wrong, correct in errata.items():
        if wrong != correct and wrong in text:
            text = text.replace(wrong, correct)
    return text


def apply_asr_phonetic_corrections(text: str, errata: dict, patterns: list[tuple[str, str]]) -> str:
    sorted_keys = sorted(
        [k for k in errata.keys() if k and errata.get(k) != k],
        key=len,
        reverse=True,
    )
    for _ in range(3):
        changed = False
        for wrong in sorted_keys:
            correct = errata[wrong]
            if wrong in text:
                text = text.replace(wrong, correct)
                changed = True
        if not changed:
            break
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text


def detect_asr_phonetic_errors(
    text: str,
    errata: dict,
    patterns: list[tuple[str, str]],
) -> list[dict]:
    errors = []
    for wrong, correct in errata.items():
        if wrong != correct and wrong in text:
            errors.append({
                "type": "asr_phonetic_error",
                "wrong": wrong,
                "correct": correct,
                "description": f"ASR语音识别错误：'{wrong}'应为'{correct}'",
            })
    for pattern, replacement in patterns:
        match = re.search(pattern, text)
        if match:
            errors.append({
                "type": "asr_phonetic_pattern",
                "wrong": match.group(),
                "correct": replacement,
                "description": f"ASR语音识别模式错误：'{match.group()}'应为'{replacement}'",
            })
    return errors


def validate_errata_entries(entries: list[dict], errata: dict) -> list[dict]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        for wrong, correct in errata.items():
            if wrong != correct and wrong in text:
                issues.append({
                    "entry_index": entry.get("index", i),
                    "issue_type": "errata_violation",
                    "severity": "critical",
                    "description": f"勘误词'{wrong}'应纠正为'{correct}'",
                    "suggestion": f"替换'{wrong}'为'{correct}'",
                })
    return issues


def validate_semantic_entries(entries: list[dict], patterns: list[tuple[str, Optional[str], Optional[str]]]) -> list[dict]:
    issues = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "").strip()
        if not text:
            continue
        for pattern, correction, description in patterns:
            if correction is None:
                continue
            match = re.search(pattern, text)
            if match:
                issues.append({
                    "entry_index": entry.get("index", i),
                    "issue_type": "semantic_anomaly",
                    "severity": "critical",
                    "description": f"逐句语义审查：{description}",
                    "suggestion": f"替换为'{correction}'",
                })
    return issues
