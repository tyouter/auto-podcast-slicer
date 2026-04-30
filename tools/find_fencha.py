import json
from pipeline.loader import load_project

ctx = load_project()
mixed_json_path = ctx.config.source_transcript
with open(mixed_json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

segments = data["segments"]

# Find segments with direct 分岔/分叉 references
fencha_segments = []
for i, seg in enumerate(segments):
    text = seg["text"]
    if "分岔" in text or "分叉" in text or "分差" in text:
        fencha_segments.append((i, seg))

print(f"Found {len(fencha_segments)} segments with direct fencha references:")
for idx, seg in fencha_segments:
    start = seg["start"]
    end = seg["end"]
    text = seg["text"][:80]
    print(f"  [{start:.0f}s-{end:.0f}s] {text}")

print()

# Find broader thematic segments about forking paths in different domains
domain_keywords = {
    "文学与博尔赫斯": ["博尔赫斯", "花园", "小说", "文学", "故事"],
    "时间哲学": ["时间", "分岔", "过去", "未来", "同时"],
    "可能性与选择": ["可能性", "选择", "路径", "决定", "如果"],
    "命运与偶然": ["命运", "偶然", "必然", "注定", "随机"],
    "人生分岔": ["人生", "路口", "转折", "方向", "迷茫"],
    "创作分岔": ["创作", "灵感", "表达", "艺术", "作品"],
}

for domain, kws in domain_keywords.items():
    matching = []
    for seg in segments:
        text = seg["text"]
        if any(kw in text for kw in kws):
            matching.append(seg)
    if matching:
        ranges = []
        current_start = matching[0]["start"]
        current_end = matching[0]["end"]
        for seg in matching[1:]:
            if seg["start"] - current_end < 30:
                current_end = seg["end"]
            else:
                ranges.append((current_start, current_end))
                current_start = seg["start"]
                current_end = seg["end"]
        ranges.append((current_start, current_end))

        print(f"{domain}: {len(matching)} segments, {len(ranges)} ranges")
        for start, end in sorted(ranges, key=lambda x: -(x[1]-x[0]))[:3]:
            duration = end - start
            if duration > 60:
                print(f"  {start:.0f}s - {end:.0f}s ({duration/60:.1f}min)")
