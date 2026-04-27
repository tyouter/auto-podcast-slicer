import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.config import PipelineConfig
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import process_subtitle_content, load_custom_errata

config = PipelineConfig()
corrections_path = Path("config/corrections.yaml")
custom_errata = load_custom_errata(corrections_path)

mixed_json_path = Path("D:/boke/garden post factory/C0257_full_mixed.json")
transcript = parse_funasr_mixed_json(mixed_json_path)
entries, merged = process_transcript_to_subtitles(transcript, config)

processed = []
for i, entry in enumerate(entries):
    next_text = entries[i + 1].text if i + 1 < len(entries) else ""
    gap_s = (entries[i + 1].start_ms - entry.end_ms) / 1000.0 if i + 1 < len(entries) else 0
    is_last = (i == len(entries) - 1)
    processed_text = process_subtitle_content(
        text=entry.text, duration_s=entry.duration_s, next_text=next_text,
        gap_s=gap_s, max_chars=18, is_last=is_last, custom_errata=custom_errata,
        strip_punctuation=True,
    )
    processed.append({"index": i + 1, "text": processed_text, "start_s": entry.start_ms / 1000})

keywords = ["洛伯", "没有我质", "神有的状态", "倒成了", "礼貌", "小文", "意识界"]
for kw in keywords:
    print(f"\n=== 含'{kw}'的条目 ===")
    for e in processed:
        if kw in e["text"]:
            print(f"  [{e['index']}] ({e['start_s']:.0f}s) {e['text']}")
