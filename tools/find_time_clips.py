import sys
sys.path.insert(0, ".")
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_content import traditional_to_simplified
from pathlib import Path

transcript = parse_funasr_mixed_json(Path("D:/boke/garden post factory/C0257_full_mixed.json"))

keywords = ["时间", "分岔", "平行", "时空", "同时", "可能性", "选择", "命运", "节点",
            "博尔赫斯", "花园", "路径", "不确定", "多重", "维度", "量子",
            "过去", "未来", "现在", "历史", "线性", "非线性", "轨道"]

hits = []
for seg in transcript.segments:
    text_simplified = traditional_to_simplified(seg.text)
    score = sum(1 for kw in keywords if kw in text_simplified)
    if score >= 2:
        hits.append((seg.start_ms / 60000, score, text_simplified[:80]))

print("=== 时间分岔高相关片段 (score>=2) ===\n")
for m, s, t in sorted(hits, key=lambda x: -x[1])[:40]:
    print(f"  {m:6.1f}min [score={s}] {t}")

print(f"\n总计: {len(hits)} 个片段\n")

print("\n=== 按5分钟时间段聚类 ===\n")

time_buckets = {}
for m, s, t in hits:
    bucket = int(m / 5) * 5
    if bucket not in time_buckets:
        time_buckets[bucket] = {"count": 0, "score": 0, "samples": []}
    time_buckets[bucket]["count"] += 1
    time_buckets[bucket]["score"] += s
    time_buckets[bucket]["samples"].append(t)

for bucket in sorted(time_buckets.keys()):
    info = time_buckets[bucket]
    print(f"  [{bucket:3d}-{bucket+5:3d}]min: {info['count']:2d} hits, score={info['score']:2d}")
    for t in info["samples"][:2]:
        print(f"    \"{t}\"")
    print()
