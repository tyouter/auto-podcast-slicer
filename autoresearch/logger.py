import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class LogEntry:
    timestamp: str
    level: str
    component: str
    message: str
    data: dict = field(default_factory=dict)


class ResearchLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / "research_log.jsonl"
        self.entries: list[LogEntry] = []

    def _write(self, entry: LogEntry):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        self.entries.append(entry)

    def info(self, component: str, message: str, data: dict | None = None):
        self._write(LogEntry(
            timestamp=datetime.now().isoformat(),
            level="info",
            component=component,
            message=message,
            data=data or {},
        ))

    def warning(self, component: str, message: str, data: dict | None = None):
        self._write(LogEntry(
            timestamp=datetime.now().isoformat(),
            level="warning",
            component=component,
            message=message,
            data=data or {},
        ))

    def error(self, component: str, message: str, data: dict | None = None):
        self._write(LogEntry(
            timestamp=datetime.now().isoformat(),
            level="error",
            component=component,
            message=message,
            data=data or {},
        ))

    def experiment(self, experiment_id: str, message: str, data: dict | None = None):
        self._write(LogEntry(
            timestamp=datetime.now().isoformat(),
            level="experiment",
            component=f"experiment:{experiment_id}",
            message=message,
            data=data or {},
        ))

    def get_recent(self, count: int = 20) -> list[dict]:
        entries = []
        if self.log_file.exists():
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-count:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def get_summary(self) -> dict:
        if not self.log_file.exists():
            return {"total_entries": 0}

        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        levels = {}
        for line in lines:
            try:
                entry = json.loads(line)
                level = entry.get("level", "unknown")
                levels[level] = levels.get(level, 0) + 1
            except json.JSONDecodeError:
                pass

        return {
            "total_entries": len(lines),
            "levels": levels,
        }
