import subprocess
from pathlib import Path

srt_path = Path("output/clips_fencha/clip01_literature/clip01_literature.srt")
srt_path_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

force_style = (
    "FontName=Noto Sans SC,"
    "FontSize=18,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&H99000000,"
    "Outline=0,"
    "Shadow=0,"
    "BorderStyle=3,"
    "Alignment=2,"
    "MarginV=55"
)

cmd = [
    "ffmpeg", "-y",
    "-i", "D:/boke/garden post factory/C0257.MP4",
    "-ss", "640", "-to", "642",
    "-vf", f"subtitles='{srt_path_escaped}':force_style='{force_style}'",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k",
    "output/test_sub.mp4"
]

result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
print("RC:", result.returncode)
if result.returncode != 0:
    print("STDERR:", result.stderr[-800:])
else:
    print("OK:", Path("output/test_sub.mp4").stat().st_size)
