from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExpectedFile:
    pattern: str
    required: bool = True
    description: str = ""


@dataclass
class ExpectedProperty:
    name: str
    check_type: str
    expected_value: str | int | float | None = None
    tolerance: float = 0.0
    description: str = ""


@dataclass
class VerificationScenario:
    scenario_id: str
    user_request: str
    expected_workflow: str
    description: str
    expected_files: list[ExpectedFile] = field(default_factory=list)
    expected_properties: list[ExpectedProperty] = field(default_factory=list)
    quality_checks: list[str] = field(default_factory=list)
    output_dir_pattern: str = ""
    risk_level: str = "low"


@dataclass
class SkillModification:
    modification_id: str
    description: str
    hypothesis: str
    skill_patch: dict = field(default_factory=dict)
    risk_level: str = "medium"


SCENARIOS = {
    "verify_workflow1_full_episode": VerificationScenario(
        scenario_id="verify_workflow1_full_episode",
        user_request="帮我剪辑这期播客，生成完整版视频",
        expected_workflow="工作流1：一期一剪",
        description="验证SKILL能否引导Agent完成一期完整播客的精剪流程",
        expected_files=[
            ExpectedFile("*_subtitled.mp4", True, "横版带字幕视频"),
            ExpectedFile("*_vertical.mp4", True, "竖版视频（模糊背景填充）"),
            ExpectedFile("*.ass", True, "ASS字幕文件"),
            ExpectedFile("*.srt", True, "SRT字幕文件"),
            ExpectedFile("*.wav", True, "WAV音频"),
            ExpectedFile("*.mp3", False, "MP3音频"),
            ExpectedFile("metadata.json", True, "元数据"),
        ],
        expected_properties=[
            ExpectedProperty("video_resolution", "equals", "1920x1080", description="横版分辨率"),
            ExpectedProperty("vertical_resolution", "equals", "1080x1920", description="竖版分辨率"),
            ExpectedProperty("subtitle_accuracy", ">=", 99.9, tolerance=0.1, description="字幕准确率"),
            ExpectedProperty("audio_lufs", "range", -15, tolerance=1.0, description="响度LUFS"),
            ExpectedProperty("vertical_no_crop", "equals", True, description="竖版无裁剪"),
        ],
        quality_checks=[
            "字幕逐句零容忍勘误",
            "音视频同步≤50ms",
            "响度标准化至目标LUFS",
            "竖版模糊背景填充非裁剪",
        ],
        output_dir_pattern="output/clips_*/clip*",
        risk_level="low",
    ),
    "verify_workflow2_content_atomization": VerificationScenario(
        scenario_id="verify_workflow2_content_atomization",
        user_request="从这期播客里拆出几个短视频，发抖音和Shorts",
        expected_workflow="工作流2：内容原子化",
        description="验证SKILL能否引导Agent识别高光时刻并产出独立短视频",
        expected_files=[
            ExpectedFile("*/clip_*_subtitled.mp4", True, "每个切片横版视频"),
            ExpectedFile("*/clip_*_vertical.mp4", True, "每个切片竖版视频"),
            ExpectedFile("*/*.ass", True, "ASS字幕"),
            ExpectedFile("*/*.srt", True, "SRT字幕"),
            ExpectedFile("*/metadata.json", True, "每个切片元数据"),
            ExpectedFile("summary.json", True, "切片集总览"),
        ],
        expected_properties=[
            ExpectedProperty("clip_count", "range", 5, tolerance=3, description="切片数量5-8个"),
            ExpectedProperty("clip_duration_range", "range", 60, tolerance=45, description="切片时长15s-3min"),
            ExpectedProperty("each_clip_independent", "equals", True, description="每个切片独立可理解"),
            ExpectedProperty("has_hook", "equals", True, description="每个切片有明确钩子"),
        ],
        quality_checks=[
            "高光检测覆盖金句/情绪/悬念/故事/争议",
            "每个切片独立可理解无需上下文",
            "前3秒有明确钩子",
            "竖版9:16模糊背景填充",
        ],
        output_dir_pattern="output/clips_*/",
        risk_level="low",
    ),
    "verify_workflow3_knowledge_mashup": VerificationScenario(
        scenario_id="verify_workflow3_knowledge_mashup",
        user_request="按知识主题混剪一系列视频，像Wiki那样组织",
        expected_workflow="工作流3：知识混剪",
        description="验证SKILL能否引导Agent按知识结构跨时间线混剪",
        expected_files=[
            ExpectedFile("wiki_*/*_subtitled.mp4", True, "每章横版视频"),
            ExpectedFile("wiki_*/*_vertical.mp4", True, "每章竖版视频"),
            ExpectedFile("wiki_*/*.ass", True, "每章ASS字幕"),
            ExpectedFile("wiki_*/*.srt", True, "每章SRT字幕"),
            ExpectedFile("wiki_*/*.wav", True, "每章WAV音频"),
            ExpectedFile("wiki_*/*.mp3", False, "每章MP3音频"),
            ExpectedFile("wiki_*/metadata.json", True, "每章元数据"),
            ExpectedFile("summary.json", True, "系列总览含章节索引"),
        ],
        expected_properties=[
            ExpectedProperty("chapter_count", ">=", 3, description="至少3个章节"),
            ExpectedProperty("chapter_duration", "range", 120, tolerance=60, description="每章2-4分钟"),
            ExpectedProperty("naming_convention", "matches", "wiki_\\d+_", description="Wiki命名规范"),
            ExpectedProperty("cross_timeline", "equals", True, description="跨时间线素材调度"),
        ],
        quality_checks=[
            "知识图谱构建完整",
            "章节间有逻辑递进",
            "每章独立可看",
            "命名规范一致",
        ],
        output_dir_pattern="output/wiki_*/",
        risk_level="medium",
    ),
    "verify_workflow4_platform_export": VerificationScenario(
        scenario_id="verify_workflow4_platform_export",
        user_request="帮我导出各平台的版本，B站抖音YouTube都要",
        expected_workflow="工作流4：全平台出品",
        description="验证SKILL能否引导Agent正确适配各平台规格",
        expected_files=[
            ExpectedFile("bilibili/*.mp4", True, "B站版本"),
            ExpectedFile("douyin/*.mp4", True, "抖音版本"),
            ExpectedFile("youtube/*.mp4", True, "YouTube版本"),
        ],
        expected_properties=[
            ExpectedProperty("bilibili_resolution", "equals", "1920x1080", description="B站分辨率"),
            ExpectedProperty("douyin_resolution", "equals", "1080x1920", description="抖音分辨率"),
            ExpectedProperty("youtube_resolution", "equals", "1920x1080", description="YouTube分辨率"),
            ExpectedProperty("douyin_subtitle_chars", "<=", 12, description="抖音每行≤12字"),
            ExpectedProperty("each_lufs_compliant", "equals", True, description="各平台响度达标"),
        ],
        quality_checks=[
            "读取platforms.yaml平台规格",
            "每个平台独立响度标准化",
            "元数据嵌入",
        ],
        output_dir_pattern="output/platforms/",
        risk_level="medium",
    ),
    "verify_workflow5_asset_packaging": VerificationScenario(
        scenario_id="verify_workflow5_asset_packaging",
        user_request="把这期节目的所有产出打包给我",
        expected_workflow="工作流5：素材库打包",
        description="验证SKILL能否引导Agent完成标准化打包交付",
        expected_files=[
            ExpectedFile("full_episode/*_subtitled.mp4", True, "完整版横版视频"),
            ExpectedFile("full_episode/*_vertical.mp4", True, "完整版竖版视频"),
            ExpectedFile("full_episode/*.wav", True, "完整版WAV"),
            ExpectedFile("full_episode/*.ass", True, "完整版ASS"),
            ExpectedFile("full_episode/*.srt", True, "完整版SRT"),
            ExpectedFile("clips/", True, "短视频切片目录"),
            ExpectedFile("assets/subtitles/", True, "字幕素材库"),
            ExpectedFile("assets/audio/", True, "音频素材库"),
            ExpectedFile("COPYRIGHT.md", True, "版权声明"),
            ExpectedFile("RELEASE_CARDS.json", True, "发布信息卡"),
            ExpectedFile("summary.json", True, "项目总览"),
        ],
        expected_properties=[
            ExpectedProperty("dir_structure_complete", "equals", True, description="目录结构完整"),
            ExpectedProperty("copyright_exists", "equals", True, description="版权声明存在"),
            ExpectedProperty("release_cards_exist", "equals", True, description="发布信息卡存在"),
            ExpectedProperty("all_formats_present", "equals", True, description="所有格式齐全"),
        ],
        quality_checks=[
            "目录结构符合SKILL规范",
            "版权声明包含素材来源/授权/CC协议",
            "发布信息卡含标题/描述/标签/封面规格",
        ],
        output_dir_pattern="output/*/",
        risk_level="low",
    ),
    "verify_quality_redlines": VerificationScenario(
        scenario_id="verify_quality_redlines",
        user_request="任意工作流执行后的质量红线检查",
        expected_workflow="全部工作流",
        description="验证SKILL的质量红线是否被严格执行",
        expected_files=[],
        expected_properties=[
            ExpectedProperty("subtitle_accuracy", ">=", 99.9, tolerance=0.1, description="字幕准确率≥99.9%"),
            ExpectedProperty("av_sync_ms", "<=", 50, description="音视频同步≤50ms"),
            ExpectedProperty("lufs_deviation", "<=", 1.0, description="响度偏差≤1dB"),
            ExpectedProperty("vertical_no_crop", "equals", True, description="竖版无裁剪"),
            ExpectedProperty("copyright_clear", "equals", True, description="版权清晰"),
        ],
        quality_checks=[
            "逐句零容忍字幕勘误",
            "音视频同步检查",
            "响度达标检查",
            "竖版画面完整性检查",
            "版权声明存在性检查",
        ],
        output_dir_pattern="output/",
        risk_level="low",
    ),
    "verify_edge_ambiguous_request": VerificationScenario(
        scenario_id="verify_edge_ambiguous_request",
        user_request="帮我处理一下这期播客",
        expected_workflow="工作流1或2（需明确意图）",
        description="验证SKILL能否引导Agent处理模糊请求，主动澄清意图",
        expected_files=[],
        expected_properties=[
            ExpectedProperty("agent_clarifies_intent", "equals", True, description="Agent主动澄清意图"),
            ExpectedProperty("no_wrong_workflow", "equals", True, description="不盲目选择错误工作流"),
        ],
        quality_checks=[
            "模糊请求时主动询问确认",
            "不假设用户意图",
        ],
        output_dir_pattern="",
        risk_level="high",
    ),
    "verify_edge_multi_workflow": VerificationScenario(
        scenario_id="verify_edge_multi_workflow",
        user_request="帮我剪这期播客，拆几个短视频，然后导出各平台版本，最后打包",
        expected_workflow="工作流1→2→4→5（组合执行）",
        description="验证SKILL能否引导Agent按序组合多个工作流",
        expected_files=[
            ExpectedFile("full_episode/", True, "完整版"),
            ExpectedFile("clips/", True, "短视频切片"),
            ExpectedFile("platforms/", True, "平台适配版"),
            ExpectedFile("COPYRIGHT.md", True, "版权声明"),
            ExpectedFile("RELEASE_CARDS.json", True, "发布信息卡"),
        ],
        expected_properties=[
            ExpectedProperty("workflow_order_correct", "equals", True, description="工作流执行顺序正确"),
            ExpectedProperty("all_workflows_completed", "equals", True, description="所有工作流完成"),
            ExpectedProperty("intermediate_reuse", "equals", True, description="中间产物复用"),
        ],
        quality_checks=[
            "先精剪再切片再导出再打包",
            "前序工作流产出作为后序输入",
            "不重复处理",
        ],
        output_dir_pattern="output/",
        risk_level="high",
    ),
}


