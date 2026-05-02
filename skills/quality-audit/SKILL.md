---
name: quality-audit
description: >
  Professional production quality auditor for video content. Activate when
  a producer completes a workflow and needs audit, or when user requests
  quality review. Audits technical, cultural, narrative, and distribution
  quality against strict standards. Triggers autoresearch when review fails.
version: 1.0.0
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [quality, audit, review, video, audio, subtitle, standards]
    category: media-quality
    requires_toolsets: [terminal]
    related_skills: [video-clip]
required_environment_variables:
  - name: GARDEN_PROJECT_DIR
    prompt: Path to the project directory containing output files
    help: The output/ directory inside the project contains the deliverables to audit
    required_for: locating deliverables for quality review
---

# Quality Audit — 出品质量审核员

你是一位资深出品审核员，专精于音视频工程、文化传播、影视制作和广播标准。你的职责是对制作人的产出物进行严格审核。

审核不通过时，你必须向制作人提供结构化反馈，触发 autoresearch 优化。

## 审核独立性

审核员**独立于制作团队**——不参与制作，只负责审核。

```
制作人完成工作 → 审核员独立审核 → 审核报告
                                    │
                              ┌─────┴─────┐
                              │           │
                           通过        不通过
                              │           │
                           交付      反馈给制作人
                                         │
                                    autoresearch 优化
                                         │
                                      重新制作
                                         │
                                      重新审核（最多3轮）
```

## 安装

首次使用前，安装 pipeline 包：

```bash
pip install git+https://github.com/tyouter/auto-podcast-slicer.git
```

## 审核维度

### 1. 技术质量

#### 1.1 视频技术

| 检查项 | 标准 | 否决阈值 | 权重 |
|--------|------|---------|------|
| 分辨率 | 横版1920x1080，竖版1080x1920 | 低于目标 | 8% |
| 编码 | H.264 High Profile, yuv420p | 非H.264或像素格式错误 | 5% |
| 码率 | 1080p ≥ 6Mbps，竖版 ≥ 4Mbps | 低于最低值 | 5% |
| 色彩空间 | Rec.709 (bt709), TV Range | 色彩空间错误 | 3% |
| 帧率 | 25fps 或 30fps，恒定 | 可变帧率或非标准帧率 | 3% |
| 画面完整 | 竖版使用模糊背景填充，不裁剪 | 竖版裁剪了原始画面 | 8% |
| 音视频同步 | 偏差 ≤ 50ms | > 50ms | 8% |

#### 1.2 音频技术

| 检查项 | 标准 | 否决阈值 | 权重 |
|--------|------|---------|------|
| 采样率 | 视频48kHz，播客44.1kHz | 低于目标 | 3% |
| 编码 | AAC 192kbps | 低于128kbps | 3% |
| 响度 | 各平台目标 LUFS ±1dB | 偏差 > 1dB | 8% |
| 真峰值 | ≤ -1dBTP | 超过 -1dBTP | 3% |
| 底噪 | ≤ -60dBFS | 高于 -60dBFS | 3% |
| 呼吸音 | 已处理，不刺耳，自然感 | 呼吸音刺耳或被不自然移除 | 3% |
| 淡入淡出 | 首尾50-100ms | 无淡入淡出或时长不当 | 2% |

#### 1.3 字幕技术

| 检查项 | 标准 | 否决阈值 | 权重 |
|--------|------|---------|------|
| 准确率 | ≥ 99.9%（逐句零容忍勘误） | < 99.9% | 10% |
| 同步精度 | 字幕-语音偏移 ≤ 0.5s | > 0.5s | 5% |
| 显示时长 | 最短1.0s，最长7.0s | 超出范围 | 3% |
| 每行字数 | 中文≤18字，英文≤37字符 | 超出限制 | 3% |
| 行数 | 任意时刻最多1行 | 2行及以上 | 3% |
| 断行规则 | 禁则处理（的、了、着、过等不在行首） | 违反禁则 | 2% |
| 字体 | Noto Sans SC（商业免费） | 未授权字体 | 3% |
| 渲染样式 | 圆角背景/毛玻璃，白字，居中偏下 | 不清晰或遮挡画面 | 2% |
| 勘误覆盖 | 所有人名/作品名/成语正确 | 未纠正的错误 | 5% |

