import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WordIssue:
    word: str
    position: int
    issue_type: str
    severity: str
    description: str
    suggestion: str = ""
    confidence: float = 0.0


@dataclass
class WordVerificationResult:
    total_words: int = 0
    issues: list[WordIssue] = field(default_factory=list)
    score: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


WORD_DICT: set[str] = set()
WORD_DICT_LOADED = False


def _load_word_dict():
    global WORD_DICT, WORD_DICT_LOADED
    if WORD_DICT_LOADED:
        return
    WORD_DICT_LOADED = True

    from pipeline.subtitle_content import (
        ERRATA_AUTHORS, ERRATA_WORKS, ERRATA_IDIOMS, ERRATA_COMMON,
        ERRATA_ASR_PHONETIC,
    )

    for correct in list(ERRATA_AUTHORS.values()) + list(ERRATA_WORKS.values()) + list(ERRATA_IDIOMS.values()) + list(ERRATA_COMMON.values()) + list(ERRATA_ASR_PHONETIC.values()):
        if correct and len(correct) >= 2:
            WORD_DICT.add(correct)

    _COMMON_WORDS = [
        "可能性", "分岔", "花园", "博尔赫斯", "平行", "时间", "选择", "命运",
        "决定", "路径", "可能性空间", "我执", "戏剧", "剧场", "演员", "角色",
        "创作", "艺术", "艺术家", "哲学", "概念", "理论", "观点", "思考",
        "不确定", "确定", "模糊", "清晰", "具体", "抽象", "逻辑", "冲突",
        "张力", "能量", "流动", "方向", "轨道", "节点", "交叉", "汇聚",
        "分散", "集中", "聚焦", "偏离", "回归", "循环", "突破", "边界",
        "限制", "自由", "约束", "规则", "秩序", "混乱", "结构", "解构",
        "意义", "价值", "判断", "评估", "认知", "感知", "体验", "感受",
        "理解", "解释", "诠释", "表达", "沟通", "对话", "交流", "互动",
        "共鸣", "共情", "同理心", "反思", "批判", "质疑", "挑战", "突破",
        "创新", "变革", "传统", "现代", "当代", "经典", "原创", "模仿",
        "真实", "虚构", "想象", "幻想", "现实", "理想", "实践", "理论",
        "个体", "群体", "社会", "文化", "历史", "未来", "过去", "现在",
        "存在", "虚无", "本质", "现象", "表象", "深层", "表面", "内在",
        "外在", "主观", "客观", "相对", "绝对", "矛盾", "统一", "对立",
        "转化", "融合", "分离", "连接", "断裂", "延续", "中断", "完成",
        "未完成", "开放", "封闭", "包容", "排斥", "接纳", "拒绝", "妥协",
        "坚持", "放弃", "执着", "释然", "纠结", "坦然", "焦虑", "平静",
        "激动", "冷静", "热情", "冷淡", "积极", "消极", "乐观", "悲观",
        "希望", "绝望", "勇气", "恐惧", "信任", "怀疑", "坚定", "动摇",
        "探索", "发现", "寻找", "迷失", "方向感", "目标", "过程", "结果",
        "手段", "目的", "原因", "结果", "前提", "结论", "假设", "验证",
        "证明", "推翻", "建立", "摧毁", "构建", "解构", "组合", "拆解",
        "整体", "局部", "系统", "要素", "关系", "结构", "功能", "形式",
        "内容", "载体", "媒介", "信息", "信号", "噪声", "编码", "解码",
        "语境", "语义", "语法", "语用", "符号", "指代", "隐喻", "转喻",
        "叙事", "故事", "情节", "人物", "场景", "氛围", "节奏", "韵律",
        "旋律", "和声", "音色", "力度", "速度", "张力", "释放", "高潮",
        "低谷", "起伏", "转折", "铺垫", "呼应", "对照", "映衬", "烘托",
        "渲染", "留白", "含蓄", "直白", "委婉", "尖锐", "温和", "激进",
        "保守", "前卫", "复古", "经典", "先锋", "实验", "探索", "尝试",
        "冒险", "稳妥", "大胆", "谨慎", "果断", "犹豫", "决绝", "徘徊",
        "坚定", "动摇", "执着", "放下", "追求", "放弃", "争取", "退让",
        "进攻", "防守", "主动", "被动", "引领", "跟随", "独立", "依附",
        "自主", "他律", "自律", "自由", "必然", "偶然", "必然性", "偶然性",
        "可能性", "现实性", "必然性", "或然性", "确定性", "不确定性",
        "分岔路", "十字路口", "歧路", "岔路", "交叉口", "抉择", "取舍",
        "进退", "攻守", "取舍", "权衡", "斟酌", "考量", "思量", "打算",
        "盘算", "计划", "规划", "设想", "构想", "蓝图", "愿景", "展望",
        "回顾", "反思", "总结", "归纳", "演绎", "推理", "推断", "推测",
        "猜测", "臆测", "估计", "评估", "评价", "评判", "鉴定", "认定",
        "确认", "核实", "查证", "验证", "校验", "检验", "测试", "审查",
        "审核", "审计", "监察", "监督", "管理", "控制", "调节", "调整",
        "优化", "改进", "改善", "提升", "提高", "增强", "加强", "巩固",
        "稳定", "维持", "保持", "延续", "持续", "继承", "发扬", "传承",
        "传播", "推广", "普及", "宣传", "倡导", "呼吁", "号召", "动员",
        "组织", "协调", "配合", "协作", "合作", "联合", "联盟", "结盟",
        "对抗", "竞争", "博弈", "较量", "角逐", "争夺", "抢占", "攻占",
        "守护", "保卫", "捍卫", "维护", "坚守", "把守", "镇守", "驻守",
        "巡视", "巡查", "巡逻", "视察", "督导", "指导", "引导", "带领",
        "率领", "指挥", "调度", "安排", "部署", "布置", "分配", "指派",
        "委派", "派遣", "差遣", "打发", "发送", "传达", "传递", "转达",
        "告知", "通知", "通报", "通告", "公告", "声明", "宣言", "承诺",
        "保证", "担保", "保障", "确保", "确认", "肯定", "否定", "拒绝",
        "否认", "反驳", "驳斥", "批判", "抨击", "攻击", "指责", "控诉",
        "控告", "起诉", "申诉", "上诉", "辩护", "辩解", "辩白", "辩驳",
        "争论", "争辩", "辩论", "讨论", "商讨", "商议", "协商", "磋商",
        "谈判", "交涉", "斡旋", "调停", "调解", "仲裁", "裁决", "判决",
        "裁定", "决定", "决议", "决策", "策略", "战略", "战术", "方法",
        "方式", "手段", "途径", "渠道", "路径", "方向", "目标", "目的",
        "动机", "意图", "企图", "打算", "计划", "方案", "对策", "措施",
        "办法", "招数", "套路", "模式", "范式", "框架", "体系", "系统",
        "机制", "制度", "规则", "规范", "标准", "准则", "原则", "底线",
        "红线", "界限", "边界", "范围", "领域", "范畴", "类别", "类型",
        "种类", "品种", "款式", "风格", "流派", "学派", "门派", "派别",
        "阵营", "立场", "态度", "观点", "看法", "见解", "主张", "意见",
        "建议", "提议", "倡议", "呼吁", "号召", "倡导", "提倡", "推崇",
        "推崇备至", "赞不绝口", "交口称赞", "一致好评", "有口皆碑",
        "口碑载道", "誉满天下", "名扬四海", "闻名遐迩", "家喻户晓",
        "妇孺皆知", "尽人皆知", "众所周知", "不言而喻", "显而易见",
        "一目了然", "心知肚明", "心照不宣", "默契", "心领神会",
        "心有灵犀", "不谋而合", "异口同声", "殊途同归", "异曲同工",
        "如出一辙", "大同小异", "千篇一律", "一模一样", "毫无二致",
        "截然不同", "天壤之别", "判若云泥", "判若两人", "今非昔比",
        "物是人非", "沧海桑田", "翻天覆地", "日新月异", "瞬息万变",
        "变化无常", "变幻莫测", "不可捉摸", "难以预料", "出人意料",
        "始料未及", "猝不及防", "防不胜防", "措手不及", "手忙脚乱",
        "慌慌张张", "急急忙忙", "匆匆忙忙", "慌不择路", "饥不择食",
        "寒不择衣", "慌忙", "匆忙", "急促", "紧迫", "紧急", "危急",
        "危在旦夕", "岌岌可危", "摇摇欲坠", "风雨飘摇", "动荡不安",
        "动荡", "波动", "震荡", "震荡", "起伏", "颠簸", "坎坷", "曲折",
        "蜿蜒", "迂回", "曲折", "蜿蜒", "曲折", "弯路", "弯道", "弯角",
        "拐角", "转角", "转折点", "拐点", "临界点", "节点", "分岔点",
        "交叉点", "汇合点", "交汇点", "汇聚点", "分散点", "起点", "终点",
        "出发", "到达", "启程", "归途", "回路", "循环", "往返", "来回",
        "反复", "重复", "再现", "重现", "回顾", "追溯", "反思", "反省",
        "觉悟", "觉醒", "领悟", "领悟", "感悟", "感触", "感慨", "感叹",
        "惊叹", "赞叹", "感叹", "感慨", "唏嘘", "嗟叹", "惋惜", "遗憾",
        "后悔", "懊悔", "悔恨", "悔悟", "醒悟", "顿悟", "领悟", "参悟",
        "感悟", "体会", "体验", "经历", "阅历", "经验", "教训", "启示",
        "启发", "启迪", "开导", "引导", "指引", "指导", "点拨", "提点",
        "提醒", "提示", "暗示", "明示", "表示", "表达", "表述", "陈述",
        "说明", "解释", "阐释", "阐述", "论述", "论证", "论辩", "辩论",
        "讨论", "商讨", "探讨", "探究", "探索", "摸索", "尝试", "试验",
        "实验", "实践", "实操", "操作", "执行", "实施", "落实", "贯彻",
        "推行", "推进", "推动", "促进", "催生", "引发", "触发", "激发",
        "激励", "鼓励", "鼓舞", "振奋", "振作", "崛起", "复兴", "振兴",
        "繁荣", "昌盛", "兴旺", "发达", "蓬勃", "欣欣向荣", "蒸蒸日上",
        "如日中天", "方兴未艾", "蓬勃发展", "日新月异", "突飞猛进",
        "一日千里", "飞速发展", "迅猛发展", "高速发展", "稳步发展",
        "持续发展", "可持续发展", "高质量发展", "创新发展", "协调发展",
        "绿色发展", "开放发展", "共享发展", "新发展理念",
        "置身事外", "身临其境", "设身处地", "将心比心", "换位思考",
        "感同身受", "同病相怜", "惺惺相惜", "志同道合", "情投意合",
        "心心相印", "心有灵犀", "不谋而合", "异口同声", "殊途同归",
        "异曲同工", "如出一辙", "大同小异", "千篇一律", "一模一样",
        "截然不同", "天壤之别", "判若云泥", "判若两人", "今非昔比",
        "功成名就", "名利双收", "名利兼收", "名利双全", "名利双收",
        "耳濡目染", "潜移默化", "润物无声", "春风化雨", "循循善诱",
        "谆谆教导", "苦口婆心", "语重心长", "言传身教", "以身作则",
        "率先垂范", "身体力行", "言行一致", "表里如一", "名副其实",
        "名不虚传", "当之无愧", "实至名归", "受之无愧", "理所应当",
        "理所当然", "顺理成章", "水到渠成", "瓜熟蒂落", "自然而然",
        "不期而遇", "不约而同", "不谋而合", "不期然而然", "不以为然",
        "不以为意", "不以为耻", "不以为然", "不置可否", "不置一词",
        "不言而喻", "不言自明", "不言自喻", "不可言喻", "不可名状",
        "不可思议", "不可理喻", "不可救药", "不可挽回", "不可逆转",
        "不可逾越", "不可磨灭", "不可磨灭", "不可分割", "不可或缺",
        "不可替代", "不可复制", "不可再生", "不可逆转", "不可阻挡",
        "势不可挡", "所向披靡", "势如破竹", "摧枯拉朽", "排山倒海",
        "翻江倒海", "惊天动地", "震天动地", "惊天动地", "气吞山河",
        "气壮山河", "气贯长虹", "气势磅礴", "波澜壮阔", "汹涌澎湃",
        "风起云涌", "波涛汹涌", "惊涛骇浪", "狂风暴雨", "暴风骤雨",
        "倾盆大雨", "瓢泼大雨", "滂沱大雨", "大雨如注", "大雨滂沱",
        "细雨绵绵", "毛毛细雨", "和风细雨", "春风化雨", "润物无声",
        "潜移默化", "耳濡目染", "言传身教", "以身作则", "身体力行",
        "贡布里希", "博尔赫斯", "卡尔维诺", "马尔克斯", "博尔赫斯",
        "小径分岔的花园", "百年孤独", "看不见的城市", "交叉小径的花园",
        "如果有一天", "在某个时间点", "从分岔的花园", "花园在并行",
    ]
    for w in _COMMON_WORDS:
        if len(w) >= 2:
            WORD_DICT.add(w)


