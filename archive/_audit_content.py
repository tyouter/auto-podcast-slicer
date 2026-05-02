import json
from pathlib import Path

base = Path("output/short_videos_v2")

print("=== 传播质量审核 ===\n")

for meta_path in sorted(base.rglob("metadata.json")):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    name = meta["id"]
    dur = meta["duration_s"]
    series = meta.get("series", "")
    hook = meta.get("hook", "")
    title = meta.get("title", "")

    dur_ok = 15 <= dur <= 180
    dur_status = "OK" if dur_ok else f"OUT_OF_RANGE({dur}s)"

    hook_ok = bool(hook and len(hook) > 3)
    hook_status = "OK" if hook_ok else "MISSING"

    print(f"  {name} ({series}):")
    print(f"    时长: {dur}s => {dur_status}")
    print(f"    钩子: '{hook}' => {hook_status}")
    print(f"    标题: '{title}'")

print("\n=== 文化质量抽查 ===\n")

key_terms = {
    "博尔赫斯": "Borges",
    "小径分岔": "Forking Paths",
    "分岔": "forking/bifurcation",
    "平行时空": "parallel timelines",
    "可能性": "possibility",
    "不确定性": "uncertainty",
}

for ass_path in sorted(base.rglob("*.ass")):
    name = ass_path.parent.name
    content = ass_path.read_text(encoding="utf-8")
    dialogues = [l for l in content.split("\n") if l.startswith("Dialogue:") and "\\p1}" not in l]

    text_dialogues = []
    for d in dialogues:
        parts = d.split(",", 9)
        if len(parts) >= 10:
            t = parts[9]
            while "{" in t and "}" in t:
                s = t.index("{")
                e = t.index("}") + 1
                t = t[:s] + t[e:]
            text_dialogues.append(t.strip())

    full_text = " ".join(text_dialogues)

    found_terms = []
    for term, eng in key_terms.items():
        if term in full_text:
            found_terms.append(term)

    print(f"  {name}: 概念覆盖={found_terms}")

print("\n=== 文件完整性 ===\n")

required = ["_subtitled.mp4", "_vertical.mp4", ".ass", ".srt", ".wav", ".mp3", "metadata.json"]
missing_report = {}
for clip_dir in sorted(base.rglob("*/")):
    if not clip_dir.is_dir() or clip_dir == base:
        continue
    name = clip_dir.name
    if "_" not in name:
        continue
    missing = []
    for suffix in required:
        if suffix == "metadata.json":
            if not (clip_dir / suffix).exists():
                missing.append(suffix)
        else:
            if not list(clip_dir.glob(f"*{suffix}")):
                missing.append(suffix)
    if missing:
        missing_report[name] = missing

if missing_report:
    for name, miss in missing_report.items():
        print(f"  {name}: MISSING {miss}")
else:
    print("  ALL COMPLETE")

copyright_exists = (base / "COPYRIGHT.md").exists()
release_cards_exists = (base / "RELEASE_CARDS.json").exists()
summary_exists = (base / "summary.json").exists()

print(f"\n  COPYRIGHT.md: {'EXISTS' if copyright_exists else 'MISSING'}")
print(f"  RELEASE_CARDS.json: {'EXISTS' if release_cards_exists else 'MISSING'}")
print(f"  summary.json: {'EXISTS' if summary_exists else 'MISSING'}")
