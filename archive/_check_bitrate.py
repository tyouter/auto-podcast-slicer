import json
import subprocess
from pathlib import Path

base = Path("output/short_videos_v2")
results = []

for mp4 in sorted(base.rglob("*_vertical.mp4")):
    name = mp4.parent.name
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,duration,bit_rate",
         "-show_entries", "format=bit_rate,duration",
         "-of", "json", str(mp4)],
        capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(r.stdout)
    fmt = data.get("format", {})
    bitrate = int(fmt.get("bit_rate", 0)) / 1000
    ok = bitrate >= 4000
    results.append(f"{name}: {bitrate:.0f}kbps => {'OK' if ok else 'LOW'}")

with open("_vertical_bitrate.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
for r in results:
    print(r)
