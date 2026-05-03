# Quick Start

三种方式使用 Auto Podcast Slicer：**Agent SKILL**（对话驱动）、**CLI**（命令行）、**Python API**（编程集成）。

## 前置条件

- Python >= 3.10
- FFmpeg 已安装并在 PATH 中
- 一期播客的素材文件（视频 .mp4 / 音频 .wav / 转录 .json）

## 安装

```bash
pip install git+https://github.com/tyouter/auto-podcast-slicer.git
```

验证：

```bash
garden --help
```

## 核心架构：意图与执行分离

本项目的核心设计是**意图与执行分离**：

```
意图层（需要智能）              执行层（确定性）
─────────────────────         ─────────────────────
选什么片段？                   切片、字幕、渲染、导出
起什么标题？         ──YAML──→  按 start_s/end_s 切割
提炼什么钩子？                 勘误纠错 + 字幕渲染
分什么系列？                   横版/竖版/多平台导出
```

- **Agent SKILL 方式**：LLM 自动理解意图，生成项目文件，然后调用 pipeline 执行
- **CLI / Python 方式**：需要**预先准备好项目文件**，pipeline 按文件中的定义执行

> ⚠️ **CLI 和 Python API 不包含意图理解能力。** 如果你使用这两种方式，需要自行创建项目文件。你可以用任何 LLM Agent 生成这些文件——只要格式正确，pipeline 就能执行。

---

## 项目文件格式

CLI 和 Python API 的输入是**项目目录**，其中包含以下文件：

### 必需文件：project.yaml

```yaml
name: "项目名称"                    # 项目标识
description: "项目描述"              # 可选

sources:
  transcript: "/path/to/transcript.json"   # FunASR 转录结果（.json）
  audio: "/path/to/audio.wav"              # 音频文件（.wav）
  video: "/path/to/video.mp4"              # 视频文件（.mp4，可选）
  wiki: "/path/to/wiki.md"                 # Wiki 文件（Markdown/YAML，可选）
  outline: "/path/to/outline.md"           # 大纲文件（Markdown/TXT，可选）
  notes: "/path/to/notes.md"               # 笔记文件（Markdown/TXT，可选）

output:
  base_dir: "/path/to/output"              # 输出目录，可选，默认 <project_dir>/output
```

**关键参数说明：**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `sources.transcript` | string | ✅ | FunASR mixed 格式的 JSON 转录文件，包含逐条带时间戳的文本 |
| `sources.audio` | string | ✅ | 原始音频，用于切割输出 WAV/MP3 |
| `sources.video` | string | ⚪ | 原始视频，用于烧录字幕和生成竖版。如不提供则只输出音频和字幕 |
| `sources.wiki` | string | ⚪ | Wiki 文件（Markdown/YAML），包含知识结构和章节规划，供 Agent 参考规划切片方案 |
| `sources.outline` | string | ⚪ | 大纲文件（Markdown/TXT），包含内容结构和重点标注，供 Agent 参考规划切片方案 |
| `sources.notes` | string | ⚪ | 笔记文件（Markdown/TXT），包含创作想法和素材标注，供 Agent 参考规划切片方案 |

### 必需文件：clips.yaml

定义切片方案——**这是意图的核心载体**，决定了"从哪里切、切多大、叫什么"。

```yaml
# 每个顶级键是一个系列名，可以自定义
highlights:                          # 系列名：高光片段
  - id: H01                          # [必需] 切片唯一标识，用于文件命名和目录结构
    title: "时间不是线性的"           # [必需] 切片标题
    series: 高光                      # [必需] 系列名（应与顶级键一致）
    start_s: 1580                    # [必需] ⭐ 起始秒数——剪辑的核心锚点
    end_s: 1610                      # [必需] ⭐ 结束秒数——剪辑的核心锚点
    hook: "时间在这里分岔了"          # [推荐] 钩子文案，用于传播
    domain: 时间哲学                  # [推荐] 主题域，用于分类

philosophy:                          # 另一个系列
  - id: P01
    title: "博尔赫斯与时间分岔"
    series: 哲思
    start_s: 640
    end_s: 780
    hook: "博尔赫斯写了一个关于时间分岔的故事"
    domain: 文学
    description: "深入讨论时间分岔的哲学含义"  # [可选] 详细描述
    chapter: "第一章 · 缘起"                   # [可选] 章节标记（深度思考系列用）
```

