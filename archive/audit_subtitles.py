import re
from pathlib import Path
from collections import defaultdict

from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.transcribe import parse_funasr_mixed_json
from pipeline.subtitle_merger import process_transcript_to_subtitles
from pipeline.subtitle_content import (
    process_subtitle_content,
    load_custom_errata,
    validate_subtitle_content,
    ERRATA_ASR_PHONETIC,
    SEMANTIC_ANOMALY_PATTERNS,
)

ctx = load_project()
config = ctx.config
entries = ctx.entries
merged = ctx.merged
transcript = ctx.transcript
custom_errata = ctx.custom_errata

processed = []
for i, entry in enumerate(entries):
    next_text = entries[i + 1].text if i + 1 < len(entries) else ""
    gap_s = (entries[i + 1].start_ms - entry.end_ms) / 1000.0 if i + 1 < len(entries) else 0
    is_last = (i == len(entries) - 1)
    processed_text = process_subtitle_content(
        text=entry.text,
        duration_s=entry.duration_s,
        next_text=next_text,
        gap_s=gap_s,
        max_chars=18,
        is_last=is_last,
        custom_errata=custom_errata,
        strip_punctuation=True,
    )
    processed.append({
        "index": i + 1,
        "text": processed_text,
        "start_ms": entry.start_ms,
        "end_ms": entry.end_ms,
    })

entry_dicts = [
    {"index": e["index"], "text": e["text"], "start_ms": e["start_ms"], "end_ms": e["end_ms"]}
    for e in processed
]

result = validate_subtitle_content(entry_dicts, max_chars=18, strip_punctuation=True)

print(f"总条数: {result.total_entries}")
print(f"准确率: {result.accuracy_rate:.4f}%")
print(f"通过: {result.passed}")
print(f"严重问题: {result.critical_count}")
print(f"警告: {result.warning_count}")
print(f"勘误错误: {result.errata_error_count}")

print("\n=== 严重问题 ===")
for issue in result.issues:
    if issue.severity == "critical":
        print(f"  [{issue.entry_index}] {issue.issue_type}: {issue.description}")
        print(f"    建议: {issue.suggestion}")

print("\n=== 潜在语义异常扫描 ===")
suspicious_patterns = [
    (r'话筒', '话筒可能是花园的误识别'),
    (r'武断', '武断可能是偶然的误识别'),
    (r'采戏', '采戏可能是排戏的误识别'),
    (r'上课(?!程)', '上课可能是上戏的误识别'),
    (r'系里面', '系可能是戏的误识别'),
    (r'消息(?!息)', '消息可能是小戏的误识别'),
    (r'目的(?!地|的)', '目的可能是母题的误识别'),
    (r'保证(?!明|书|人)', '保证可能是评估的误识别'),
    (r'缓缓的', '缓缓的可能是多余词'),
    (r'可能现(?!群|实|象|有|的|在|出|代|性)', '可能现可能是可能性的误识别'),
    (r'互联(?!网)', '互联可能是互联网的误识别'),
    (r'[^\u4e00-\u9fff]C\b', '说C可能是各种的误识别'),
    (r'VA', 'VA可能是A和B的误识别'),
    (r'传奇(?!还在)', '传奇可能是余传奇的误识别'),
]

all_text = " ".join(e["text"] for e in processed)
for pattern, desc in suspicious_patterns:
    matches = list(re.finditer(pattern, all_text))
    if matches:
        for m in matches:
            start = max(0, m.start() - 10)
            end = min(len(all_text), m.end() + 10)
            context = all_text[start:end]
            print(f"  [{desc}] 匹配: '{m.group()}' 上下文: ...{context}...")

print("\n=== 未被勘误表覆盖的疑似异常词 ===")
all_errata_keys = set(ERRATA_ASR_PHONETIC.keys())
all_texts = [e["text"] for e in processed]

common_misrecognitions = [
    '烫化', '烫话', '互联码', '互联马', '中联人', '五大文学院',
    '话言上', '话颜上', '样台', '扬台', '战方传', '作对我方编的',
    '中联人的事大爱好', '也可以这么心理', '送任', '于传奇',
    '质疑于打', '这期段', '差异的我想', '不冲着了节目',
    '弱手', '小庆', '边绪', '生灵里', '美食美课',
    '数字在', '支条', '其班是', '才系', '树理过',
    '而如慕然', '公布里', '写说的', '戏剧充座', '规例',
    '取动的', '玩播率', '非常理心', '曹早的', '新中大概',
    '抱志愿', '回上起来', '大微了', '奇异博士杨',
    '佛家奖的', '百千万一', '工程民旧', '好不犹豫',
    '松锐', '该躺的康', '细和了', '命理说了说',
    '小英文', '舒服自己的', '英文是我父亲', '总有他的',
    '签字对药', '太戏聊', '签一下医院的通知室',
    '签证据', '学我这次', '试我这次', '质疑于',
    '理心的', '砍的吧', '躺在的坑',
]

for word in common_misrecognitions:
    if word not in all_errata_keys:
        for t in all_texts:
            if word in t:
                idx = all_texts.index(t) + 1
                print(f"  未覆盖: '{word}' 出现在第{idx}条: {t}")
                break