def forward_max_match(text: str, word_dict: set[str], max_len: int = 6) -> list[str]:
    words = []
    i = 0
    while i < len(text):
        matched = False
        for length in range(min(max_len, len(text) - i), 1, -1):
            candidate = text[i:i + length]
            if candidate in word_dict:
                words.append(candidate)
                i += length
                matched = True
                break
        if not matched:
            words.append(text[i])
            i += 1
    return words


SWALLOW_CHAR_PATTERNS = [
    (r'(.)\1{2,}', 'repeat_stutter', '疑似口吃/重复：{0}出现3次以上'),
    (r'[\u4e00-\u9fff][啊呃嗯唔哦噢哈呀哇嘛呗]', 'filler_sound', '疑似语气词/含糊音：{0}'),
    (r'什么[教叫要是]', 'asr_confusion', '疑似ASR混淆："什么{1}"可能为"什么叫做/就是"'),
]

CONTEXT_DISAMBIGUATION = [
    {
        "context_words": ["博尔赫斯", "花园", "分岔", "时间", "路径", "可能性"],
        "corrections": {
            "分叉": "分岔",
            "分差": "分岔",
            "分茶": "分岔",
            "花园里": "花园",
            "并型": "并行",
            "冰型": "并行",
            "平型": "平行",
        },
    },
    {
        "context_words": ["戏剧", "剧场", "演员", "角色", "舞台", "演出"],
        "corrections": {
            "戏聚": "戏剧",
            "系剧": "戏剧",
            "洗剧": "戏剧",
            "充座": "创作",
            "冲座": "创作",
        },
    },
    {
        "context_words": ["我执", "执着", "坚持", "执念"],
        "corrections": {
            "我值": "我执",
            "我职": "我执",
            "我直": "我执",
            "我只": "我执",
        },
    },
    {
        "context_words": ["贡布里希", "艺术", "艺术史"],
        "corrections": {
            "公布里": "贡布里",
            "公布里希": "贡布里希",
            "贡布里斯": "贡布里希",
        },
    },
    {
        "context_words": ["可能性", "不确定", "选择", "分岔"],
        "corrections": {
            "可能现": "可能性",
            "可能线": "可能性",
            "可能性现": "可能性",
        },
    },
]

