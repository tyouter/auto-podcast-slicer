# Auto Podcast Slicer

播客视频全链路自动化制作框架。从"我有个想法"到"我有一整套平台成品"——一个人驱动一整支专业团队。

灵感来自 Karpathy 的 autoresearch 项目——将 AI 研究的自主迭代范式应用于播客视频制作领域。

## 特性

- **Agent Skills 驱动**：通过 SKILL 定义 7 个专业角色，Agent 自动编排工作流
- **全链路覆盖**：创意对话 → 制作加工 → 质量审核 → 发行出品
- **全自动 pipeline**：转录解析 → 字幕生成 → 勘误纠错 → 逐词校验 → 视频合成
- **双格式输出**：横版 16:9 + 竖版 9:16（模糊背景填充）
- **字幕零容忍**：重叠零容忍（一票否决）、准确率 ≥ 99.9%
- **逐词校验**：口音/含糊/吞字/ASR 混淆检测，200+ 条 ASR 语音纠错规则
- **四维度出品审核**：技术/文化/传播/影视制作，加权评分 + 一票否决
- **Autoresearch 自动迭代**：审核不通过时自动优化，最多 3 轮
- **多 Agent 兼容**：Claude Code / Trae / Hermes 均可通过 SKILL 调用

## Agent Skills

本项目通过 Agent Skills 开放标准（[agentskills.io](https://agentskills.io)）定义了两个核心技能：

### video-clip — 视频制作团队

7 个专业角色，按需自动切换：

| 角色 | 职责 |
|------|------|
| **制作人** | 创作对话、意图转化、工作流编排、autoresearch 驱动 |
| **策划总监** | 选题分析、内容策略、知识结构梳理 |
| **剪辑师** | 素材裁切、节奏把控、画面合成 |
| **字幕师** | ASR 纠错、字幕渲染、样式设计 |
| **声音设计师** | 降噪、响度标准化、呼吸音处理 |
| **包装师** | 片头片尾、水印、封面、元数据 |
| **出品人** | 多平台导出、素材打包、版权声明 |

5 条工作流覆盖完整链路：

| 工作流 | 场景 |
|--------|------|
| Workflow 0: 制作人对话 | 创意对话 → 意图转化 → 蓝图确认 → 执行编排 |
| Workflow 1: 一期一剪 | 完整播客 → 精剪长视频 |
| Workflow 2: 内容原子化 | 长视频 → 多个独立短视频 |
| Workflow 3: 知识混剪 | 多期素材 → 主题系列 |
| Workflow 4: 全平台出品 | 成品 → 6 平台适配导出 |
| Workflow 5: 素材库打包 | 全部产出物 → 标准化交付 |

### quality-audit — 出品审核

独立于制作团队的审核人，四维度审核 + autoresearch 反馈闭环：

- **技术质量**：视频/音频/字幕技术参数检查
- **文化质量**：内容准确性、文化敏感性、叙事质量
- **传播质量**：钩子强度、独立可理解、平台适配
- **影视制作质量**：剪辑节奏、声音设计、视觉呈现

审核不通过时，自动向制作人反馈结构化修复指令，触发 autoresearch 优化迭代。

## 快速开始

### 安装

```bash
pip install git+https://github.com/tyouter/auto-podcast-slicer.git
```

需要 FFmpeg 在 PATH 中可用。

验证安装：

```bash
garden --help
```

### 创建项目

```bash
# 使用空白模板创建
python -c "from tools.project_manager import create_project; create_project('my-podcast', 'path/to/media.mp3')"

# 或使用 CLI
garden status --project-dir /path/to/new-project
```

### 生成视频

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
```

### 通过 Agent 使用

#### Claude Code / Trae

在项目目录下直接对话，SKILL 自动激活：

```
"帮我从这期播客中剪出5个短视频"
"审核一下生成的视频质量"
"创建一个新的播客项目"
```

#### Hermes

```bash
# 安装 SKILL
hermes skills install tyouter/auto-podcast-slicer

# 对话使用
hermes chat -q "Use the video-clip skill to produce 5 short clips from my podcast"
```

## 项目结构

```
auto-podcast-slicer/
├── pipeline/                    # 核心 pipeline
│   ├── clip_processor.py        # 切片处理（process_clip / process_series）
│   ├── text_normalizer.py       # 文本规范化（繁简转换、著→着、标点修正）
│   ├── subtitle_formatter.py    # 字幕格式化（断行、禁则、行长控制）
│   ├── subtitle_renderer.py     # 字幕渲染（圆角背景ASS、毛玻璃滤镜）
│   ├── errata_engine.py         # 勘误引擎（项目级 errata.yaml + 框架级规则）
│   ├── content_validator.py     # 内容验证（语义异常、上下文纠错、重叠零容忍）
│   ├── quality_checker.py       # 质量检查（四维度评分、一票否决）
│   ├── loudness_normalizer.py   # 响度标准化
│   ├── exporter.py              # 多平台导出
│   └── ...
├── autoresearch/                # 自动迭代框架
│   ├── strategies.py            # 改进策略库（15个策略）
│   ├── metrics.py               # 质量指标
│   └── experiment.py            # 实验运行器
├── skills/                      # Agent Skills（agentskills.io 标准）
│   ├── video-clip/              # 视频制作团队 SKILL
│   │   ├── SKILL.md             # 主指令
│   │   └── references/          # API 参考
│   └── quality-audit/           # 出品审核 SKILL
│       ├── SKILL.md
│       └── references/
├── config/                      # 框架默认配置
│   ├── platforms.yaml           # 6 平台规格
│   └── quality_standards.yaml   # 质量标准
├── templates/                   # 项目模板
├── tools/
│   ├── cli.py                   # garden CLI 入口
│   └── project_manager.py       # 项目管理工具
└── make_clips.py                # 快捷脚本
```

## 质量标准

### 一票否决项

| 检查项 | 标准 |
|--------|------|
| 字幕准确率 | ≥ 99.9% |
| 字幕重叠 | 零容忍，任意两条时间区间无交集 |
| 音视频同步 | 偏差 ≤ 50ms |
| 竖版画面 | 不裁剪原始画面（模糊背景填充） |
| 事实性错误 | 零容忍 |
| 歧视性内容 | 零容忍 |

### 审核评分

```
总分 = Σ(各检查项得分 × 权重)

通过线：≥ 85 分
警告线：70-84 分（有条件通过）
不通过：< 70 分
```

## Autoresearch 策略

| 策略 | 说明 |
|------|------|
| `improve_cut_points` | 优化切点位置 |
| `improve_crossfade` | 增加交叉淡化 |
| `improve_subtitle_errata` | 增强勘误覆盖 |
| `zero_tolerance_subtitle_overlap` | 字幕重叠零容忍 |
| `word_level_verification` | 逐词校验 |
| ... | 共 15 个策略 |

查看全部策略：

```bash
garden strategies
```

## 许可

MIT License
