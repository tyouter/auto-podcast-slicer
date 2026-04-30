import re
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

suspicious_contexts = [
    (r'拍的.{0,2}消息', '消息→小戏'),
    (r'去上课(?!程|的)', '上课→上戏'),
    (r'某一个系(?!统|列|统)', '系→戏'),
    (r'系里面', '系→戏'),
    (r'目的性', None),
    (r'目的型', None),
    (r'节目的目的', None),
    (r'传奇(?!还在|18|导演|它|就是)', '传奇→余传奇?'),
    (r'偶然', None),
    (r'排戏', None),
    (r'上戏', None),
    (r'小戏', None),
    (r'母题', None),
    (r'评估', None),
    (r'漫无目的', None),
]

all_text_lines = [(e["index"], e["text"], e["start_s"]) for e in processed]

for pattern, note in suspicious_contexts:
    matches = []
    for idx, text, start_s in all_text_lines:
        if re.search(pattern, text):
            matches.append((idx, text, start_s))
    if matches and note:
        print(f"\n=== {note} (pattern: {pattern}) ===")
        for idx, text, start_s in matches:
            print(f"  [{idx}] ({start_s:.0f}s) {text}")
    elif matches and note is None:
        pass

print("\n=== 全量字幕输出（供人工审查）===")
for e in processed:
    print(f"[{e['index']:4d}] ({e['start_s']:6.0f}s) {e['text']}")
