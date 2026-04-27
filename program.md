# Garden AutoResearch — 播客视频制作自主研究框架

> 灵感来源：Karpathy 的 autoresearch 项目。将 AI 研究的自主迭代范式应用于播客视频制作领域。
> 核心理念：Agent 自主修改 pipeline 参数 → 运行实验 → 测量质量 → 保留或丢弃改进 → 持续迭代。

## 你的角色

你是一个自主研究 Agent，负责持续改进播客视频制作 pipeline 的质量。你的工作方式是：

1. **读取当前 pipeline 状态** — 了解当前配置和最近的实验结果
2. **分析问题** — 从质量报告中识别需要改进的方向
3. **选择策略** — 从预定义策略中选择或自行设计改进方案
4. **运行实验** — 修改配置参数，运行 pipeline，测量结果
5. **评估结果** — 比较改进前后的质量指标
6. **决策保留/丢弃** — 如果改进则保留，否则回滚
7. **记录发现** — 将实验结果和洞察写入日志

## 项目结构

```
.
├── program.md              ← 你正在读的文件（Agent 指令）
├── pipeline/               ← 核心 pipeline 模块（你主要修改配置参数，不直接修改代码）
│   ├── config.py           ← 配置管理
│   ├── ingest.py           ← 素材导入
│   ├── transcribe.py       ← 语音转录
│   ├── topic_analysis.py   ← 主题分析
│   ├── clip_planning.py    ← 切片策划
│   ├── audio_processor.py  ← 音频处理（切分、交叉淡化、呼吸处理）
│   ├── subtitle_generator.py ← 字幕生成
│   ├── subtitle_verifier.py  ← 字幕校验
│   ├── audio_verifier.py   ← 音频校验
│   ├── loudness_normalizer.py ← 响度标准化
│   ├── video_processor.py  ← 视频处理
│   ├── exporter.py         ← 多平台导出
│   └── quality_checker.py  ← 质量终检
├── autoresearch/           ← 自主研究框架
│   ├── metrics.py          ← 质量指标计算
│   ├── experiment.py       ← 实验运行器
│   ├── strategies.py       ← 改进策略库
│   └── logger.py           ← 研究日志
├── config/                 ← 配置文件
│   ├── default.yaml        ← 默认 pipeline 配置
│   ├── platforms.yaml      ← 平台规格
│   └── quality_standards.yaml ← 行业质量标准
├── tools/                  ← CLI 工具
│   └── cli.py              ← 命令行入口
└── output/                 ← 输出目录
```

## 核心质量指标

pipeline 的质量由以下指标衡量（满分100分）：

| 指标类别 | 权重 | 关键子指标 |
|---------|------|-----------|
| 音频质量 | 60% | 响度合规(LUFS)、真峰值(dBTP)、切点质量、呼吸处理 |
| 字幕质量 | 40% | 时间轴合规、阅读速度、行长度、重叠检测 |

### 音频质量关键检查项

1. **切点质量** — 无突兀进入、无截断式结尾、气口合适
2. **响度标准** — 目标 -14 LUFS（流媒体）/ -16 LUFS（播客），真峰值 ≤ -1 dBTP
3. **呼吸处理** — 降低音量而非删除，保留自然感
4. **交叉淡化** — 切点处平滑过渡，消除爆音

### 字幕质量关键检查项

1. **时间轴** — 最短1秒、最长7秒、间隔≥67ms、无重叠
2. **阅读速度** — 中文≤4字/秒
3. **行长度** — 每行≤15字（中文），最多2行
4. **文本质量** — 无空字幕、无过长文本、有适当标点

## 改进策略

当你需要改进 pipeline 时，可以从以下策略中选择：

### 低风险策略（优先尝试）

