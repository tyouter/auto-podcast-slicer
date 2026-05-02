import json
import subprocess
from pathlib import Path

base = Path("output/short_videos_v2")
results = []

for mp4 in sorted(base.rglob("*_subtitled.mp4")):
    name = mp4.parent.name
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration,bit_rate,r_frame_rate,pix_fmt",
         "-show_entries", "format=bit_rate,duration,size",
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

    v_dur = float(v.get("duration", 0))
    a_dur = float(a.get("duration", 0))
    fmt_dur = float(fmt.get("duration", 0))
    sync_diff = abs(v_dur - a_dur) * 1000

    format_bitrate = int(fmt.get("bit_rate", 0)) / 1000
    size_mb = int(fmt.get("size", 0)) / 1024 / 1024

    w = v.get("width")
    h = v.get("height")
    fps = v.get("r_frame_rate")
    pix = v.get("pix_fmt")

    min_bitrate = 6000 if w == 3840 else 6000
    bitrate_ok = format_bitrate >= min_bitrate

    results.append({
        "name": name,
        "resolution": f"{w}x{h}",
        "fps": fps,
        "pix_fmt": pix,
        "v_dur": v_dur,
        "a_dur": a_dur,
        "sync_diff_ms": round(sync_diff, 1),
        "bitrate_kbps": round(format_bitrate),
        "size_mb": round(size_mb, 1),
        "bitrate_ok": bitrate_ok,
    })

for mp4 in sorted(base.rglob("*_vertical.mp4")):
    name = mp4.parent.name + "_V"
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration,bit_rate,r_frame_rate,pix_fmt",
         "-show_entries", "format=bit_rate,duration,size",
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

    v_dur = float(v.get("duration", 0))
    a_dur = float(a.get("duration", 0))
    sync_diff = abs(v_dur - a_dur) * 1000

    format_bitrate = int(fmt.get("bit_rate", 0)) / 1000
    size_mb = int(fmt.get("size", 0)) / 1024 / 1024

    w = v.get("width")
    h = v.get("height")

    results.append({
        "name": name,
        "resolution": f"{w}x{h}",
        "v_dur": v_dur,
        "a_dur": a_dur,
        "sync_diff_ms": round(sync_diff, 1),
        "bitrate_kbps": round(format_bitrate),
        "size_mb": round(size_mb, 1),
        "bitrate_ok": format_bitrate >= 4000,
    })

print("=== 横版视频码率 ===")
for r in results:
    if "_V" not in r["name"]:
        status = "OK" if r["bitrate_ok"] else "LOW"
        print(f"  {r['name']}: {r['resolution']} {r['bitrate_kbps']}kbps {r['size_mb']}MB sync={r['sync_diff_ms']}ms => {status}")

print("\n=== 竖版视频码率 ===")
for r in results:
    if "_V" in r["name"]:
        status = "OK" if r["bitrate_ok"] else "LOW"
        print(f"  {r['name']}: {r['resolution']} {r['bitrate_kbps']}kbps {r['size_mb']}MB sync={r['sync_diff_ms']}ms => {status}")

sync_issues = [r for r in results if r["sync_diff_ms"] > 50]
bitrate_issues = [r for r in results if not r["bitrate_ok"]]

print(f"\n=== 同步问题 (>50ms) ===")
for r in sync_issues:
    print(f"  {r['name']}: {r['sync_diff_ms']}ms")

print(f"\n=== 码率不足 ===")
for r in bitrate_issues:
    print(f"  {r['name']}: {r['bitrate_kbps']}kbps")

with open("_audit_tech.txt", "w", encoding="utf-8") as f:
    for r in results:
        f.write(f"{json.dumps(r, ensure_ascii=False)}\n")
