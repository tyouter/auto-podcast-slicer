import sys
sys.path.insert(0, ".")
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import process_subtitle_content, load_custom_errata

config = PipelineConfig()
transcript = parse_funasr_mixed_json(Path("D:/boke/garden post factory/C0257_full_mixed.json"))
entries, merged = process_transcript_to_subtitles(transcript, config)
custom_errata = load_custom_errata(Path("config/corrections.yaml"))

count = 0
for i, entry in enumerate(entries):
    if "著" in entry.text:
        next_text = entries[i+1].text if i+1 < len(entries) else ""
        gap_ms = entries[i+1].start_ms - entry.end_ms if i+1 < len(entries) else 0
        processed = process_subtitle_content(entry.text, entry.duration_s, next_text, gap_ms/1000, 18, i==len(entries)-1, custom_errata)
        print(f"  #{entry.index}: raw=\"{entry.text}\" -> processed=\"{processed}\"")
        count += 1
        if count >= 10:
            break

print(f"\nTotal entries with 著: {sum(1 for e in entries if '著' in e.text)}")

count2 = 0
for i, entry in enumerate(entries):
    if "於" in entry.text:
        next_text = entries[i+1].text if i+1 < len(entries) else ""
        gap_ms = entries[i+1].start_ms - entry.end_ms if i+1 < len(entries) else 0
        processed = process_subtitle_content(entry.text, entry.duration_s, next_text, gap_ms/1000, 18, i==len(entries)-1, custom_errata)
        print(f"  #{entry.index}: raw=\"{entry.text}\" -> processed=\"{processed}\"")
        count2 += 1
        if count2 >= 5:
            break
