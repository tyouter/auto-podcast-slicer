import re


LINE_START_FORBIDDEN = '的了着过吗呢吧啊呀哇嘛呗的啦咯嗯噢哦哈'

LINE_END_FORBIDDEN = '不没很更最就才又再还却倒并而或'

QUESTION_INDICATORS = [
    '吗', '呢', '吧', '什么', '怎么', '为什么', '哪里', '谁',
    '多少', '几', '是否', '难道', '究竟', '到底', '如何',
]

EXCLAMATION_INDICATORS = [
    '太', '好', '真', '特别', '非常', '极其', '超级', '真的',
    '啊', '呀', '哇', '哎',
]

CONNECTIVE_WORDS = [
    '但是', '不过', '可是', '其实', '然后', '所以', '而且', '就是',
    '因为', '如果', '虽然', '因此', '或者', '同时', '另外', '那么',
    '对', '嗯', '啊', '是', '不是', '那个', '这个', '而且',
    '所以说', '也就是说', '换句话说', '总而言之',
]

PAUSE_PUNCTUATION = {
    '，': 0.3, '。': 0.6, '！': 0.5, '？': 0.5,
    '；': 0.4, '、': 0.2, '：': 0.3,
}


def add_punctuation_smart(
    text: str,
    next_text: str = '',
    duration_s: float = 0,
    gap_s: float = 0,
    is_last: bool = False,
) -> str:
    text = text.strip()
    if not text:
        return text

    if re.search(r'[。！？；：，、,.!?;:]$', text):
        return text

    if any(text.endswith(q) for q in QUESTION_INDICATORS):
        return text + '？'

    if any(text.endswith(e) for e in EXCLAMATION_INDICATORS):
        if text.endswith('啊') or text.endswith('呀') or text.endswith('哇'):
            return text + '！'
        return text + '！'

    if is_last or gap_s > 2.5:
        return text + '。'

    if gap_s > 1.5:
        return text + '。'

    if next_text:
        for cw in CONNECTIVE_WORDS:
            if next_text.startswith(cw):
                if cw in ('但是', '不过', '可是', '虽然', '如果', '虽然'):
                    return text + '，'
                elif cw in ('所以', '因此', '那么'):
                    return text + '，'
                elif cw in ('对', '嗯', '啊', '是', '不是'):
                    return text + '，'
                elif cw in ('而且', '同时', '另外', '或者'):
                    return text + '，'
                break

    if duration_s > 4.0:
        return text + '。'
    elif duration_s > 2.0:
        return text + '，'

    return text + '，'


def clean_subtitle_text(text: str) -> str:
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'^[，。！？、；：]+', '', text)
    text = re.sub(r'[，]{2,}', '，', text)
    text = re.sub(r'[。]{2,}', '。', text)
    text = text.strip()
    return text


def enforce_single_line(text: str) -> str:
    return text.replace('\n', '')


def format_subtitle_single_line(text: str, max_chars: int = 18) -> str:
    text = enforce_single_line(text)
    text = clean_subtitle_text(text)
    if len(text) <= max_chars:
        return text
    break_points = list(re.finditer(r'[，。！？、；：]', text[:max_chars + 3]))
    if break_points:
        pos = break_points[-1].end()
        if pos <= max_chars:
            return text[:pos]
    return text[:max_chars]


def check_line_start_rules(text: str) -> list[str]:
    violations = []
    if text and text[0] in LINE_START_FORBIDDEN:
        violations.append(f"行首禁则违规：'{text[0]}'不应出现在行首")
    return violations


def check_line_end_rules(text: str) -> list[str]:
    violations = []
    if text and text[-1] in LINE_END_FORBIDDEN:
        violations.append(f"行末禁则违规：'{text[-1]}'不应出现在行末")
    return violations


def detect_meaningless_words(text: str) -> list[str]:
    meaningless = []
    filler_patterns = [
        r'那个那个', r'这个这个', r'然后然后', r'就是就是',
        r'嗯嗯嗯+', r'啊啊啊+', r'呃呃呃+',
    ]
    for pattern in filler_patterns:
        matches = re.findall(pattern, text)
        meaningless.extend(matches)
    return meaningless


def detect_context_anomalies(text: str, check_punctuation: bool = True) -> list[str]:
    anomalies = []
    if re.search(r'[a-zA-Z]{3,}', text):
        en_words = re.findall(r'[a-zA-Z]{3,}', text)
        common_en = {'the', 'and', 'for', 'not', 'but', 'all', 'can', 'her',
                     'him', 'one', 'our', 'out', 'has', 'have', 'had', 'was',
                     'are', 'been', 'from', 'this', 'that', 'with', 'they',
                     'will', 'what', 'when', 'who', 'how', 'why', 'did', 'get', 'got'}
        for w in en_words:
            if w.lower() not in common_en:
                anomalies.append(f"疑似ASR误识别英文: '{w}'")

    if check_punctuation and re.search(r'[\u4e00-\u9fff]{8,}', text) and not re.search(r'[，。！？、；：]', text):
        anomalies.append("长文本无标点断句，可能为ASR连续输出未断句")

    return anomalies


def remove_display_punctuation(text: str) -> str:
    punctuation = set('，。！？；：、""''（）【】《》—…·,.\'\"!?;:()[]{}<>-–—…·')
    return ''.join(ch for ch in text if ch not in punctuation)