**关键参数说明：**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 切片唯一标识，仅用字母数字和下划线，用于文件名和目录名 |
| `title` | string | ✅ | 切片标题，写入 metadata.json |
| `series` | string | ✅ | 系列名，决定输出目录层级 |
| **`start_s`** | float | ✅ | **起始秒数**，ffmpeg `-ss` 参数，决定从哪里开始切 |
| **`end_s`** | float | ✅ | **结束秒数**，ffmpeg `-to` 参数，决定切到哪里 |
| `hook` | string | 推荐 | 钩子文案，用于短视频开头吸引注意力 |
| `domain` | string | 推荐 | 主题域，用于分类和检索 |
| `description` | string | 可选 | 详细描述 |
| `chapter` | string | 可选 | 章节标记 |

> 💡 `start_s` 和 `end_s` 是整个 pipeline 的核心锚点。所有处理都围绕这对时间码展开：ffmpeg 切割、字幕筛选、时长计算。确定这对时间码需要理解内容，这正是 LLM 的价值所在。

### 可选文件：corrections.yaml

项目级 ASR 勘误表，简单的错→对映射：

```yaml
corrections:
  博赫斯: 博尔赫斯          # 人名纠错
  小径分叉: 小径分岔        # ASR 同音混淆
  我值: 我执                # 语义纠错
  AVC: ""                   # 删除 ASR 噪音词（空字符串表示删除）
  H264: ""
```

**适用场景**：转录中反复出现的特定错误（人名、地名、专业术语）。框架已内置 200+ 条通用 ASR 纠错规则，corrections.yaml 是项目级的补充。

### 可选文件：errata.yaml

结构化勘误表，支持分类和正则模式：

```yaml
authors:
  博赫斯: 博尔赫斯
  公里希: 贡布里希

works:
  小径分叉的花园: 小径分岔的花园

idioms:
  取高贺寡: 曲高和寡

common:
  我值: 我执
  规道: 轨道

asr_phonetic:
  憋脚: 蹩脚

asr_noise:
  AVC: ""
  Ope: ""

asr_phonetic_patterns:           # 正则模式匹配
  - pattern: "智生(?!态|物)"     # 排除"智生态""智生物"
    replacement: "置身"

semantic_patterns:                # 语义异常检测
  - pattern: "置身室外"
    correction: "置身事外"
    description: "成语误用：室外→事外"
```

**corrections.yaml vs errata.yaml：**

| | corrections.yaml | errata.yaml |
|---|---|---|
| 格式 | 扁平 `错: 对` | 分类结构 + 正则 |
| 适用 | 简单替换 | 复杂纠错（语境消歧、正则匹配） |
| 优先级 | 后执行（在框架勘误之后） | 先执行（与框架勘误合并） |

### 可选字段：verification（project.yaml 内）

逐词校验的自定义配置，写在 `project.yaml` 中：

```yaml
verification:
  word_dict_extra:                # 自定义词典（补充框架内置 1152 词）
    - 小径分岔
    - 博尔赫斯
    - 贡布里希

  context_disambiguation:         # 语境消歧规则
    - pattern: "我值"
      correct: "我执"
      context: "佛教|哲学|执念"
```

### 项目目录结构

```
my-podcast/                       # 项目目录
├── project.yaml                  # [必需] 项目配置 + 素材路径
├── clips.yaml                    # [必需] 切片定义（意图核心）
├── corrections.yaml              # [可选] 简单勘误
├── errata.yaml                   # [可选] 结构化勘误
└── output/                       # 输出目录（自动创建）
    └── highlights/               # 按系列名组织
        └── H01/                  # 按 clip id 组织
            ├── H01_subtitled.mp4
            ├── H01_vertical.mp4
            ├── H01.ass
            ├── H01.srt
            ├── H01.wav
            ├── H01.mp3
            └── metadata.json
```

