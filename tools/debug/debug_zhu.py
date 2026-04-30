from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import process_subtitle_content, load_custom_errata

ctx = load_project()
config = ctx.config
entries = ctx.entries
merged = ctx.merged
transcript = ctx.transcript
custom_errata = ctx.custom_errata

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
