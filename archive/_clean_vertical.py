from pathlib import Path

base = Path("output/short_videos_v2")
removed = 0
for f in base.rglob("*_vertical.mp4"):
    f.unlink()
    removed += 1
print(f"Removed {removed} vertical videos")
