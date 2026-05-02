import json
from pathlib import Path
from pipeline.loader import load_project

ctx = load_project()
custom_errata = ctx.custom_errata

base = Path("output/short_videos_v2")

subtitle_stats = {"total": 0, "too_long": 0, "too_short_dur": 0, "too_long_dur": 0, "multi_line": 0}
subtitle_issues = []

for ass_path in sorted(base.rglob("*.ass")):
    name = ass_path.parent.name
    content = ass_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    dialogues = [l for l in lines if l.startswith("Dialogue:")]

    for d in dialogues:
        parts = d.split(",", 9)
        if len(parts) < 10:
            continue
        text = parts[9].strip()

        if "\\p1}" in text:
            continue

        text_clean = text
        while "{" in text_clean and "}" in text_clean:
            start = text_clean.index("{")
            end = text_clean.index("}") + 1
            text_clean = text_clean[:start] + text_clean[end:]

        subtitle_stats["total"] += 1

        char_count = len(text_clean.replace("\\N", "").replace("\\n", ""))
        if char_count > 18:
            subtitle_stats["too_long"] += 1
            if char_count <= 25:
                subtitle_issues.append(f"[minor] {name}: 单行{char_count}字>18: '{text_clean[:30]}'")

        start_parts = parts[1].split(":")
        end_parts = parts[2].split(":")
        try:
            start_s = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + float(start_parts[2])
            end_s = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + float(end_parts[2])
            dur = end_s - start_s
            if dur < 1.0:
                subtitle_stats["too_short_dur"] += 1
                subtitle_issues.append(f"[major] {name}: 显示时长{dur:.1f}s<1.0s: '{text_clean[:20]}'")
            if dur > 7.0:
                subtitle_stats["too_long_dur"] += 1
                subtitle_issues.append(f"[minor] {name}: 显示时长{dur:.1f}s>7.0s: '{text_clean[:20]}'")
        except (ValueError, IndexError):
            pass

        if "\\N" in parts[9] or "\\n" in parts[9]:
            subtitle_stats["multi_line"] += 1

for srt_path in sorted(base.rglob("*.srt")):
    name = srt_path.parent.name
    content = srt_path.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines_list = block.strip().split("\n")
        if len(lines_list) >= 3:
            text = " ".join(lines_list[2:])
            for wrong, right in custom_errata.items():
                if wrong in text:
                    subtitle_issues.append(f"[veto] {name}: 未勘误 '{wrong}'→'{right}': '{text[:50]}'")

veto_count = sum(1 for i in subtitle_issues if i.startswith("[veto]"))
major_count = sum(1 for i in subtitle_issues if i.startswith("[major]"))
minor_count = sum(1 for i in subtitle_issues if i.startswith("[minor]"))

print("=== 字幕统计 ===")
for k, v in subtitle_stats.items():
    print(f"  {k}: {v}")

print(f"\n=== 问题汇总 ===")
print(f"  veto: {veto_count}")
print(f"  major: {major_count}")
print(f"  minor: {minor_count}")

print(f"\n=== VETO项 (未勘误) ===")
veto_items = [i for i in subtitle_issues if i.startswith("[veto]")]
seen = set()
for v in veto_items:
    key = v.split(":")[1] if ":" in v else v
    if key not in seen:
        seen.add(key)
        print(f"  {v}")
    if len(seen) > 30:
        print(f"  ... 共{len(veto_items)}条veto")
        break

print(f"\n=== MAJOR项 ===")
major_items = [i for i in subtitle_issues if i.startswith("[major]")]
for m in major_items[:20]:
    print(f"  {m}")

with open("_audit_subtitles_v2.txt", "w", encoding="utf-8") as f:
    f.write(f"统计: {json.dumps(subtitle_stats, ensure_ascii=False)}\n")
    f.write(f"veto: {veto_count}, major: {major_count}, minor: {minor_count}\n\n")
    for issue in subtitle_issues:
        f.write(f"{issue}\n")
