import json
import sys
from pathlib import Path

data = json.load(open("output/audio/topic_analysis.json", "r", encoding="utf-8"))
for t in data["topics"]:
    start = t["start_ms"] / 1000
    end = t["end_ms"] / 1000
    dur = end - start
    print(f'{t["id"]}: {t["title"]} ({start:.0f}s-{end:.0f}s, {dur/60:.1f}min)')
