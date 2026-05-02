# Garden AutoResearch

播客视频自动化制作框架。将一期播客录制素材自动切分为多个短视频，配备字幕、竖版适配、质量校验，并通过 autoresearch 机制持续迭代优化。

灵感来自 Karpathy 的 autoresearch 项目——将 AI 研究的自主迭代范式应用于播客视频制作领域。

## 特性

- 全自动 pipeline：转录解析 → 字幕生成 → 勘误纠错 → 逐词校验 → 视频合成
- 多系列输出：高光/哲思/精彩对话/深度思考/沉浸式场域
- 双格式：横版 16:9 + 竖版 9:16（模糊背景填充）
- 字幕重叠零容忍（一票否决）
- 逐词校验：口音/含糊/吞字/ASR混淆检测
- 200+ 条 ASR 语音纠错规则
- 四维度出品审核（技术/文化/传播/影视制作）
- Autoresearch 自动迭代优化
- 外部项目支持：每个播客项目独立管理

## 快速开始

### 安装

```bash
git clone <repo-url>
cd garden-autoresearch
pip install -e .
```

需要 FFmpeg 在 PATH 中可用。

### 创建项目

```bash
# 使用空白模板创建
python tools/project_manager.py create "我的播客" --template blank

# 基于示例模板创建
python tools/project_manager.py create "我的播客" --template garden-forking-paths
```

### 配置项目

编辑项目目录下的 `project.yaml`：

```yaml
name: "我的播客项目"
description: "项目描述"

sources:
  transcript: "/path/to/transcript.json"
  audio: "/path/to/audio.wav"
  video: "/path/to/video.mp4"

output:
  base_dir: "/path/to/output"

clips:
  highlights:
    - id: H01
      title: "标题"
      series: 高光
      start_s: 100
      end_s: 150
      hook: "钩子文本"
      domain: 主题
```

可选创建 `corrections.yaml` 定义自定义勘误：

```yaml
corrections:
  错误词: 正确词
```

### 生成视频

```bash
# 生成切片视频（统一CLI）
python make_clips.py --project /path/to/my-podcast

# 使用内嵌配置（向后兼容）
python make_clips.py
```

### 使用 Claude Code

在 Claude Code 中打开本仓库，直接对话即可：

```
"帮我从这期播客中剪出5个短视频"
"审核一下生成的视频质量"
"创建一个新的播客项目"
```

## 项目结构

```
garden-autoresearch/
├── pipeline/                    # 核心 pipeline
│   ├── config.py                # 配置管理（支持外部项目）
│   ├── loader.py                # 项目加载器
│   ├── text_normalizer.py       # 文本规范化（繁简转换、著→着、标点修正）
│   ├── subtitle_formatter.py    # 字幕行格式化（断行、禁则、行长控制）
│   ├── subtitle_renderer.py     # 字幕渲染（圆角背景ASS、毛玻璃滤镜）
│   ├── errata_engine.py         # 勘误引擎（项目级 errata.yaml + 框架级规则）
│   ├── content_validator.py     # 内容验证（语义异常检测、上下文纠错）
│   ├── clip_processor.py        # 统一切片处理
│   ├── word_verifier.py         # 逐词校验模块
│   ├── subtitle_content.py      # 字幕处理入口（整合上述模块）
│   ├── subtitle_verifier.py     # 字幕验证
│   ├── subtitle_merger.py       # 字幕合并
│   ├── quality_checker.py       # 质量检查
│   └── ...
├── autoresearch/                # 自动迭代框架
│   ├── strategies.py            # 改进策略库
│   ├── metrics.py               # 质量指标
│   └── experiment.py            # 实验运行器
├── config/                      # 框架默认配置
├── projects/                    # 外部项目目录
│   └── garden-forking-paths/    # 《小径分岔的花园》项目
│       ├── project.yaml         # 项目配置
│       ├── errata.yaml          # 项目级勘误表
│       └── clips.yaml           # 项目级切片定义
├── templates/                   # 项目模板
│   ├── blank/                   # 空白模板
│   └── garden-forking-paths/    # 示例模板
├── tools/
│   └── project_manager.py       # 项目管理工具
├── .claude/skills/              # Claude Code SKILL
│   ├── video-clip/              # 视频制作团队
│   └── quality-audit/           # 出品审核
└── make_clips.py                # 统一切片生成CLI
```

## 质量标准

### 一票否决项

| 检查项 | 标准 |
|--------|------|
| 字幕准确率 | >= 99.9% |
| 字幕重叠 | 零容忍，任意两条时间区间无交集 |
| 音视频同步 | 偏差 <= 50ms |
| 竖版画面 | 不裁剪原始画面（模糊背景填充） |
| 事实性错误 | 零容忍 |
| 歧视性内容 | 零容忍 |

### 逐词校验

`pipeline/word_verifier.py` 提供：
- 正向最大匹配分词（1152词内置词典）
- 5组语境消歧规则
- 平翘舌/韵母混淆检测
- 吞字/口吃检测

## Autoresearch 策略

| 策略 | 说明 |
|------|------|
| `improve_cut_points` | 优化切点位置 |
| `improve_crossfade` | 增加交叉淡化 |
| `improve_subtitle_errata` | 增强勘误覆盖 |
| `zero_tolerance_subtitle_overlap` | 字幕重叠零容忍 |
| `word_level_verification` | 逐词校验 |
| ... | 共15个策略 |

## 许可

MIT License