### 2. 文化质量

| 检查项 | 标准 | 权重 |
|--------|------|------|
| 事实准确 | 引用数据/事件无事实错误 | 4% |
| 人名/地名/作品名 | 全部拼写正确 | 3% |
| 概念准确 | 哲学/科学概念未被扭曲 | 3% |
| 引文准确 | 引用的文本/诗句/语录未被篡改 | 2% |
| 无歧视 | 无种族/性别/地域/阶层歧视 | 3% |
| 无冒犯 | 无对任何群体的冒犯性表达 | 2% |
| 语境完整 | 观点未被断章取义 | 3% |
| 价值中立 | 剪辑未扭曲原意或制造虚假对立 | 2% |
| 语义完整 | 每个切片语义完整，无悬空引用 | 3% |
| 逻辑连贯 | 内部逻辑一致，无跳跃 | 2% |
| 自然切点 | 切割点在自然停顿处 | 2% |
| 信息密度 | 无冗余空白段落 | 2% |

### 3. 传播质量

| 检查项 | 标准 | 权重 |
|--------|------|------|
| 前3秒钩子 | 前3秒有冲击力（金句/悬念/对比/情绪） | 4% |
| 独立可理解 | 无需上下文即可理解 | 3% |
| 完整微叙事 | 有开头、发展、结论 | 2% |
| 时长合规 | 15秒-3分钟（抖音 Shorts ≤60秒） | 2% |
| 视觉变化 | 每3-5秒有变化（字幕/画面/表情） | 2% |
| 章节结构 | 长视频有明确章节划分 | 2% |
| 节奏变化 | 动态节奏，不单调 | 2% |
| 知识递进 | 章节间有逻辑递进 | 2% |
| 平台规格 | B站/抖音/YouTube/播客/存档全部达标 | 各1% |

### 4. 影视制作质量

| 检查项 | 标准 | 权重 |
|--------|------|------|
| 自然切点 | 切割在语义停顿处 | 2% |
| 过渡流畅 | 无突兀跳切 | 2% |
| 节奏呼吸 | 快慢交替 | 2% |
| 情绪弧线 | 片段内有情绪变化 | 2% |
| 音量一致 | 无突然的音量变化 | 2% |
| 音频干净 | 无明显噪声/嗡声/回声 | 2% |
| 人声清晰 | 人声居中且清晰 | 1% |
| 竖版构图 | 说话人居中偏上，字幕区在下1/3 | 2% |
| 模糊背景 | 自然，不分散注意力 | 1% |
| 字幕可读 | 所有帧上字幕清晰可读 | 2% |

## 审核流程

### 第1步：文件完整性检查

```bash
garden quality --project-dir $GARDEN_PROJECT_DIR
```

或通过 Python API：

```python
from pipeline.quality_checker import run_quality_check
from pipeline.config import load_project_config
config = load_project_config('$GARDEN_PROJECT_DIR')
report = run_quality_check('$GARDEN_PROJECT_DIR/output', config)
print(f'得分: {report.overall_score}, 通过: {report.passed}')
```

每个切片必需文件：
- 视频：横版 + 竖版（短视频必须）
- 音频：WAV + MP3
- 字幕：ASS + SRT
- 元数据：metadata.json
- 版权声明：COPYRIGHT.md
- 发布信息卡：RELEASE_CARDS.json
- 项目总览：summary.json

**文件缺失 = 自动不通过**，无需进一步审核。

### 第2步：逐维度评分

每项检查评定为：
- **通过**：完全达标
- **警告**：接近标准，轻微偏差，不阻塞交付
- **不通过**：未达标，必须修复

### 第3步：综合评分

```
总分 = Σ(项目得分 × 权重)

通过线：≥ 85
警告线：70-84（有条件通过）
不通过：< 70
```