MODIFICATIONS = {
    "add_decision_tree": SkillModification(
        modification_id="add_decision_tree",
        description="在SKILL顶部添加工作流决策树，帮助Agent快速匹配用户意图到正确工作流",
        hypothesis="明确的决策树减少工作流选择错误，提升workflow_selection_accuracy",
        skill_patch={
            "section": "工作流",
            "action": "prepend",
            "content": """## 工作流决策树

根据用户请求选择工作流：

```
用户请求
├─ 包含"完整版"/"精剪"/"一期" → 工作流1：一期一剪
├─ 包含"短视频"/"切片"/"拆"/"抖音"/"Shorts"/"Reels" → 工作流2：内容原子化
├─ 包含"主题"/"系列"/"混剪"/"知识"/"Wiki" → 工作流3：知识混剪
├─ 包含"导出"/"平台"/"B站"/"YouTube"/"适配" → 工作流4：全平台出品
├─ 包含"打包"/"交付"/"全部产出"/"素材库" → 工作流5：素材库打包
├─ 模糊请求（如"处理一下"）→ 主动询问：您需要哪种处理？
└─ 组合请求 → 按序执行：1→2→4→5
```""",
        },
        risk_level="low",
    ),
    "add_checklists": SkillModification(
        modification_id="add_checklists",
        description="在每个工作流末尾添加执行检查清单，确保不遗漏步骤",
        hypothesis="检查清单减少遗漏步骤，提升output_completeness",
        skill_patch={
            "section": "每个工作流",
            "action": "append_to_each_workflow",
            "content": """**执行检查清单**：
- [ ] 所有expected_files已生成
- [ ] 字幕准确率≥99.9%
- [ ] 音视频同步≤50ms
- [ ] 响度达标（各平台LUFS ±1dB）
- [ ] 竖版视频模糊背景填充（非裁剪）
- [ ] metadata.json完整""",
        },
        risk_level="low",
    ),
    "add_examples": SkillModification(
        modification_id="add_examples",
        description="为每个工作流添加具体的用户请求示例和预期输出示例",
        hypothesis="具体示例提升Agent对工作流的理解，减少参数错误",
        skill_patch={
            "section": "每个工作流",
            "action": "append_to_each_workflow",
            "content": """**用户请求示例**：
- "帮我剪辑这期播客，生成完整版视频"
- "把这期录的播客剪一下，加上字幕"

**预期输出示例**：
```
output/clips_full/
├── episode_subtitled.mp4    # 1920x1080, H.264 CRF20
├── episode_vertical.mp4     # 1080x1920, 模糊背景填充
├── episode.ass              # Noto Sans SC, 圆角背景85%不透明
├── episode.srt
├── episode.wav              # 48kHz, AAC 192k
└── metadata.json
```""",
        },
        risk_level="low",
    ),
    "add_error_recovery": SkillModification(
        modification_id="add_error_recovery",
        description="添加错误恢复指引，当工作流执行失败时Agent知道如何处理",
        hypothesis="错误恢复指引提升鲁棒性，减少因单步失败导致整体失败",
        skill_patch={
            "section": "工作流",
            "action": "append",
            "content": """## 错误恢复

当工作流执行中遇到错误时：

1. **ffmpeg失败**：检查源文件是否存在、参数是否正确，降低CRF或preset重试
2. **字幕准确率不达标**：扩展ERRATA_ASR_PHONETIC，增加语义异常模式，重新运行勘误
3. **响度不达标**：执行两遍loudnorm（第一遍分析，第二遍标准化）
4. **竖版画面被裁剪**：确认使用split+boxblur+overlay滤镜链，而非crop
5. **文件缺失**：检查前序步骤是否完成，必要时重新执行该步骤
6. **组合工作流中断**：从失败步骤重新开始，复用已完成的中间产物""",
        },
        risk_level="low",
    ),
    "add_parameter_tables": SkillModification(
        modification_id="add_parameter_tables",
        description="将分散在各工作流中的参数整合为统一的参数参考表",
        hypothesis="集中参数表减少参数查找错误，提升parameter_compliance",
        skill_patch={
            "section": "底层能力索引",
            "action": "prepend",
            "content": """## 参数速查表

### 视频参数
| 用途 | 分辨率 | 编码 | 码率/CRF | 像素格式 |
|------|--------|------|----------|----------|
| 横版 | 1920x1080 | H.264 | CRF 20 | yuv420p |
| 竖版 | 1080x1920 | H.264 | CRF 22 | yuv420p |
| B站 | 1920x1080 | H.264 | 8Mbps | yuv420p |
| 抖音 | 1080x1920 | H.264 | 6Mbps | yuv420p |
| YouTube | 1920x1080 | H.264 | 10Mbps | yuv420p |
| 存档母带 | 原始 | ProRes 422 | - | 原始 |

### 音频参数
| 用途 | 编码 | 码率 | 采样率 | LUFS | True Peak |
|------|------|------|--------|------|-----------|
| 通用 | AAC | 192k | 48kHz | -14 | -1 |
| 抖音 | AAC | 128k | 48kHz | -14 | -1 |
| 播客 | AAC | 192k | 48kHz | -16 | -1 |
| 存档 | PCM | 24bit | 48kHz | - | - |

### 字幕参数
| 属性 | 值 |
|------|-----|
| 字体 | Noto Sans SC |
| 背景样式 | BorderStyle=3, 圆角 |
| 背景色 | #1A1A1A, 85%不透明 |
| 文字色 | 白色 |
| 每行字数 | ≤18（通用）, ≤12（抖音）|
| 准确率 | ≥99.9% |""",
        },
        risk_level="low",
    ),
    "simplify_structure": SkillModification(
        modification_id="simplify_structure",
        description="精简SKILL结构，移除底层能力索引（Agent可自行查找），突出工作流和决策逻辑",
        hypothesis="精简SKILL减少信息过载，Agent聚焦核心决策逻辑",
        skill_patch={
            "section": "底层能力索引",
            "action": "replace",
            "content": "底层能力索引已移除。Agent可自行通过SearchCodebase查找pipeline模块和配置文件。",
        },
        risk_level="medium",
    ),
    "add_role_activation": SkillModification(
        modification_id="add_role_activation",
        description="在工作流中明确标注当前激活的角色，强化角色切换意识",
        hypothesis="显式角色标注提升Agent对职责边界的感知，减少角色混淆",
        skill_patch={
            "section": "工作流",
            "action": "modify_each_workflow",
            "content": """在每个工作流步骤前标注角色：
1. [策划总监] 素材审阅：...
2. [剪辑师] 粗剪规划：...
3. [剪辑师] 精剪执行：...
4. [字幕师] 字幕制作：...
5. [声音设计师] 声音处理：...
6. [包装师] 成片输出：...
7. [出品人] 质量检查：...""",
        },
        risk_level="low",
    ),
    "add_delivery_template": SkillModification(
        modification_id="add_delivery_template",
        description="添加交付物模板，明确每个工作流的交付物清单和验收标准",
        hypothesis="明确交付模板减少交付遗漏，提升output_completeness和delivery_score",
        skill_patch={
            "section": "工作流",
            "action": "append_to_each_workflow",
            "content": """**交付物清单**：
| 交付物 | 格式 | 必需 | 验收标准 |
|--------|------|------|----------|
| 横版视频 | MP4 1920x1080 | 是 | H.264, CRF20, 字幕内嵌 |
| 竖版视频 | MP4 1080x1920 | 是 | 模糊背景填充, 非裁剪 |
| ASS字幕 | .ass | 是 | Noto Sans SC, 圆角背景85% |
| SRT字幕 | .srt | 是 | UTF-8, 时间轴准确 |
| WAV音频 | .wav | 是 | 48kHz, 响度达标 |
| MP3音频 | .mp3 | 否 | 192kbps |
| 元数据 | metadata.json | 是 | 含标题/描述/时长/字幕数 |""",
        },
        risk_level="low",
    ),
    "add_output_spec_per_workflow": SkillModification(
        modification_id="add_output_spec_per_workflow",
        description="为每个工作流添加明确的输出文件规格，包含文件名模式和目录结构",
        hypothesis="明确的输出规格让Agent知道该产出什么文件，提升output_completeness",
        skill_patch={
            "section": "工作流",
            "action": "append_to_each_workflow",
            "content": """**输出规格**：
- 输出目录：`output/{project_name}/`
- 横版视频：`{id}_subtitled.mp4` (1920x1080)
- 竖版视频：`{id}_vertical.mp4` (1080x1920)
- ASS字幕：`{id}.ass`
- SRT字幕：`{id}.srt`
- WAV音频：`{id}.wav`
- MP3音频：`{id}.mp3`
- 元数据：`metadata.json`
- 版权声明：`COPYRIGHT.md`
- 发布信息卡：`RELEASE_CARDS.json`""",
        },
        risk_level="low",
    ),
    "add_platform_output_spec": SkillModification(
        modification_id="add_platform_output_spec",
        description="为工作流4添加各平台的具体输出目录和文件命名规范",
        hypothesis="明确的平台输出规范减少导出遗漏，提升workflow4的output_completeness",
        skill_patch={
            "section": "工作流4：全平台出品",
            "action": "append",
            "content": """**平台输出目录结构**：
```
output/{project_name}/platforms/
├── bilibili/
│   └── {id}_bilibili.mp4      # 1920x1080, H.264 8Mbps, AAC 192k, SRT
├── douyin/
│   └── {id}_douyin.mp4        # 1080x1920, H.264 6Mbps, AAC 128k, ≤12字/行
├── youtube/
│   ├── {id}_youtube.mp4       # 1920x1080, H.264 10Mbps, AAC 192k
│   └── {id}_shorts.mp4        # 1080x1920, ≤60秒
├── podcast/
│   ├── {id}_xiaoyuzhou.m4a    # AAC 192k, LUFS -16
│   └── {id}_apple.m4a         # AAC 192k, LUFS -16
└── archive/
    └── {id}_master.mov         # ProRes 422 + PCM 24bit
```""",
        },
        risk_level="low",
    ),
    "add_packaging_output_spec": SkillModification(
        modification_id="add_packaging_output_spec",
        description="为工作流5添加详细的打包输出目录结构和文件清单",
        hypothesis="明确的打包规范减少遗漏，提升workflow5的output_completeness",
        skill_patch={
            "section": "工作流5：素材库打包",
            "action": "append",
            "content": """**打包输出清单**：
- `full_episode/` — 完整版视频（横版+竖版+音频+字幕）
- `clips/` — 短视频切片（每个clip独立文件夹）
- `wiki_series/` — 知识混剪系列（如适用）
- `platforms/` — 各平台适配版本（bilibili/douyin/youtube/podcast/archive）
- `assets/subtitles/` — 全部字幕文件集合
- `assets/audio/` — 全部音频文件集合
- `assets/covers/` — 封面图集合
- `COPYRIGHT.md` — 版权声明（素材来源/授权/CC协议）
- `RELEASE_CARDS.json` — 发布信息卡（标题/描述/标签/封面规格）
- `summary.json` — 项目总览（含所有产出物索引）""",
        },
        risk_level="low",
    ),
    "add_multi_workflow_spec": SkillModification(
        modification_id="add_multi_workflow_spec",
        description="添加组合工作流的详细执行规范和中间产物复用规则",
        hypothesis="明确的组合规范提升edge_multi_workflow场景的输出完整度",
        skill_patch={
            "section": "工作流",
            "action": "append",
            "content": """## 组合工作流规范

当用户请求涉及多个工作流时，按以下规则执行：

1. **执行顺序**：工作流1 → 工作流2 → 工作流4 → 工作流5
2. **中间产物复用**：
   - 工作流1的输出作为工作流2的输入源
   - 工作流2的每个切片作为工作流4的导出源
   - 所有工作流的产出作为工作流5的打包源
3. **不重复处理**：已完成的步骤不重新执行
4. **输出目录**：所有产出物统一在 `output/{project_name}/` 下
5. **完整交付**：组合执行时必须包含 full_episode/, clips/, platforms/, COPYRIGHT.md, RELEASE_CARDS.json""",
        },
        risk_level="low",
    ),
}


