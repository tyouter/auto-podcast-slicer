import sys
sys.path.insert(0, ".")
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import process_subtitle_content, load_custom_errata, TRADITIONAL_ONLY

config = PipelineConfig()
transcript = parse_funasr_mixed_json(Path("D:/boke/garden post factory/C0257_full_mixed.json"))
entries, merged = process_transcript_to_subtitles(transcript, config)
custom_errata = load_custom_errata(Path("config/corrections.yaml"))

processed = []
for i, entry in enumerate(entries):
    next_text = entries[i+1].text if i+1 < len(entries) else ""
    gap_ms = entries[i+1].start_ms - entry.end_ms if i+1 < len(entries) else 0
    p = process_subtitle_content(entry.text, entry.duration_s, next_text, gap_ms/1000, 18, i==len(entries)-1, custom_errata)
    processed.append((entry.index, p))

for idx, text in processed:
    found = [c for c in text if c in TRADITIONAL_ONLY]
    if found:
        print(f"  #{idx}: \"{text}\" - traditional chars: {''.join(found)}")