---

## 方式一：Agent SKILL（推荐）

与 AI Agent 对话，自动编排完整工作流。支持 Claude Code、Trae、Hermes。

Agent 自动完成意图理解 → 生成项目文件 → 调用 pipeline 执行的全流程，无需手动编写 YAML。

### Claude Code / Trae

在项目目录下打开 Agent，直接对话：

```
你: 帮我从这期播客中剪出5个最精彩的短视频

Agent: [激活 video-clip SKILL]
       → 制作人与你对话，理解创作意图
       → 生成 project.yaml + clips.yaml（意图物化）
       → 调用 pipeline 执行剪辑
       → 自动剪辑 + 字幕 + 音频 + 竖版
       → 调用 quality-audit SKILL 独立审核
       → 审核不通过则 autoresearch 优化
       → 交付成品
```

更多对话示例：

```
"审核一下生成的视频质量"
"这期播客有哪些值得做短视频的高光时刻？"
"帮我做一期深度思考的长视频"
"把成品导出到B站和抖音"
```

### Hermes

```bash
# 安装 SKILL
hermes skills install tyouter/auto-podcast-slicer

# 对话使用
hermes chat -q "Use the video-clip skill to produce 5 short clips from my podcast"

# 审核使用
hermes chat -q "Use the quality-audit skill to review the output"
```

### SKILL 工作流一览

| 工作流 | 触发方式 | 产出 |
|--------|---------|------|
| 制作人对话 | "我想做点东西" | 创作蓝图 |
| 一期一剪 | "出一期精剪" | 横版+竖版长视频 |
| 内容原子化 | "剪几个短视频" | 多条独立短视频 |
| 主题系列剪辑 | "做个主题系列" | 主题系列视频 |
| 全平台出品 | "导出到各平台" | 6 平台适配版本 |
| 素材库打包 | "打包交付" | 标准化目录 |

---

## 方式二：CLI 命令行

通过 `garden` 命令直接操作，适合脚本化、批处理、CI/CD 场景。

> ⚠️ CLI 不包含意图理解。你需要预先准备好 `project.yaml` 和 `clips.yaml`。可以用任何 LLM Agent 生成这些文件，只要格式符合上面的规范。

### 创建项目

```bash
# 使用空白模板创建（需要手动填写素材路径和切片定义）
python -c "from tools.project_manager import create_project; create_project('my-podcast', '/path/to/audio.wav')"
```

### 执行命令

```bash
# 切片处理
garden clip --project-dir /path/to/my-podcast --series highlights

# 质量检查
garden quality --project-dir /path/to/my-podcast

# 出品审核
garden audit --project-dir /path/to/my-podcast

# 全平台导出
garden export --project-dir /path/to/my-podcast

# 自动优化迭代
garden autoresearch --project-dir /path/to/my-podcast

# 查看项目状态
garden status --project-dir /path/to/my-podcast

# 查看可用优化策略
garden strategies
```

### CLI 速查

| 命令 | 说明 |
|------|------|
| `garden clip` | 切片处理 |
| `garden quality` | 质量检查 |
| `garden audit` | 出品审核 |
| `garden export` | 平台导出 |
| `garden autoresearch` | 自动优化 |
| `garden status` | 项目状态 |
| `garden strategies` | 优化策略列表 |

---

## 方式三：Python API

直接调用 pipeline 模块，适合集成到自己的应用、Jupyter Notebook、或自定义工作流。

> ⚠️ Python API 同样不包含意图理解。你需要预先创建 `project.yaml` 和 `clips.yaml`，或通过编程方式构造 `PipelineConfig` 对象。

### 切片处理

```python
from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.clip_processor import process_series

config = PipelineConfig(project_dir="/path/to/my-podcast")
ctx = load_project(config=config)

process_series(
    clips=config.get_clips("highlights"),
    series_dir=config.output_dir / "clips" / "highlights",
    entries=ctx.entries,
    audio_source=config.source_audio,
    video_source=config.source_video,
    custom_errata=ctx.custom_errata,
)
```