def get_all_scenarios() -> dict[str, VerificationScenario]:
    return SCENARIOS.copy()


def get_all_modifications() -> dict[str, SkillModification]:
    return MODIFICATIONS.copy()


def get_scenario(name: str) -> VerificationScenario | None:
    return SCENARIOS.get(name)


def get_modification(name: str) -> SkillModification | None:
    return MODIFICATIONS.get(name)


def get_recommended_modifications(metrics: dict) -> list[SkillModification]:
    recommended = []
    if metrics.get("workflow_selection_accuracy", 100) < 80:
        recommended.append(MODIFICATIONS["add_decision_tree"])
    if metrics.get("output_completeness", 100) < 80:
        recommended.append(MODIFICATIONS["add_output_spec_per_workflow"])
        recommended.append(MODIFICATIONS["add_delivery_template"])
        recommended.append(MODIFICATIONS["add_packaging_output_spec"])
        recommended.append(MODIFICATIONS["add_platform_output_spec"])
        recommended.append(MODIFICATIONS["add_multi_workflow_spec"])
    if metrics.get("parameter_compliance", 100) < 80:
        recommended.append(MODIFICATIONS["add_parameter_tables"])
        recommended.append(MODIFICATIONS["add_examples"])
    if metrics.get("quality_compliance", 100) < 80:
        recommended.append(MODIFICATIONS["add_error_recovery"])
    if not recommended:
        for mod in MODIFICATIONS.values():
            if mod.risk_level == "low":
                recommended.append(mod)
    return recommended
