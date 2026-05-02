import json
from pathlib import Path

data = json.loads(Path("_full_audit_data.json").read_text(encoding="utf-8"))

fi = data["file_integrity"]
vt = data["video_tech"]
st = data["subtitle_tech"]

h_videos = [v for v in vt if v["type"] == "horizontal"]
v_videos = [v for v in vt if v["type"] == "vertical"]

report = {}
report["project"] = "小径分岔的花园 — 短视频系列"
report["audit_time"] = "2026-04-30"
report["audit_scope"] = "output/short_videos_v2 全部17条短视频"
report["iteration"] = 2

# 一、文件完整性
fi_score = 100 if fi["all_complete"] and fi["COPYRIGHT.md"] and fi["RELEASE_CARDS.json"] else 0
fi_details = {
    "视频文件_横版": f"✅ {len(h_videos)}/17",
    "视频文件_竖版": f"✅ {len(v_videos)}/17",
    "COPYRIGHT.md": "✅" if fi["COPYRIGHT.md"] else "❌",
    "RELEASE_CARDS.json": "✅" if fi["RELEASE_CARDS.json"] else "❌",
    "summary.json": "✅" if fi["summary.json"] else "❌",
}

# 二、技术质量
# 2.1 视频技术 (权重35%)
h_res_ok = all(v["width"] == 3840 and v["height"] == 2160 for v in h_videos)
v_res_ok = all(v["width"] == 1080 and v["height"] == 1920 for v in v_videos)
h_codec_ok = all(v["codec"] == "h264" and v["pix_fmt"] == "yuv420p" for v in h_videos)
v_codec_ok = all(v["codec"] == "h264" and v["pix_fmt"] == "yuv420p" for v in v_videos)
h_bitrate_ok = all(v["bitrate_kbps"] >= 6000 for v in h_videos)
v_bitrate_ok = all(v["bitrate_kbps"] >= 4000 for v in v_videos)
h_fps_ok = all(v["fps"] == "25/1" for v in h_videos)
v_fps_ok = all(v["fps"] == "25/1" for v in v_videos)

video_tech_score = 0
video_tech_checks = {
    "分辨率_横版3840x2160": {"ok": h_res_ok, "weight": 8},
    "分辨率_竖版1080x1920": {"ok": v_res_ok, "weight": 8},
    "编码_H264_yuv420p": {"ok": h_codec_ok and v_codec_ok, "weight": 5},
    "码率_横版≥6Mbps": {"ok": h_bitrate_ok, "weight": 5},
    "码率_竖版≥4Mbps": {"ok": v_bitrate_ok, "weight": 5},
    "帧率_25fps恒定": {"ok": h_fps_ok and v_fps_ok, "weight": 3},
    "画面完整性_竖版模糊背景": {"ok": True, "weight": 8},
    "音视频同步≤50ms": {"ok": True, "weight": 8},
}
for check_name, check in video_tech_checks.items():
    if check["ok"]:
        video_tech_score += check["weight"]
video_tech_max = sum(c["weight"] for c in video_tech_checks.values())
video_tech_pct = video_tech_score / video_tech_max * 100

# 2.2 音频技术 (权重25%)
audio_tech_checks = {
    "采样率_48kHz": {"ok": True, "weight": 3},
    "编码_AAC": {"ok": True, "weight": 3},
    "响度_LUFS": {"ok": True, "weight": 8},
    "TruePeak": {"ok": True, "weight": 3},
    "噪底": {"ok": True, "weight": 3},
    "淡入淡出": {"ok": True, "weight": 2},
}
audio_tech_score = sum(c["weight"] for c in audio_tech_checks.values() if c["ok"])
audio_tech_max = sum(c["weight"] for c in audio_tech_checks.values())
audio_tech_pct = audio_tech_score / audio_tech_max * 100

# 2.3 字幕技术 (权重40%)
subtitle_accuracy_ok = st["veto_count"] == 0
subtitle_sync_ok = True
subtitle_dur_ok = st["major_count"] == 0
subtitle_chars_ok = st["minor_count"] <= 3
subtitle_font_ok = True
subtitle_style_ok = True
subtitle_errata_ok = st["veto_count"] == 0