1. **improve_cut_points** — 优化切点位置，增加静音检测搜索范围
2. **improve_crossfade** — 增加交叉淡化时长，使过渡更平滑
3. **improve_breath_handling** — 优化呼吸声处理参数
4. **improve_subtitle_timing** — 调整字幕时间参数
5. **improve_subtitle_readability** — 优化字幕可读性

### 中风险策略（低风险无效时尝试）

6. **improve_loudness_target** — 调整响度目标
7. **improve_topic_segmentation** — 调整主题分割参数
8. **improve_clip_duration** — 优化切片时长范围

### 自定义策略

你也可以自行设计改进策略。原则：
- 每次只修改1-3个参数
- 记录修改理由
- 测量改进效果

## 实验流程

每次实验遵循以下步骤：

```
1. 读取当前配置 → config/default.yaml
2. 读取最近实验日志 → output/experiments/experiment_log.json
3. 分析当前质量问题 → 从 quality_report.json 读取
4. 选择改进策略 → 从 strategies.py 或自行设计
5. 修改配置参数 → 通过 config.set() 修改
6. 运行 pipeline → python -m tools.run_pipeline
7. 测量质量 → 读取新的 quality_report.json
8. 比较前后指标 → autoresearch.metrics.compare_metrics()
9. 决策：改进→保留配置 | 退步→回滚配置
10. 记录实验 → experiment_log.json
```

## 行业质量标准参考

### 音频标准
- **EBU R128**: 目标 -23 LUFS, 真峰值 -1 dBTP, LRA ≤ 15 LU
- **流媒体通用**: 目标 -14 LUFS, 真峰值 -1 dBTP, LRA ≤ 10 LU
- **播客通用**: 目标 -16 LUFS, 真峰值 -1 dBTP
- **呼吸声处理**: 降至 -18~-24 dB，保留 30%-50%
- **交叉淡化**: 最短 3-5ms（消除爆音），推荐 10-50ms（自然过渡）
- **J-Cut/L-Cut**: 音频先于/延后画面 3-10 帧

### 字幕标准
- **SRT 格式**: UTF-8, 时间码 HH:MM:SS,mmm
- **显示时长**: 最短 1s, 最长 7s
- **间隔**: ≥ 67ms (2帧@30fps)
- **阅读速度**: 中文 3-4 字/秒
- **行限制**: 最多 2 行, 中文每行 ≤ 15 字
- **安全区域**: 标题安全区 10%, 动作安全区 5%

### 视频标准
- **色彩空间**: Rec.709 (SDR)
- **编码**: H.264 High Profile, CRF 18-20
- **像素格式**: yuv420p
- **音频**: AAC 192kbps, 48kHz, 立体声

## 运行命令

```bash
# 安装依赖
uv sync

# 运行完整 pipeline
uv run python -m tools.run_pipeline --source <video_path>

# 运行单个实验
uv run python -m tools.run_experiment --strategy improve_cut_points

# 查看实验历史
uv run python -m tools.cli status

# 查看质量报告
uv run python -m tools.cli report
```

## 注意事项

1. **不要修改 pipeline 代码** — 只修改配置参数（config/default.yaml 中的值）
2. **每次实验只改1-3个参数** — 便于定位改进来源
3. **记录所有实验** — 即使失败的实验也有价值
4. **关注 critical issues** — 这些是必须解决的问题
5. **响度和真峰值是不可妥协的底线** — 必须符合行业标准
6. **切点质量是用户体验的核心** — 突兀的进入/截断是最严重的问题

## 研究方向建议

以下是目前最值得探索的方向（按优先级排序）：

1. **切点优化** — 如何在自动切分时确保气口合适、无突兀进入/截断
2. **呼吸声处理** — 如何在保留自然感和消除干扰之间找到最佳平衡
3. **字幕时间轴** — 如何自动调整字幕时间使其既合规又不丢失信息
4. **主题完整性** — 如何确保切片不丢失更好的开头与结尾上下文
5. **多平台适配** — 如何一次制作适配多个平台的规格要求
