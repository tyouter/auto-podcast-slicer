import json
import subprocess
from pathlib import Path

base = Path("output/short_videos_v2")
report = {}

clip_dirs = sorted([d for d in base.iterdir() if d.is_dir() for d in d.iterdir() if d.is_dir()])
report["total_clips"] = len(clip_dirs)

required_files = {
    "subtitled": lambda d: f"{d.name}_subtitled.mp4",
    "vertical": lambda d: f"{d.name}_vertical.mp4",
    "ass": lambda d: f"{d.name}.ass",
    "srt": lambda d: f"{d.name}.srt",
    "wav": lambda d: f"{d.name}.wav",
    "mp3": lambda d: f"{d.name}.mp3",
    "metadata": lambda d: "metadata.json",
}

completeness = {}
for clip_dir in clip_dirs:
    name = clip_dir.name
    files = {}
    for key, fn in required_files.items():
        fpath = clip_dir / fn(clip_dir)
        files[key] = fpath.exists()
    missing = [k for k, v in files.items() if not v]
    completeness[name] = {"files": files, "missing": missing}

report["completeness"] = completeness

tech = {}
for clip_dir in clip_dirs:
    name = clip_dir.name
    info = {"video": {}, "audio": {}, "ass": {}}

    sub_mp4 = clip_dir / f"{name}_subtitled.mp4"
    vert_mp4 = clip_dir / f"{name}_vertical.mp4"

    for label, mp4 in [("subtitled", sub_mp4), ("vertical", vert_mp4)]:
        if not mp4.exists():
            info[label] = {"status": "MISSING"}
            continue
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,width,height,duration,nb_frames,bit_rate,sample_rate,channels,pix_fmt,r_frame_rate",
             "-show_entries", "format=bit_rate,duration",
             "-of", "json", str(mp4)],
            capture_output=True, text=True, encoding="utf-8",
        )
        data = json.loads(r.stdout)
        streams = {}
        fmt = data.get("format", {})
        for s in data.get("streams", []):
            streams[s.get("codec_type")] = s
        info[label] = {
            "video": streams.get("video", {}),
            "audio": streams.get("audio", {}),
            "format": fmt,
            "size_mb": round(mp4.stat().st_size / 1024 / 1024, 1),
        }

    ass_path = clip_dir / f"{name}.ass"
    if ass_path.exists():
        content = ass_path.read_text(encoding="utf-8")
        fontsize = None
        playres = None
        dialogue_count = 0
        for line in content.split("\n"):
            if "Fontsize" in line and "Style" in line:
                parts = line.split(",")
                for p in parts:
                    if p.strip().isdigit() and int(p.strip()) > 50:
                        fontsize = int(p.strip())
                        break
            if line.startswith("PlayResX:"):
                playres = line.split(":")[1].strip()
            if line.startswith("Dialogue:"):
                dialogue_count += 1
        info["ass"] = {"fontsize": fontsize, "playres": playres, "dialogue_count": dialogue_count}

    tech[name] = info

report["tech"] = tech

with open("_audit_raw.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2, default=str)

print(f"Total clips: {report['total_clips']}")
for name, comp in completeness.items():
    if comp["missing"]:
        print(f"  {name}: MISSING {comp['missing']}")
    else:
        print(f"  {name}: COMPLETE")

print("\n--- Video Resolution Summary ---")
for name, t in tech.items():
    for label in ["subtitled", "vertical"]:
        v = t.get(label, {}).get("video", {})
        w = v.get("width")
        h = v.get("height")
        dur = v.get("duration")
        codec = v.get("codec_name")
        pix = v.get("pix_fmt")
        fps = v.get("r_frame_rate")
        sz = t.get(label, {}).get("size_mb")
        if w:
            print(f"  {name} {label}: {w}x{h} {codec} {pix} dur={dur}s fps={fps} size={sz}MB")

print("\n--- Audio Summary ---")
for name, t in tech.items():
    for label in ["subtitled", "vertical"]:
        a = t.get(label, {}).get("audio", {})
        codec = a.get("codec_name")
        sr = a.get("sample_rate")
        ch = a.get("channels")
        if codec:
            print(f"  {name} {label}: {codec} {sr}Hz {ch}ch")

print("\n--- ASS Summary ---")
for name, t in tech.items():
    ass = t.get("ass", {})
    if ass:
        print(f"  {name}: fontsize={ass.get('fontsize')} playres={ass.get('playres')} dialogues={ass.get('dialogue_count')}")

print("\nDONE")