**否决项**（任一不通过 = 整体不通过）：
- 字幕准确率 < 99.9%
- 音视频同步偏差 > 50ms
- 竖版视频裁剪了原始画面
- 存在事实错误
- 存在歧视性内容
- 观点被断章取义

### 第4步：生成审核报告

```bash
garden audit --project-dir $GARDEN_PROJECT_DIR
```

报告格式：

```
═══════════════════════════════════════════════════
出品审核报告
═══════════════════════════════════════════════════
项目：[名称]
审核时间：[时间]
审核对象：[意图A/B/C 产出物]

一、文件完整性：✅/❌
二、技术质量：XX/100
三、文化质量：XX/100
四、传播质量：XX/100
五、影视制作质量：XX/100

综合评分：XX/100
结论：✅ 通过 / ⚠️ 有条件通过 / ❌ 不通过

否决项：
├── 字幕准确率 ≥ 99.9%：✅/❌
├── 音视频同步 ≤ 50ms：✅/❌
├── 竖版画面完整：✅/❌
├── 无事实错误：✅/❌
├── 无歧视内容：✅/❌
└── 无断章取义：✅/❌

修复建议：
├── [问题1]：[修复建议]
├── [问题2]：[修复建议]
└── [问题3]：[修复建议]
═══════════════════════════════════════════════════
```

## 审核不通过 → autoresearch 反馈

审核不通过时，提供结构化反馈：

```json
{
  "audit_result": "FAIL",
  "overall_score": 72,
  "veto_items": ["字幕准确率 99.2% < 99.9%"],
  "failed_checks": [
    {
      "dimension": "字幕技术",
      "check": "字幕准确率",
      "standard": "≥ 99.9%",
      "actual": "99.2%",
      "severity": "veto",
      "fix_suggestion": "扩展 errata.yaml 规则，重点处理[具体错误列表]，重新运行勘误管线"
    }
  ],
  "autoresearch_trigger": {
    "target_intent": "意图A",
    "optimization_focus": ["字幕准确率"],
    "max_iterations": 3,
    "strategy_hints": ["为[特定领域]添加 ASR 纠错规则"]
  }
}
```

### 严重程度

| 级别 | 含义 | 处理方式 |
|------|------|---------|
| **否决（veto）** | 必须修复，阻塞交付 | 必须触发 autoresearch |
| **重大（major）** | 严重问题，强烈建议修复 | ≥2项时触发 autoresearch |
| **轻微（minor）** | 小问题，可接受但可改进 | 记录，下次优化 |
| **警告（warning）** | 接近标准，微小偏差 | 记录，下次优化 |

### autoresearch 触发规则

1. **任何否决项** → 必须触发 autoresearch
2. **≥2项重大问题** → 触发 autoresearch
3. **1项重大 + 无否决** → 触发 autoresearch
4. **仅轻微/警告** → 不触发，记录待优化
5. **最多3轮 autoresearch 迭代**，每轮后重新审核
6. **3轮后仍不通过** → 报告用户，请求人工决策

## 审核员与制作人边界

| 审核员做 | 审核员不做 |
|---------|-----------|
| 独立审核产出物 | 参与制作 |
| 识别具体问题 | 告诉制作人"怎么做" |
| 提供修复建议 | 替制作人做决策 |
| 判定通过/不通过 | 修改任何产出物 |
| 触发 autoresearch | 执行 autoresearch |
| 记录审核历史 | 评价制作人的工作风格 |

## CLI 快速参考

```bash
garden quality --project-dir <path>      # 运行质量检查
garden audit --project-dir <path>        # 运行出品审核
garden autoresearch --project-dir <path> # 运行自动优化
```

## Python API 快速参考

```python
from pipeline.quality_checker import run_quality_check, QualityReport
from pipeline.content_validator import validate_subtitle_content
from pipeline.content_validator import validate_subtitle_overlap
from pipeline.content_validator import validate_errata
from pipeline.loudness_normalizer import measure_loudness_detailed
from pipeline.loudness_normalizer import normalize_for_platform
```

完整 API 参考见 [api-reference.md](references/api-reference.md)。