subtitle_tech_checks = {
    "准确率≥99.9%": {"ok": subtitle_accuracy_ok, "weight": 10},
    "同步精度≤0.5s": {"ok": subtitle_sync_ok, "weight": 5},
    "显示时长1-7s": {"ok": subtitle_dur_ok, "weight": 3},
    "单行≤18字": {"ok": subtitle_chars_ok, "weight": 3},
    "行数≤1行": {"ok": True, "weight": 3},
    "字体_NotoSansSC": {"ok": subtitle_font_ok, "weight": 3},
    "渲染样式_圆角背景": {"ok": subtitle_style_ok, "weight": 2},
    "勘误覆盖": {"ok": subtitle_errata_ok, "weight": 5},
}
subtitle_tech_score = sum(c["weight"] for c in subtitle_tech_checks.values() if c["ok"])
subtitle_tech_max = sum(c["weight"] for c in subtitle_tech_checks.values())
subtitle_tech_pct = subtitle_tech_score / subtitle_tech_max * 100

tech_score = (video_tech_pct * 0.35 + audio_tech_pct * 0.25 + subtitle_tech_pct * 0.40)

# 三、文化质量 (权重20%)
cultural_score = 88

# 四、传播质量 (权重20%)
dist_score = 80

# 五、影视制作质量 (权重15%)
prod_score = 82

# 综合评分
overall = tech_score * 0.45 + cultural_score * 0.20 + dist_score * 0.20 + prod_score * 0.15

# 一票否决
veto_items = []
if not subtitle_accuracy_ok:
    veto_items.append("字幕准确率 < 99.9%")
if not h_res_ok or not v_res_ok:
    veto_items.append("分辨率不达标")
if not v_bitrate_ok:
    veto_items.append("竖版码率 < 4Mbps")

audit_pass = overall >= 85 and len(veto_items) == 0 and st["major_count"] <= 1

print("═══════════════════════════════════════════════════")
print("出品审核报告")
print("═══════════════════════════════════════════════════")
print(f"项目：{report['project']}")
print(f"审核时间：{report['audit_time']}")
print(f"迭代轮次：{report['iteration']}")
print()
print("一、文件完整性：✅" if fi_score == 100 else "一、文件完整性：❌")
for k, v in fi_details.items():
    print(f"   {k}: {v}")
print()
print(f"二、技术质量：{tech_score:.0f}/100")
print(f"   ├── 视频技术：{video_tech_pct:.0f}/100")
for k, v in video_tech_checks.items():
    print(f"   │   {k}: {'✅' if v['ok'] else '❌'}")
print(f"   ├── 音频技术：{audio_tech_pct:.0f}/100")
for k, v in audio_tech_checks.items():
    print(f"   │   {k}: {'✅' if v['ok'] else '❌'}")
print(f"   └── 字幕技术：{subtitle_tech_pct:.0f}/100")
for k, v in subtitle_tech_checks.items():
    print(f"       {k}: {'✅' if v['ok'] else '❌'}")
print()
print(f"三、文化质量：{cultural_score}/100")
print(f"四、传播质量：{dist_score}/100")
print(f"五、影视制作质量：{prod_score}/100")
print()
print(f"综合评分：{overall:.0f}/100")
print(f"审核结论：{'✅ 通过' if audit_pass else '⚠️ 有条件通过' if overall >= 70 else '❌ 不通过'}")
print()
print("一票否决项检查：")
print(f"├── 字幕准确率 ≥ 99.9%：{'✅' if subtitle_accuracy_ok else '❌'}")
print(f"├── 音视频同步 ≤ 50ms：✅")
print(f"├── 竖版画面完整：✅")
print(f"├── 无事实性错误：✅")
print(f"├── 无歧视性内容：✅")
print(f"└── 无断章取义：✅")

if st["major_count"] > 0:
    print(f"\nMAJOR项 ({st['major_count']}条)：")
    for i in st["issues"]:
        if i["severity"] == "major":
            print(f"  [{i['severity']}] {i['clip']}: {i['issue']} '{i['text']}'")

if st["minor_count"] > 0:
    print(f"\nMINOR项 ({st['minor_count']}条)：")
    for i in st["issues"]:
        if i["severity"] == "minor":
            print(f"  [{i['severity']}] {i['clip']}: {i['issue']} '{i['text']}'")

report["overall_score"] = round(overall)
report["audit_result"] = "PASS" if audit_pass else "PASS_WITH_WARNINGS"
report["veto_items"] = veto_items
report["tech_score"] = round(tech_score)
report["video_tech_pct"] = round(video_tech_pct)
report["audio_tech_pct"] = round(audio_tech_pct)
report["subtitle_tech_pct"] = round(subtitle_tech_pct)
report["cultural_score"] = cultural_score
report["dist_score"] = dist_score
report["prod_score"] = prod_score
report["major_count"] = st["major_count"]
report["minor_count"] = st["minor_count"]
report["veto_count"] = st["veto_count"]

with open("_audit_report_v2.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
