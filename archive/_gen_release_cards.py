import json
from pathlib import Path

base = Path("output/short_videos_v2")
cards = []

for meta_path in sorted(base.rglob("metadata.json")):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    clip_dir = meta_path.parent
    clip_id = meta["id"]
    series = meta.get("series", "")
    title = meta.get("title", "")
    hook = meta.get("hook", "")
    dur = meta.get("duration_s", 0)

    sub_mp4 = clip_dir / f"{clip_id}_subtitled.mp4"
    vert_mp4 = clip_dir / f"{clip_id}_vertical.mp4"
    mp3_file = clip_dir / f"{clip_id}.mp3"

    card = {
        "id": clip_id,
        "series": series,
        "title": title,
        "hook": hook,
        "duration_s": dur,
        "files": {
            "horizontal_4k": str(sub_mp4.relative_to(base)) if sub_mp4.exists() else None,
            "vertical_1080x1920": str(vert_mp4.relative_to(base)) if vert_mp4.exists() else None,
            "audio_mp3": str(mp3_file.relative_to(base)) if mp3_file.exists() else None,
        },
        "platform_targets": [],
        "tags": [],
    }

    if series == "高光":
        card["platform_targets"] = ["抖音", "快手", "视频号", "YouTube Shorts"]
        card["tags"] = ["高光时刻", "金句", "短视频"]
    elif series == "哲思":
        card["platform_targets"] = ["B站", "YouTube", "小红书"]
        card["tags"] = ["深度思考", "哲学", "博尔赫斯"]
    elif series == "精彩对话":
        card["platform_targets"] = ["B站", "YouTube", "播客平台"]
        card["tags"] = ["对话", "访谈", "思想碰撞"]

    cards.append(card)

output_path = base / "RELEASE_CARDS.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print(f"Generated {len(cards)} release cards")
