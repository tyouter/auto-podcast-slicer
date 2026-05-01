# Garden AutoResearch — 播客视频自动化制作框架

> 将一期播客录制素材自动切分为多个短视频，配备字幕、竖版适配、质量校验，并通过 autoresearch 机制持续迭代优化。

## 项目架构

```
garden-autoresearch/                ← 框架（本仓库）
├── pipeline/                       ← 核心 pipeline 模块
│   ├── config.py                   ← 配置管理（支持外部项目加载）
│   ├── loader.py                   ← 项目加载器
│   ├── word_verifier.py            ← 逐词校验模块
│   ├── subtitle_content.py         ← 字幕处理（勘误/纠错/逐词校验）
│   ├── subtitle_verifier.py        ← 字幕验证
│   └── ...
├── autoresearch/                   ← 自动迭代研究框架
├── config/                         ← 框架默认配置
│   ├── default.yaml                ← 默认 pipeline 参数
│   ├── platforms.yaml              ← 平台规格
│   └── quality_standards.yaml      ← 质量标准
├── templates/                      ← 项目模板
│   ├── blank/                      ← 空白模板
│   └── garden-forking-paths/       ← 《小径分岔的花园》模板
├── tools/
│   └── project_manager.py          ← 项目管理工具
├── make_short_videos_v2.py         ← 短视频生成脚本
├── make_full_project.py            ← 全项目生成脚本
├── make_wiki_clips.py              ← Wiki系列生成脚本
└── .claude/skills/                 ← Claude Code SKILL
    ├── video-clip/SKILL.md         ← 视频制作团队 SKILL
    └── quality-audit/SKILL.md      ← 出品审核 SKILL
```

## 外部项目结构

每个播客/视频项目是一个独立目录，只需包含：

```
my-podcast-project/
├── project.yaml        ← 项目配置（素材源 + 切片定义）
├── corrections.yaml    ← 自定义勘误表（可选）
└── output/             ← 自动生成的输出目录
```

### project.yaml 格式

```yaml
name: "我的播客项目"
description: "项目描述"

sources:
  transcript: "/path/to/transcript.json"   # FunASR转录结果
  audio: "/path/to/audio.wav"              # 音频文件
  video: "/path/to/video.mp4"              # 视频文件

output:
  base_dir: "/path/to/my-podcast-project/output"

clips:
  highlights:                              # 系列名（自定义）
    - id: H01_my_clip
      title: "剪辑标题"
      series: 系列名
      description: "剪辑描述"
      start_s: 1580                        # 开始时间（秒）
      end_s: 1610                          # 结束时间（秒）
      hook: "前3秒钩子文本"
      domain: 主题域
```

## 使用方式

### 1. 创建新项目

```bash
python tools/project_manager.py create "我的播客" --template blank --dir /path/to/my-podcast
```

### 2. 编辑 project.yaml

填写素材路径和切片定义。

### 3. 生成视频

```bash
# 生成短视频（高光+哲思+精彩对话）
python make_short_videos_v2.py --project /path/to/my-podcast

# 生成全部系列
python make_full_project.py --project /path/to/my-podcast

# 生成Wiki系列
python make_wiki_clips.py --project /path/to/my-podcast
```

### 4. 使用内嵌项目（向后兼容）

不传 `--project` 时使用框架内置的 config/ 目录配置：

```bash
python make_short_videos_v2.py
```

## Claude Code 对话触发

在 Claude Code 中打开本仓库后，可以直接对话：

- "帮我从这期播客中剪出5个短视频" → 触发 video-clip SKILL
- "审核一下生成的视频质量" → 触发 quality-audit SKILL
- "创建一个新的播客项目" → 使用 project_manager.py

## 质量保障

- 字幕重叠零容忍（一票否决）
- 逐词校验（口音/含糊/吞字检测）
- ASR语音纠错（200+条规则）
- 出品审核（技术/文化/传播/影视制作 四维度）

## 依赖

```
Python >= 3.10
FFmpeg (需在 PATH 中)
pyyaml, rich, click, srt, pydub
```
