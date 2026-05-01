# Quick Start — 5分钟上手

## 前置条件

- Python >= 3.10
- FFmpeg 已安装并在 PATH 中
- 一期播客的素材文件：
  - 视频文件（.mp4）
  - 音频文件（.wav）
  - 转录文件（FunASR .json 格式）

## 第一步：安装框架

```bash
cd garden-autoresearch
pip install -e .
```

## 第二步：创建项目

```bash
python tools/project_manager.py create "我的播客"
```

这会在上一级目录创建 `我的播客/` 文件夹。

## 第三步：配置素材路径

编辑 `我的播客/project.yaml`，填写三个关键路径：

```yaml
sources:
  transcript: "D:/podcast/episode01_transcript.json"
  audio: "D:/podcast/episode01.wav"
  video: "D:/podcast/episode01.mp4"
```

## 第四步：定义切片

在 `project.yaml` 的 `clips` 部分，定义你想剪出的片段：

```yaml
clips:
  highlights:
    - id: H01_best_moment
      title: "最精彩的3分钟"
      series: 高光
      start_s: 300        # 第5分钟开始
      end_s: 480          # 第8分钟结束
      hook: "开头的金句"
      domain: 主题
```

> 如何确定 start_s / end_s？先看一遍视频记录时间点即可。

## 第五步：生成视频

```bash
python make_short_videos_v2.py --project "../我的播客"
```

等待生成完成（约1-3分钟/条）。

## 第六步：查看结果

```
我的播客/output/
├── 高光/
│   └── H01_best_moment/
│       ├── H01_best_moment_subtitled.mp4    # 横版
│       ├── H01_best_moment_vertical.mp4     # 竖版（抖音/Shorts）
│       ├── H01_best_moment.ass              # ASS字幕
│       ├── H01_best_moment.srt              # SRT字幕
│       └── metadata.json                    # 元数据
```

## 可选：添加勘误

如果 ASR 转录有识别错误，在项目目录创建 `corrections.yaml`：

```yaml
corrections:
  错误词: 正确词
  博赫斯: 博尔赫斯
```

重新运行生成脚本即可自动纠正。

## 使用 Claude Code（推荐）

在 Claude Code 中打开 `garden-autoresearch` 仓库，直接对话：

```
你: 帮我从这期播客中剪出5个最精彩的短视频

Claude: [启动 video-clip SKILL]
        → 与你对话理解需求
        → 自动生成创作蓝图
        → 执行生成
        → 调用 quality-audit 审核
        → 交付成品
```

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `python tools/project_manager.py create "名称"` | 创建项目 |
| `python tools/project_manager.py templates` | 查看模板 |
| `python tools/project_manager.py list` | 查看已注册项目 |
| `python make_short_videos_v2.py --project <dir>` | 生成短视频 |
| `python make_full_project.py --project <dir>` | 生成全部系列 |
| `python make_wiki_clips.py --project <dir>` | 生成Wiki系列 |