PHONETIC_CONFUSION_GROUPS = [
    {"zh": "z", "ch": "c", "sh": "s"},
    {"n": "l", "l": "n"},
    {"f": "h", "h": "f"},
    {"an": "ang", "ang": "an", "en": "eng", "eng": "en", "in": "ing", "ing": "in"},
]


def _check_phonetic_confusion(word: str, word_dict: set[str]) -> list[tuple[str, float]]:
    candidates = []
    for group in PHONETIC_CONFUSION_GROUPS:
        for wrong, correct in group.items():
            if wrong in word:
                variant = word.replace(wrong, correct)
                if variant in word_dict and variant != word:
                    candidates.append((variant, 0.6))
    return candidates


def verify_word_level(
    text: str,
    context_before: str = "",
    context_after: str = "",
    custom_errata: dict | None = None,
) -> WordVerificationResult:
    _load_word_dict()

    result = WordVerificationResult()
    words = forward_max_match(text, WORD_DICT)
    result.total_words = len(words)

    full_context = f"{context_before} {text} {context_after}".strip()

    pos = 0
    for word in words:
        if len(word) < 2:
            pos += 1
            continue

        if custom_errata:
            for wrong, correct in custom_errata.items():
                if wrong in word and wrong != correct:
                    result.issues.append(WordIssue(
                        word=word, position=pos,
                        issue_type="custom_errata",
                        severity="critical",
                        description=f"自定义勘误：'{wrong}'应为'{correct}'",
                        suggestion=correct,
                        confidence=0.95,
                    ))

        for ctx_rule in CONTEXT_DISAMBIGUATION:
            if any(cw in full_context for cw in ctx_rule["context_words"]):
                for wrong, correct in ctx_rule["corrections"].items():
                    if wrong in text and correct not in text:
                        result.issues.append(WordIssue(
                            word=wrong, position=text.index(wrong),
                            issue_type="contextual_disambiguation",
                            severity="critical",
                            description=f"语境纠错：'{wrong}'应为'{correct}'（上下文含{[w for w in ctx_rule['context_words'] if w in full_context][:3]}）",
                            suggestion=correct,
                            confidence=0.85,
                        ))

        if word not in WORD_DICT and len(word) >= 3:
            candidates = _check_phonetic_confusion(word, WORD_DICT)
            for candidate, conf in candidates:
                result.issues.append(WordIssue(
                    word=word, position=pos,
                    issue_type="phonetic_confusion",
                    severity="warning",
                    description=f"疑似平翘舌/韵母混淆：'{word}'可能为'{candidate}'",
                    suggestion=candidate,
                    confidence=conf,
                ))

        pos += len(word)

    for pattern, issue_type, desc_template in SWALLOW_CHAR_PATTERNS:
        for match in re.finditer(pattern, text):
            matched_text = match.group()
            desc = desc_template.format(matched_text, matched_text[-1] if len(matched_text) > 1 else "")
            result.issues.append(WordIssue(
                word=matched_text, position=match.start(),
                issue_type=issue_type,
                severity="warning",
                description=desc,
                suggestion="",
                confidence=0.5,
            ))

    if result.issues:
        result.score = max(0, 100 - result.critical_count * 10 - result.warning_count * 3)

    return result


