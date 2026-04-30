from pathlib import Path
import subprocess
from PIL import Image
import numpy as np
from pipeline.subtitle_content import load_custom_errata

videos = [
    ("time_03", "output/clips_time_bifurcation/time_03_time_and_possibility/time_03_time_and_possibility_subtitled.mp4"),
    ("fencha_01", "output/clips_fencha/clip01_literature/clip01_literature_subtitled.mp4"),
]

for name, vpath in videos:
    video = Path(vpath)
    frame = Path(f"output/verify_fg_{name}.png")
    subprocess.run(["ffmpeg", "-y", "-ss", "10", "-i", str(video), "-frames:v", "1", str(frame)], capture_output=True)
    img = np.array(Image.open(frame))
    h, w = img.shape[:2]

    sub = img[int(h*0.85):int(h*0.95), int(w*0.2):int(w*0.8), :]
    gray = sub.mean(axis=2)
    white = np.sum(gray > 200) / gray.size * 100
    dark_bg = np.sum((gray > 30) & (gray < 100)) / gray.size * 100

    top_area = img[int(h*0.3):int(h*0.4), int(w*0.2):int(w*0.8), :]
    bottom_area = img[int(h*0.85):int(h*0.95), int(w*0.2):int(w*0.8), :]
    top_var = top_area.var()
    bottom_var = bottom_area.var()

    print(f"{name}: white={white:.1f}% dark_bg={dark_bg:.1f}% top_var={top_var:.0f} bottom_var={bottom_var:.0f} blur_ratio={top_var/bottom_var:.1f}x")

errata = load_custom_errata(Path("config/corrections.yaml"))
print(f"\nErrata count: {len(errata)}")
print(f"宋锐 errata: 宋瑞 in errata = {'宋瑞' in errata} -> {errata.get('宋瑞', 'N/A')}")
print(f"余传奇 errata: 于传奇 in errata = {'于传奇' in errata} -> {errata.get('于传奇', 'N/A')}")

import re
ass_path = Path("output/clips_time_bifurcation/time_03_time_and_possibility/time_03_time_and_possibility.ass")
with open(ass_path, "r", encoding="utf-8") as f:
    content = f.read()
dialogue_lines = [l for l in content.split("\n") if l.startswith("Dialogue")]
punct_found = False
for line in dialogue_lines[:10]:
    text = line.split(",,")[-1] if ",," in line else ""
    text = re.sub(r"\{[^}]*\}", "", text)
    if any(c in text for c in "，。！？、；："):
        punct_found = True
        print(f"  PUNCT: {text}")
if not punct_found:
    print("No punctuation in subtitle text - PASS")
print(f"BorderStyle=3: {'3,20' in content}")

# Efficiency check
summary1 = Path("output/clips_time_bifurcation/summary.json")
summary2 = Path("output/clips_fencha/summary.json")
import json
with open(summary1, encoding="utf-8") as f:
    s1 = json.load(f)
with open(summary2, encoding="utf-8") as f:
    s2 = json.load(f)
print(f"\nEfficiency:")
print(f"  Time bifurcation: {s1.get('generated_count', 'N/A')} generated, {s1.get('skipped_count', 'N/A')} skipped, {s1.get('total_time_s', 'N/A')}s")
print(f"  Fencha: {s2.get('generated_count', 'N/A')} generated, {s2.get('skipped_count', 'N/A')} skipped, {s2.get('total_time_s', 'N/A')}s")