### 单条切片

```python
from pipeline.clip_processor import process_clip

result = process_clip(
    clip={"id": "H01", "start_s": 300, "end_s": 480, "title": "测试", "series": "高光"},
    clip_dir=config.output_dir / "clips" / "highlights" / "H01",
    entries=ctx.entries,
    audio_source=config.source_audio,
    video_source=config.source_video,
    custom_errata=ctx.custom_errata,
)
print(f"Output: {result.output_dir}, Errors: {result.errors}")
```

### 字幕处理

```python
from pipeline.text_normalizer import normalize_chinese
from pipeline.subtitle_formatter import format_subtitle_single_line
from pipeline.errata_engine import ErrataConfig, apply_errata
from pipeline.content_validator import validate_subtitle_content

# 文本规范化
text = normalize_chinese("繁體字和著作權")

# 勘误修正
errata_config = ErrataConfig.from_project_dir("/path/to/my-podcast")
corrected = apply_errata(text, errata_config.flat_errata)

# 字幕格式化
formatted = format_subtitle_single_line(corrected, max_chars=18)

# 内容验证
result = validate_subtitle_content(entries, errata_config)
print(f"Valid: {result.is_valid}, Issues: {len(result.issues)}")
```

### 质量检查

```python
from pipeline.quality_checker import run_quality_check

report = run_quality_check(
    output_dir="/path/to/my-podcast/output/clips/highlights",
    config=config,
    version_key="highlights"
)
print(f"Score: {report.overall_score}, Passed: {report.passed}")
for issue in report.critical_issues:
    print(f"  CRITICAL: {issue}")
```

### 响度标准化

```python
from pipeline.loudness_normalizer import normalize_for_platform, measure_loudness_detailed

info = measure_loudness_detailed("/path/to/audio.wav")
print(f"LUFS: {info['integrated_loudness']}, TruePeak: {info['true_peak']}")

normalize_for_platform("/path/to/audio.wav", target_lufs=-14)
```

### 多平台导出

```python
from pipeline.exporter import export_all_platforms

export_all_platforms(
    input_dir="/path/to/my-podcast/output/clips/highlights/H01",
    project_config=config
)
```

### Autoresearch

```python
from autoresearch.experiment import run_experiment

result = run_experiment(
    project_dir="/path/to/my-podcast",
    strategies=["improve_subtitle_errata", "word_level_verification"],
    max_iterations=3
)
print(f"Best score: {result.best_score}, Strategy: {result.best_strategy}")
```

---

## 三种方式对比

| | Agent SKILL | CLI | Python API |
|---|---|---|---|
| **适合场景** | 创意对话、端到端交付 | 批处理、脚本化、CI/CD | 应用集成、自定义工作流 |
| **交互方式** | 自然语言对话 | 命令行参数 | 函数调用 |
| **意图理解** | ✅ LLM 自动生成项目文件 | ❌ 需预先准备项目文件 | ❌ 需预先准备项目文件 |
| **质量审核** | ✅ 自动调用 quality-audit | ✅ `garden audit` | ✅ `run_quality_check()` |
| **autoresearch** | ✅ 审核不通过自动触发 | ✅ `garden autoresearch` | ✅ `run_experiment()` |
| **学习成本** | 低（对话即可） | 中（需了解命令+文件格式） | 高（需了解 API+文件格式） |
| **灵活性** | 中（SKILL 编排） | 中（命令组合） | 高（完全控制） |

### 用其他 Agent 生成意图文件

CLI 和 Python API 的项目文件格式是开放的。你可以用任何 LLM Agent 生成这些文件：

```
1. 将转录文件交给任意 LLM Agent
2. 让 Agent 分析内容，选出片段，确定 start_s / end_s
3. Agent 输出 project.yaml + clips.yaml
4. 用 CLI 或 Python API 执行 pipeline
```

示例 prompt：

```
分析以下播客转录文件，选出5个最精彩的高光片段，输出为 clips.yaml 格式。
每个片段需要包含：id, title, series, start_s, end_s, hook, domain。
片段时长建议 30-120 秒。
```
