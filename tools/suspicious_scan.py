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

suspicious = [
    (r'暴喜', '暴喜→白颊?'),
    (r'不能作品', '不能作品→改编作品?'),
    (r'不杂的', '不杂的→复杂的?'),
    (r'他这件好了', '他这件→天意?'),
    (r'唱得很好唱', '唱得→版权?'),
    (r'先排', '先排→博尔赫斯?'),
    (r'你那一小时候', '小时候→博尔赫斯?'),
    (r'跟他改变成', '改变成→改编成?'),
    (r'身体', '身体→什么?'),
    (r'传奇(?!还在|18|导演|它|就是)', '传奇→余传奇?'),
    (r'消息', '消息→小戏?'),
    (r'上课(?!程)', '上课→上戏?'),
    (r'系里面', '系→戏?'),
    (r'缓缓的', '缓缓的→多余?'),
    (r'武断', '武断→偶然?'),
    (r'可能遇到', '可能→很难?'),
    (r'保证', '保证→评估?'),
    (r'目的(?!性|型|地|的)', '目的→母题?'),
]

all_text_lines = [(e["index"], e["text"], e["start_s"]) for e in processed]

found_any = False
for pattern, note in suspicious:
    matches = []
    for idx, text, start_s in all_text_lines:
        if re.search(pattern, text):
            matches.append((idx, text, start_s))
    if matches:
        found_any = True
        print(f"\n=== {note} ===")
        for idx, text, start_s in matches:
            print(f"  [{idx}] ({start_s:.0f}s) {text}")

if not found_any:
    print("未发现可疑条目")
