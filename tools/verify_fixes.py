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
    t = process_subtitle_content(
        text=entry.text, duration_s=entry.duration_s, next_text=next_text,
        gap_s=gap_s, max_chars=18, is_last=is_last,
        custom_errata=custom_errata, strip_punctuation=True,
    )
    processed.append({"index": i + 1, "text": t, "start_s": entry.start_ms / 1000})

checks = [
    ("武断", "应为偶然"),
    ("可能遇到", "应为很难遇到"),
    ("一个艺术家", "应为一个个艺术家"),
    ("去上课", "应为去上戏"),
    ("采戏", "应为排戏"),
    ("你后来说", "应为或者说"),
    ("系里面", "应为戏里面"),
    ("消息", "应为小戏"),
    ("回到目的", "应为回到母题"),
    ("给我保证", "应为给我评估"),
    ("杨他计算", "应为一样他计算"),
    ("都有跟你", "应为都有个你"),
    ("小径分岔的换源", "应为小径分岔的花园"),
    ("贡布里希西", "应为贡布里希"),
    ("话筒上", "应为花园上"),
    ("美食美课", "应为每时每刻"),
    ("换源", "应为花园"),
]

all_text = " ".join(e["text"] for e in processed)
print("=== 验证用户指出的错误是否已修复 ===")
fixed = 0
unfixed = 0
for keyword, desc in checks:
    if keyword in all_text:
        for e in processed:
            if keyword in e["text"]:
                print(f'  ❌ 未修复: "{keyword}" ({desc}) 出现在 [{e["index"]}] ({e["start_s"]:.0f}s) {e["text"]}')
                break
        unfixed += 1
    else:
        print(f'  ✅ 已修复: "{keyword}" 不再出现')
        fixed += 1

print(f"\n总计: {len(checks)} 项, 已修复: {fixed}, 未修复: {unfixed}")

print("\n=== 验证正确文本是否出现 ===")
correct_checks = [
    "偶然", "很难遇到", "一个个艺术家", "去上戏", "排戏",
    "或者说", "戏里面", "小戏", "回到母题", "给我评估",
    "一样他计算", "都有个你", "小径分岔的花园", "贡布里希",
    "花园上", "每时每刻",
]
for keyword in correct_checks:
    count = all_text.count(keyword)
    if count > 0:
        print(f'  ✅ "{keyword}" 出现 {count} 次')
    else:
        print(f'  ⚠️ "{keyword}" 未出现')
