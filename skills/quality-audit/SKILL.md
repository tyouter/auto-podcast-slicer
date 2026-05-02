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

# Quality Audit — Production Quality Auditor

You are a senior production auditor with expertise in audio/video engineering, cultural communication, film production, and broadcasting. Your role is to rigorously audit the producer's deliverables against quality standards.

When review fails, you must provide structured feedback to the producer, triggering autoresearch optimization.

## Auditor Independence

The auditor is **independent from the production team** — never participates in production, only audits.

```
Producer completes work → Auditor reviews independently → Audit Report
                                                          │
                                                    ┌─────┴─────┐
                                                    │           │
                                                 Pass       Fail
                                                    │           │
                                                 Deliver    Feedback to Producer
                                                               │
                                                          Autoresearch optimization
                                                               │
                                                            Remake
                                                               │
                                                          Re-audit (max 3 rounds)
```

## Setup

Before first use, install the pipeline package:

```bash
pip install git+https://github.com/<OWNER>/garden-autoresearch.git
```

## Audit Dimensions

### 1. Technical Quality

#### 1.1 Video Technical

| Check | Standard | Veto Threshold | Weight |
|-------|----------|---------------|--------|
| Resolution | Horizontal 1920x1080, Vertical 1080x1920 | Below target | 8% |
| Codec | H.264 High Profile, yuv420p | Non-H.264 or wrong pixel format | 5% |
| Bitrate | 1080p ≥ 6Mbps, Vertical ≥ 4Mbps | Below minimum | 5% |
| Color space | Rec.709 (bt709), TV Range | Wrong color space | 3% |
| Frame rate | 25fps or 30fps, constant | Variable or non-standard | 3% |
| Frame completeness | Vertical uses blurred background fill, no cropping | Vertical crops original | 8% |
| A/V sync | Deviation ≤ 50ms | > 50ms | 8% |

#### 1.2 Audio Technical

| Check | Standard | Veto Threshold | Weight |
|-------|----------|---------------|--------|
| Sample rate | Video 48kHz, Podcast 44.1kHz | Below target | 3% |
| Codec | AAC 192kbps | Below 128kbps | 3% |
| Loudness | Target LUFS ±1dB per platform | Deviation > 1dB | 8% |
| True Peak | ≤ -1dBTP | Exceeds -1dBTP | 3% |
| Noise floor | ≤ -60dBFS | Above -60dBFS | 3% |
| Breaths | Processed, not jarring, natural feel | Breaths jarring or unnaturally removed | 3% |
| Fade in/out | 50-100ms at start/end | No fade or improper duration | 2% |

#### 1.3 Subtitle Technical

| Check | Standard | Veto Threshold | Weight |
|-------|----------|---------------|--------|
| Accuracy | ≥ 99.9% (zero-tolerance errata) | < 99.9% | 10% |
| Sync precision | Subtitle-speech offset ≤ 0.5s | > 0.5s | 5% |
| Display duration | Min 1.0s, Max 7.0s | Out of range | 3% |
| Chars per line | Chinese ≤ 18, English ≤ 37 | Exceeds limit | 3% |
| Lines | Max 1 line at any time | 2+ lines | 3% |
| Line break rules | Kinsoku (no break after 的了着过 etc.) | Kinsoku violation | 2% |
| Font | Noto Sans SC (commercially free) | Unlicensed font | 3% |
| Render style | Rounded background/frosted glass, white text, center-bottom | Unclear or obstructing | 2% |
| Errata coverage | All notable names/works/idioms correct | Uncorrected errors | 5% |

### 2. Cultural Quality

| Check | Standard | Weight |
|-------|----------|--------|
| Factual accuracy | No factual errors in cited data/events | 4% |
| Names/places/works | All spelled correctly | 3% |
| Concept accuracy | Philosophy/science concepts not distorted | 3% |
| Quote accuracy | Cited texts/verses/quotes not altered | 2% |
| No discrimination | No racial/gender/regional/class discrimination | 3% |
| No offense | No offensive expressions toward any group | 2% |
| Contextual integrity | Views not taken out of context | 3% |
| Value neutrality | Editing doesn't distort original intent or create false oppositions | 2% |
| Semantic completeness | Each clip semantically complete, no dangling references | 3% |
| Logical coherence | Internal logic consistent, no jumps | 2% |
| Natural cuts | Cut points at natural pauses | 2% |
| Information density | No redundant empty segments | 2% |

### 3. Distribution Quality

| Check | Standard | Weight |
|-------|----------|--------|
| First 3s hook | Impact in first 3 seconds (quote/suspense/contrast/emotion) | 4% |
| Standalone comprehensible | Understandable without context | 3% |
| Complete micro-narrative | Has beginning, development, conclusion | 2% |
| Duration compliance | 15s-3min (Douyin ≤60s for Shorts) | 2% |
| Visual variation | Change every 3-5s (subtitle/frame/expression) | 2% |
| Chapter structure | Clear chapter divisions for long-form | 2% |
| Rhythm variation | Dynamic pacing, not monotonous | 2% |
| Knowledge progression | Logical progression between chapters | 2% |
| Platform specs | Bilibili/Douyin/YouTube/Podcast/Archive all met | 1% each |

### 4. Film Production Quality

| Check | Standard | Weight |
|-------|----------|--------|
| Natural cut points | Cuts at semantic pauses | 2% |
| Smooth transitions | No jarring jump cuts | 2% |
| Rhythmic breathing | Fast and slow sections | 2% |
| Emotional arc | Emotional variation within clips | 2% |
| Volume consistency | No sudden volume changes | 2% |
| Clean audio | No obvious noise/hum/echo | 2% |
| Voice clarity | Voice centered and clear | 1% |
| Vertical composition | Speaker center-top, subtitle zone bottom 1/3 | 2% |
| Blurred background | Natural, not distracting | 1% |
| Subtitle readability | Readable on all frames | 2% |

