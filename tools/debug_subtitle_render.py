import subprocess
from pathlib import Path
from PIL import Image
import numpy as np

video_source = Path("D:/boke/garden post factory/C0257.MP4")

# Reference: no subtitle
frame_nosub = Path("output/frame_nosub.png")
arr_nosub = np.array(Image.open(frame_nosub))
h, w = arr_nosub.shape[:2]

# Test 1: Simple SRT with English text (known working)
srt_simple = Path("output/simple.srt")
srt_simple.write_text("1\n00:00:01,000 --> 00:00:05,000\nTEST SUBTITLE\n", encoding="utf-8")
srt_esc1 = str(srt_simple).replace("\\", "/").replace(":", "\\:")

# Test 2: Simple SRT with Chinese text
srt_cn = Path("output/simple_cn.srt")
srt_cn.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕可见性\n", encoding="utf-8")
srt_esc2 = str(srt_cn).replace("\\", "/").replace(":", "\\:")

# Test 3: Actual SRT file from the clip
srt_actual = Path("output/clips_time_bifurcation/time_03_time_and_possibility/time_03_time_and_possibility.srt")
srt_esc3 = str(srt_actual).replace("\\", "/").replace(":", "\\:")

# Test 4: Copy actual SRT to simple path
srt_copy = Path("output/actual_copy.srt")
srt_copy.write_text(srt_actual.read_text(encoding="utf-8"), encoding="utf-8")
srt_esc4 = str(srt_copy).replace("\\", "/").replace(":", "\\:")

tests = [
    ("simple_english", srt_esc1),
    ("simple_chinese", srt_esc2),
    ("actual_path", srt_esc3),
    ("actual_copy", srt_esc4),
]

for name, srt_esc in tests:
    output = Path(f"output/test_{name}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-ss", "1860", "-to", "1865",
        "-i", str(video_source),
        "-vf", f"subtitles='{srt_esc}'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-an",
        str(output)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    if r.returncode != 0:
        print(f"{name}: FAIL")
        for line in r.stderr.split("\n"):
            if any(kw in line.lower() for kw in ["error", "subtitle", "cannot"]):
                print(f"  {line}")
        continue
    
    frame_path = Path(f"output/frame_{name}.png")
    subprocess.run(["ffmpeg", "-y", "-i", str(output), "-ss", "2", "-frames:v", "1", str(frame_path)], capture_output=True)
    
    arr = np.array(Image.open(frame_path))
    diff = np.abs(arr.astype(int) - arr_nosub.astype(int))
    
    sub_area = diff[int(h*0.85):h, int(w*0.2):int(w*0.8), :]
    total = sub_area.shape[0] * sub_area.shape[1] * 3
    sig = np.sum(sub_area > 30)
    
    print(f"{name}: diff={sig/total*100:.2f}% size={output.stat().st_size/1024/1024:.1f}MB")
