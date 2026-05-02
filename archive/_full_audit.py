import json
import subprocess
from pathlib import Path
from pipeline.loader import load_project

ctx = load_project()
custom_errata = ctx.custom_errata
base = Path("output/short_videos_v2")

audit_data = {
    "file_integrity": {},
    "video_tech": [],
    "audio_tech": [],
    "subtitle_tech": {},
    "cultural": {},
    "distribution": {},
    "production": {},
}

required_files = ["_subtitled.mp4", "_vertical.mp4", ".ass", ".srt", ".wav", ".mp3", "metadata.json"]
missing_all = []
for clip_dir in sorted(base.rglob("*/")):
    if not clip_dir.is_dir() or clip_dir == base:
        continue
    name = clip_dir.name
    if "_" not in name:
        continue
    missing = []
    for suffix in required_files:
        if suffix == "metadata.json":
            if not (clip_dir / suffix).exists():
                missing.append(suffix)
        else:
            if not list(clip_dir.glob(f"*{suffix}")):
                missing.append(suffix)
    if missing:
        missing_all.append({"clip": name, "missing": missing})

audit_data["file_integrity"] = {
    "COPYRIGHT.md": (base / "COPYRIGHT.md").exists(),
    "RELEASE_CARDS.json": (base / "RELEASE_CARDS.json").exists(),
    "summary.json": (base / "summary.json").exists(),
    "missing_files": missing_all,
    "all_complete": len(missing_all) == 0,
}

for mp4 in sorted(base.rglob("*_subtitled.mp4")):
    name = mp4.parent.name
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration,bit_rate,r_frame_rate,pix_fmt,sample_rate,channels",
         "-show_entries", "format=bit_rate,duration",
         "-of", "json", str(mp4)],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(r.stdout)
    streams = {}
    fmt = data.get("format", {})
    for s in data.get("streams", []):
        streams[s.get("codec_type")] = s
    v = streams.get("video", {})
    a = streams.get("audio", {})
    audit_data["video_tech"].append({
        "name": name,
        "type": "horizontal",
        "width": v.get("width"),
        "height": v.get("height"),
        "codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "fps": v.get("r_frame_rate"),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0)) / 1000),
        "duration_s": float(fmt.get("duration", 0)),
        "audio_codec": a.get("codec_name"),
        "audio_sample_rate": a.get("sample_rate"),
        "audio_channels": a.get("channels"),
    })

for mp4 in sorted(base.rglob("*_vertical.mp4")):
    name = mp4.parent.name
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration,bit_rate,r_frame_rate,pix_fmt,sample_rate,channels",
         "-show_entries", "format=bit_rate,duration",
         "-of", "json", str(mp4)],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(r.stdout)
    streams = {}
    fmt = data.get("format", {})
    for s in data.get("streams", []):
        streams[s.get("codec_type")] = s
    v = streams.get("video", {})
    a = streams.get("audio", {})
    audit_data["video_tech"].append({
        "name": name,
        "type": "vertical",
        "width": v.get("width"),
        "height": v.get("height"),
        "codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"),
        "fps": v.get("r_frame_rate"),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0)) / 1000),
        "duration_s": float(fmt.get("duration", 0)),
        "audio_codec": a.get("codec_name"),
        "audio_sample_rate": a.get("sample_rate"),
        "audio_channels": a.get("channels"),
    })

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
            subtitle_issues.append({"severity": "minor", "clip": name, "issue": f"单行{char_count}字>18", "text": text_clean[:30]})
        start_parts = parts[1].split(":")
        end_parts = parts[2].split(":")
        try:
            start_s = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + float(start_parts[2])
            end_s = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + float(end_parts[2])
            dur = end_s - start_s
            if dur < 1.0:
                subtitle_stats["too_short_dur"] += 1
                subtitle_issues.append({"severity": "major", "clip": name, "issue": f"显示时长{dur:.1f}s<1.0s", "text": text_clean[:20]})
            if dur > 7.0:
                subtitle_stats["too_long_dur"] += 1
                subtitle_issues.append({"severity": "minor", "clip": name, "issue": f"显示时长{dur:.1f}s>7.0s", "text": text_clean[:20]})
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
                    subtitle_issues.append({"severity": "veto", "clip": name, "issue": f"未勘误 '{wrong}'→'{right}'", "text": text[:50]})

audit_data["subtitle_tech"] = {
    "stats": subtitle_stats,
    "issues": subtitle_issues,
    "veto_count": sum(1 for i in subtitle_issues if i["severity"] == "veto"),
    "major_count": sum(1 for i in subtitle_issues if i["severity"] == "major"),
    "minor_count": sum(1 for i in subtitle_issues if i["severity"] == "minor"),
}

with open("_full_audit_data.json", "w", encoding="utf-8") as f:
    json.dump(audit_data, f, ensure_ascii=False, indent=2)

print("=== 文件完整性 ===")
print(f"  全部文件: {'✅' if audit_data['file_integrity']['all_complete'] else '❌'}")
print(f"  COPYRIGHT.md: {'✅' if audit_data['file_integrity']['COPYRIGHT.md'] else '❌'}")
print(f"  RELEASE_CARDS: {'✅' if audit_data['file_integrity']['RELEASE_CARDS.json'] else '❌'}")

print("\n=== 视频技术 ===")
h_ok = sum(1 for v in audit_data["video_tech"] if v["type"] == "horizontal" and v["width"] == 3840 and v["bitrate_kbps"] >= 6000)
h_total = sum(1 for v in audit_data["video_tech"] if v["type"] == "horizontal")
v_ok = sum(1 for v in audit_data["video_tech"] if v["type"] == "vertical" and v["width"] == 1080 and v["bitrate_kbps"] >= 4000)
v_total = sum(1 for v in audit_data["video_tech"] if v["type"] == "vertical")
print(f"  横版4K码率≥6Mbps: {h_ok}/{h_total}")
print(f"  竖版码率≥4Mbps: {v_ok}/{v_total}")

low_v = [v for v in audit_data["video_tech"] if v["type"] == "vertical" and v["bitrate_kbps"] < 4000]
if low_v:
    print("  码率不足竖版:")
    for v in low_v:
        print(f"    {v['name']}: {v['bitrate_kbps']}kbps")

print("\n=== 字幕技术 ===")
st = audit_data["subtitle_tech"]
print(f"  总条数: {st['stats']['total']}")
print(f"  veto: {st['veto_count']}")
print(f"  major: {st['major_count']}")
print(f"  minor: {st['minor_count']}")