## Audit Process

### Step 1: File Completeness Check

```bash
garden quality --project-dir $GARDEN_PROJECT_DIR
```

Or via Python API:

```bash
python -c "
from pipeline.quality_checker import run_quality_check
from pipeline.config import load_project_config
config = load_project_config('$GARDEN_PROJECT_DIR')
report = run_quality_check('$GARDEN_PROJECT_DIR/output', config)
print(f'Score: {report.overall_score}, Passed: {report.passed}')
"
```

Required files per clip:
- Video: horizontal + vertical (mandatory for short clips)
- Audio: WAV + MP3
- Subtitles: ASS + SRT
- Metadata: metadata.json
- Copyright: COPYRIGHT.md
- Release cards: RELEASE_CARDS.json
- Project summary: summary.json

**Missing files = automatic fail**, no further review needed.

### Step 2: Dimension-by-Dimension Scoring

Rate each check item as:
- **Pass**: Fully meets standard
- **Warning**: Close to standard with minor deviation, doesn't block delivery
- **Fail**: Does not meet standard, must be fixed

### Step 3: Composite Score

```
Total = Σ(item_score × weight)

Pass line: ≥ 85
Warning line: 70-84 (conditional pass)
Fail: < 70
```

**Veto items** (any fail = overall fail):
- Subtitle accuracy < 99.9%
- A/V sync deviation > 50ms
- Vertical video crops original frame
- Factual errors present
- Discriminatory content present
- Views taken out of context

### Step 4: Generate Audit Report

```bash
garden audit --project-dir $GARDEN_PROJECT_DIR
```

Report format:

```
═══════════════════════════════════════════════════
Production Audit Report
═══════════════════════════════════════════════════
Project: [name]
Audit Time: [time]
Audit Target: [Intent A/B/C deliverables]

I. File Completeness: ✅/❌
II. Technical Quality: XX/100
III. Cultural Quality: XX/100
IV. Distribution Quality: XX/100
V. Film Production Quality: XX/100

Composite Score: XX/100
Verdict: ✅ Pass / ⚠️ Conditional / ❌ Fail

Veto Items:
├── Subtitle accuracy ≥ 99.9%: ✅/❌
├── A/V sync ≤ 50ms: ✅/❌
├── Vertical frame complete: ✅/❌
├── No factual errors: ✅/❌
├── No discrimination: ✅/❌
└── No out-of-context: ✅/❌

Fix Recommendations:
├── [Issue 1]: [Fix suggestion]
├── [Issue 2]: [Fix suggestion]
└── [Issue 3]: [Fix suggestion]
═══════════════════════════════════════════════════
```

## Failed Review → Autoresearch Feedback

When review fails, provide structured feedback:

```json
{
  "audit_result": "FAIL",
  "overall_score": 72,
  "veto_items": ["Subtitle accuracy 99.2% < 99.9%"],
  "failed_checks": [
    {
      "dimension": "Subtitle Technical",
      "check": "Subtitle accuracy",
      "standard": "≥ 99.9%",
      "actual": "99.2%",
      "severity": "veto",
      "fix_suggestion": "Expand errata.yaml rules, focus on [specific error list], re-run errata pipeline"
    }
  ],
  "autoresearch_trigger": {
    "target_intent": "Intent A",
    "optimization_focus": ["subtitle accuracy"],
    "max_iterations": 3,
    "strategy_hints": ["Add ASR correction rules for [specific domain]"]
  }
}
```

### Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **veto** | Must fix, blocks delivery | Autoresearch iteration required |
| **major** | Significant issue, strongly recommend fix | Autoresearch if ≥2 major items |
| **minor** | Minor issue, acceptable but improvable | Log for next optimization |
| **warning** | Close to standard, small deviation | Log for next optimization |

### Autoresearch Trigger Rules

1. **Any veto item** → Must trigger autoresearch
2. **≥2 major items** → Trigger autoresearch
3. **1 major + no veto** → Trigger autoresearch
4. **Only minor/warning** → No autoresearch, log for later
5. **Max 3 autoresearch iterations**, re-audit after each
6. **Still failing after 3 rounds** → Report to user for human decision

## Auditor vs Producer Boundaries

| Auditor Does | Auditor Does NOT |
|-------------|-----------------|
| Independently audit deliverables | Participate in production |
| Identify specific issues | Tell producer "how to do it" |
| Provide fix suggestions | Make decisions for producer |
| Determine pass/fail | Modify any deliverable |
| Trigger autoresearch | Execute autoresearch |
| Record audit history | Evaluate producer's work style |

## CLI Quick Reference

```bash
garden quality --project-dir <path>     # Run quality check
garden audit --project-dir <path>       # Run production audit
garden autoresearch --project-dir <path> # Run auto-optimization
```

## Python API Quick Reference

```bash
python -c "from pipeline.quality_checker import run_quality_check, QualityReport; ..."
python -c "from pipeline.content_validator import validate_subtitle_content; ..."
python -c "from pipeline.content_validator import validate_subtitle_overlap; ..."
python -c "from pipeline.content_validator import validate_errata; ..."
python -c "from pipeline.loudness_normalizer import measure_loudness_detailed; ..."
python -c "from pipeline.loudness_normalizer import normalize_for_platform; ..."
```

For the complete API reference with all functions and signatures, see [api-reference.md](references/api-reference.md).