def verify_entries_word_level(
    entries: list[dict],
    custom_errata: dict | None = None,
    context_window: int = 3,
) -> list[WordVerificationResult]:
    results = []
    for i, entry in enumerate(entries):
        text = entry.get("text", "")
        prev_texts = [entries[j].get("text", "") for j in range(max(0, i - context_window), i)]
        next_texts = [entries[j].get("text", "") for j in range(i + 1, min(len(entries), i + 1 + context_window))]
        context_before = " ".join(prev_texts)
        context_after = " ".join(next_texts)

        result = verify_word_level(text, context_before, context_after, custom_errata)
        results.append(result)

    return results


def check_subtitle_overlap(entries: list[dict]) -> list[WordIssue]:
    issues = []
    sorted_entries = sorted(entries, key=lambda e: e.get("start_s", 0))
    for i in range(len(sorted_entries) - 1):
        curr_end = sorted_entries[i].get("end_s", 0)
        next_start = sorted_entries[i + 1].get("start_s", 0)
        if curr_end > next_start:
            overlap = curr_end - next_start
            issues.append(WordIssue(
                word="", position=i,
                issue_type="subtitle_overlap",
                severity="critical",
                description=f"字幕重叠：第{i + 1}条结束于{curr_end:.2f}s，第{i + 2}条开始于{next_start:.2f}s，重叠{overlap:.2f}s",
                suggestion=f"将第{i + 1}条end_s调整为{next_start - 0.04:.2f}s",
                confidence=1.0,
            ))
    return issues
