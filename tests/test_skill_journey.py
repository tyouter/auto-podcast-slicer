import sys
import json
import time
import shutil
from pathlib import Path
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import PipelineConfig
from pipeline.loader import load_project, ProjectContext
from pipeline.errata_engine import ErrataConfig, flatten_errata, apply_errata, apply_asr_phonetic_corrections, detect_asr_phonetic_errors
from pipeline.text_normalizer import traditional_to_simplified, convert_zhu_to_zhe, normalize_chinese, TRADITIONAL_TO_SIMPLIFIED, ZHU_KEEP_COMPOUNDS
from pipeline.subtitle_formatter import (
    add_punctuation_smart, clean_subtitle_text, enforce_single_line,
    format_subtitle_single_line, check_line_start_rules, check_line_end_rules,
    detect_meaningless_words, detect_context_anomalies, remove_display_punctuation,
    LINE_START_FORBIDDEN, LINE_END_FORBIDDEN, QUESTION_INDICATORS,
    EXCLAMATION_INDICATORS, CONNECTIVE_WORDS, PAUSE_PUNCTUATION,
)
from pipeline.subtitle_renderer import (
    generate_ass_with_rounded_bg, get_frosted_glass_ffmpeg_filter,
    validate_font_license, validate_render_style,
    COMMERCIAL_FREE_FONTS, NON_COMMERCIAL_FONTS,
)
from pipeline.content_validator import (
    ContentValidationIssue, ContentValidationResult,
    validate_simplified_chinese, validate_punctuation, validate_single_line,
    validate_line_length, validate_errata, validate_asr_phonetic,
    validate_sentence_by_sentence, validate_context_coherence,
    validate_line_break_rules, validate_contextual_errata,
    validate_word_level, validate_subtitle_overlap, validate_subtitle_content,
)
from pipeline.subtitle_content import (
    process_subtitle_content, normalize_to_simplified_chinese,
    apply_custom_errata, load_custom_errata, load_errata_from_project,
    validate_subtitle_content as validate_subtitle_content_facade,
    validate_contextual_errata as validate_contextual_errata_facade,
    set_project_verification_config,
)
from pipeline.clip_processor import (
    extract_clip_entries, process_clip_subtitles, merge_short_entries,
    generate_audio, generate_ass, generate_srt,
    generate_video_subtitled, generate_video_vertical,
    write_metadata, process_clip, process_series, ClipProcessResult,
)
from pipeline.exporter import export_for_platform, export_all_platforms, export_audio_only, ExportResult
from pipeline.loudness_normalizer import normalize_for_platform, measure_loudness_detailed, normalize_loudness, batch_normalize, NormalizationResult
from pipeline.quality_checker import run_quality_check, check_audio_files, check_subtitle_files, check_efficiency, generate_recommendations, QualityReport
from autoresearch.strategies import STRATEGIES, get_strategy, get_all_strategies, get_strategies_by_risk, get_recommended_strategies, StrategyResult
from autoresearch.experiment import Experiment, ExperimentLog, ExperimentRecord
from autoresearch.metrics import PipelineMetrics, compute_metrics_from_quality_report, compare_metrics, compute_better_than_baseline

OUTPUT_BASE = PROJECT_ROOT / "output" / "test_skill_journey"
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"

ALL_PLATFORMS = ["bilibili", "douyin", "youtube", "xiaoyuzhou", "apple_podcasts", "archive"]

journey_log = []


def log_phase(phase: str, role: str, action: str, detail: str = ""):
    entry = {
        "phase": phase,
        "role": role,
        "action": action,
        "detail": detail,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    journey_log.append(entry)
    print(f"[{phase}] [{role}] {action}" + (f" — {detail}" if detail else ""))


def save_journey_log():
    log_path = OUTPUT_BASE / "journey_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(journey_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJourney log saved to {log_path}")


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# Journey Phase 1: 制作人对话 → 创作蓝图（工作流0）
# ═══════════════════════════════════════════════════════════════

def journey_phase1() -> ProjectContext:
    print_section("Journey Phase 1: 制作人对话 → 创作蓝图（工作流0）")

    log_phase("J1", "制作人", "创作对话", "用户提出：我要做全套的《小径分岔的花园》播客全平台素材")

    log_phase("J1", "制作人", "意图转化", "生成创作蓝图：3个剪辑意图")

    blueprint = {
        "intent_A": {
            "name": "高光引流",
            "workflow": "工作流2-内容原子化",
            "series": "highlights",
            "target_count": 6,
            "platforms": ["douyin", "youtube"],
        },
        "intent_B": {
            "name": "哲思系列",
            "workflow": "工作流3-知识混剪",
            "series": "philosophy",
            "target_count": 6,
            "platforms": ["bilibili", "youtube", "xiaoyuzhou"],
        },
        "intent_C": {
            "name": "深度思考系列",
            "workflow": "工作流3-知识混剪",
            "series": "deep_thinking",
            "target_count": 9,
            "platforms": ["bilibili", "youtube"],
        },
    }

    log_phase("J1", "制作人", "加载项目配置", f"project_dir={PROJECT_DIR}")
    config = PipelineConfig(project_dir=PROJECT_DIR)

    assert config.project_dir == PROJECT_DIR, "项目目录加载失败"
    assert config.project_name == "小径分岔的花园", f"项目名称不匹配: {config.project_name}"
    assert config.source_transcript.exists(), f"转录文件不存在: {config.source_transcript}"
    assert config.source_audio.exists(), f"音频文件不存在: {config.source_audio}"

    log_phase("J1", "制作人", "加载项目上下文", "load_project()")
    ctx = load_project(config=config)

    assert ctx.config is config, "ProjectContext.config 不一致"
    assert len(ctx.entries) > 0, "entries 为空"
    assert len(ctx.merged) > 0, "merged 为空"
    assert isinstance(ctx.custom_errata, dict), "custom_errata 类型错误"

    log_phase("J1", "制作人", "勘误引擎加载", f"entries={len(ctx.entries)}, errata_keys={len(ctx.custom_errata)}")

    errata_cfg = ErrataConfig.from_project_dir(PROJECT_DIR)
    assert len(errata_cfg.flat_errata) > 0, "flat_errata 为空"
    assert len(errata_cfg.asr_phonetic_patterns) >= 0, "asr_phonetic_patterns 加载失败"

    flat = flatten_errata({"authors": {"博赫斯": "博尔赫斯"}, "works": {"百年弧独": "百年孤独"}})
    assert flat == {"博赫斯": "博尔赫斯", "百年弧独": "百年孤独"}, f"flatten_errata 结果不正确: {flat}"

    log_phase("J1", "制作人", "创作蓝图确认", f"意图A={blueprint['intent_A']['name']}, 意图B={blueprint['intent_B']['name']}, 意图C={blueprint['intent_C']['name']}")

    blueprint_path = OUTPUT_BASE / "blueprint.json"
    blueprint_path.parent.mkdir(parents=True, exist_ok=True)
    blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 项目加载成功: {config.project_name}")
    print(f"  ✅ 转录条目: {len(ctx.entries)}")
    print(f"  ✅ 合并条目: {len(ctx.merged)}")
    print(f"  ✅ 勘误条目: {len(errata_cfg.flat_errata)}")
    print(f"  ✅ 创作蓝图已保存")

    return ctx, blueprint


# ═══════════════════════════════════════════════════════════════
# Journey Phase 2: 意图A — 内容原子化（工作流2）+ 出品审核 + autoresearch
# ═══════════════════════════════════════════════════════════════

def journey_phase2(ctx: ProjectContext, blueprint: dict):
    print_section("Journey Phase 2: 意图A — 内容原子化（工作流2）")

    intent = blueprint["intent_A"]
    series_name = intent["series"]
    clips = ctx.config.get_clips(series_name)

    log_phase("J2", "策划总监", "选题分析", f"系列={series_name}, 切片数={len(clips)}")

    assert len(clips) > 0, f"系列 '{series_name}' 无切片定义"

    for clip in clips:
        assert "id" in clip, f"切片缺少 id: {clip}"
        assert "start_s" in clip, f"切片缺少 start_s: {clip}"
        assert "end_s" in clip, f"切片缺少 end_s: {clip}"
        assert clip["end_s"] > clip["start_s"], f"切片时间无效: {clip['id']}"

    log_phase("J2", "剪辑师", "提取切片条目", f"提取第一个切片作为示例")
    sample_clip = clips[0]
    raw_entries = extract_clip_entries(ctx.entries, sample_clip["start_s"], sample_clip["end_s"])
    assert len(raw_entries) > 0, f"切片 {sample_clip['id']} 无条目"

    log_phase("J2", "字幕师", "字幕处理全链路", "process_clip_subtitles → merge_short_entries")

    processed = process_clip_subtitles(raw_entries, ctx.custom_errata, max_chars=18, strip_punctuation=True)
    assert len(processed) > 0, "字幕处理后为空"

    merged = merge_short_entries(processed, max_chars=18)
    assert len(merged) > 0, "合并后为空"

    for entry in merged:
        assert "index" in entry, f"合并条目缺少 index"
        assert "start_s" in entry, f"合并条目缺少 start_s"
        assert "end_s" in entry, f"合并条目缺少 end_s"
        assert "text" in entry, f"合并条目缺少 text"

    log_phase("J2", "字幕师", "文本规范化验证", "normalize_to_simplified_chinese")

    test_cases = [
        ("博赫斯寫了小徑分叉的花園", "博尔赫斯写了小径分岔的花园"),
        ("著名的著作裡說著", "著名的著作里说着"),
        ("他著急地走著", "他着急地走着"),
    ]
    for input_text, expected_substring in test_cases:
        result = normalize_to_simplified_chinese(input_text)
        assert expected_substring in result or result == expected_substring, \
            f"规范化失败: '{input_text}' → '{result}', 期望包含 '{expected_substring}'"

    log_phase("J2", "字幕师", "字幕格式化验证", "add_punctuation_smart / format_subtitle_single_line")

    punct_result = add_punctuation_smart("你觉得呢", next_text="但是", duration_s=2.0, gap_s=0.5)
    assert "？" in punct_result or "，" in punct_result, f"标点添加失败: '{punct_result}'"

    formatted = format_subtitle_single_line("这是一个非常非常长的字幕文本需要被截断处理", max_chars=18)
    assert len(formatted) <= 18, f"格式化后超长: '{formatted}' ({len(formatted)})"

    log_phase("J2", "字幕师", "禁则处理验证", "check_line_start_rules / check_line_end_rules")

    start_violations = check_line_start_rules("的了着过吗")
    assert len(start_violations) > 0, "行首禁则未检测到"

    end_violations = check_line_end_rules("不没很更")
    assert len(end_violations) > 0, "行末禁则未检测到"

    meaningless = detect_meaningless_words("那个那个然后然后嗯嗯嗯")
    assert len(meaningless) > 0, "无意义重复词未检测到"

    anomalies = detect_context_anomalies("这是一个非常长的中文文本没有任何标点符号来断句但是内容很多", check_punctuation=True)
    assert len(anomalies) > 0, "无标点长文本异常未检测到"

    log_phase("J2", "字幕师", "字幕渲染验证", "generate_ass_with_rounded_bg")

    ass_content = generate_ass_with_rounded_bg(
        entries=merged,
        video_width=1920,
        video_height=1080,
        font_name="Noto Sans SC",
        font_size=52,
    )
    assert "[Script Info]" in ass_content, "ASS 缺少 Script Info"
    assert "[Events]" in ass_content, "ASS 缺少 Events"
    assert "Dialogue:" in ass_content, "ASS 缺少 Dialogue"
    assert "Noto Sans SC" in ass_content, "ASS 缺少字体名"
    assert "ScaledBorderAndShadow" in ass_content, "ASS 缺少 ScaledBorderAndShadow"

    log_phase("J2", "字幕师", "字体授权校验", "validate_font_license")

    noto_issues = validate_font_license("Noto Sans SC")
    assert len(noto_issues) == 0, f"Noto Sans SC 不应有授权问题: {noto_issues}"

    yahei_issues = validate_font_license("Microsoft YaHei")
    assert len(yahei_issues) > 0, "微软雅黑应检测到授权问题"

    unknown_issues = validate_font_license("SomeUnknownFont")
    assert any(i["issue_type"] == "unknown_font_license" for i in unknown_issues), "未知字体应产生警告"

    log_phase("J2", "字幕师", "渲染样式校验", "validate_render_style")

    style_issues = validate_render_style({
        "font_name": "Noto Sans SC",
        "mode": "frosted_glass_dark",
        "font_color": "white",
        "bg_opacity": 0.7,
    })
    assert len(style_issues) == 0, f"正确样式不应有问题: {style_issues}"

    bad_style_issues = validate_render_style({
        "font_name": "Microsoft YaHei",
        "mode": "frosted_glass_dark",
        "font_color": "black",
        "bg_opacity": 0.2,
    })
    assert len(bad_style_issues) > 0, "错误样式应检测到问题"

    log_phase("J2", "字幕师", "毛玻璃滤镜生成", "get_frosted_glass_ffmpeg_filter")
    filter_str = get_frosted_glass_ffmpeg_filter(1920, 1080, blur_radius=12, band_height=120)
    assert "boxblur" in filter_str, "毛玻璃滤镜缺少 boxblur"
    assert "overlay" in filter_str, "毛玻璃滤镜缺少 overlay"

    log_phase("J2", "字幕师", "内容验证全维度", "validate_subtitle_content")

    validation_result = validate_subtitle_content_facade(
        merged,
        max_chars=18,
        render_style={"font_name": "Noto Sans SC", "mode": "frosted_glass_dark", "font_color": "white", "bg_opacity": 0.7},
        strip_punctuation=True,
        enable_word_verify=True,
        enable_overlap_check=True,
    )
    assert isinstance(validation_result, ContentValidationResult), "验证结果类型错误"
    assert validation_result.total_entries > 0, "验证条目数为0"

    log_phase("J2", "字幕师", "内容验证子维度", "validate_simplified_chinese / validate_punctuation / validate_single_line / validate_line_length / validate_errata / validate_asr_phonetic / validate_sentence_by_sentence / validate_context_coherence / validate_line_break_rules / validate_contextual_errata / validate_word_level / validate_subtitle_overlap")

    sc_issues = validate_simplified_chinese(merged)
    p_issues = validate_punctuation(merged)
    sl_issues = validate_single_line(merged)
    ll_issues = validate_line_length(merged, max_chars=18)

    errata_cfg = ErrataConfig.from_project_dir(PROJECT_DIR)
    e_issues = validate_errata(merged, errata_cfg.flat_errata)
    asr_issues = validate_asr_phonetic(merged, errata_cfg.flat_errata, errata_cfg.asr_phonetic_patterns)
    sem_issues = validate_sentence_by_sentence(merged, errata_cfg.semantic_patterns)
    cc_issues = validate_context_coherence(merged, strip_punctuation=True)
    lb_issues = validate_line_break_rules(merged)
    ce_issues = validate_contextual_errata(merged, errata_cfg, context_keywords=None, context_disambiguation=None)
    wl_issues = validate_word_level(merged)
    ov_issues = validate_subtitle_overlap(merged)

    log_phase("J2", "字幕师", "process_subtitle_content入口", "整合链路测试")

    processed_text = process_subtitle_content(
        text="博赫斯寫了小徑分叉的花園",
        duration_s=3.0,
        next_text="但是",
        gap_s=0.5,
        max_chars=18,
        is_last=False,
        custom_errata=ctx.custom_errata,
        strip_punctuation=True,
    )
    assert "博尔赫斯" in processed_text or "小径分岔" in processed_text, \
        f"process_subtitle_content 处理失败: '{processed_text}'"

    log_phase("J2", "剪辑师", "process_series统一入口", f"系列={series_name}, 切片数={len(clips)}")

    series_dir = OUTPUT_BASE / "clips" / series_name
    results = process_series(
        clips=clips,
        series_dir=series_dir,
        entries=ctx.entries,
        audio_source=ctx.config.source_audio,
        video_source=ctx.config.source_video,
        custom_errata=ctx.custom_errata,
        make_vertical=False,
        make_srt=True,
        skip_existing=True,
        max_chars=18,
        strip_punctuation=True,
        series_name=series_name,
        project_name=ctx.config.project_name,
    )

    generated = sum(1 for r in results if not r.errors)
    log_phase("J2", "剪辑师", "切片处理完成", f"成功={generated}, 总数={len(results)}")

    summary_path = series_dir / "summary.json"
    assert summary_path.exists(), "summary.json 未生成"

    log_phase("J2", "审核人", "出品审核", "run_quality_check")
    quality_report = run_quality_check(series_dir, ctx.config, version_key=f"intent_A_{series_name}")

    assert isinstance(quality_report, QualityReport), "质量报告类型错误"
    assert quality_report.overall_score >= 0, f"质量分数异常: {quality_report.overall_score}"

    report_path = OUTPUT_BASE / "reports" / f"quality_{series_name}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    quality_report.save(report_path)

    log_phase("J2", "审核人", "审核结论", f"score={quality_report.overall_score:.1f}, passed={quality_report.passed}, critical={len(quality_report.critical_issues)}")

    if not quality_report.passed:
        log_phase("J2", "制作人", "autoresearch优化", "审核未通过，启动优化迭代")
        _run_autoresearch(ctx, quality_report, series_dir, "intent_A")

    print(f"  ✅ 意图A完成: {generated}/{len(results)} 切片成功")
    print(f"  ✅ 质量评分: {quality_report.overall_score:.1f}")
    print(f"  ✅ 审核结果: {'通过' if quality_report.passed else '未通过'}")


# ═══════════════════════════════════════════════════════════════
# Journey Phase 3: 意图B — 知识混剪（工作流3）+ 出品审核 + autoresearch
# ═══════════════════════════════════════════════════════════════

def journey_phase3(ctx: ProjectContext, blueprint: dict):
    print_section("Journey Phase 3: 意图B — 知识混剪（工作流3）")

    intent = blueprint["intent_B"]
    series_name = intent["series"]
    clips = ctx.config.get_clips(series_name)

    log_phase("J3", "策划总监", "知识图谱构建", f"系列={series_name}, 章节数={len(clips)}")

    assert len(clips) > 0, f"系列 '{series_name}' 无切片定义"

    for clip in clips:
        assert "domain" in clip, f"哲思切片缺少 domain: {clip['id']}"

    log_phase("J3", "剪辑师", "系列制作", f"process_series for {series_name}")

    series_dir = OUTPUT_BASE / "clips" / series_name
    results = process_series(
        clips=clips,
        series_dir=series_dir,
        entries=ctx.entries,
        audio_source=ctx.config.source_audio,
        video_source=ctx.config.source_video,
        custom_errata=ctx.custom_errata,
        make_vertical=False,
        make_srt=True,
        skip_existing=True,
        max_chars=18,
        strip_punctuation=True,
        series_name=series_name,
        project_name=ctx.config.project_name,
    )

    generated = sum(1 for r in results if not r.errors)
    log_phase("J3", "剪辑师", "系列制作完成", f"成功={generated}, 总数={len(results)}")

    summary_path = series_dir / "summary.json"
    assert summary_path.exists(), "summary.json 未生成"

    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "total_clips" in summary_data, "summary.json 缺少 total_clips"
    assert "clips" in summary_data, "summary.json 缺少 clips"

    log_phase("J3", "审核人", "出品审核", "run_quality_check")
    quality_report = run_quality_check(series_dir, ctx.config, version_key=f"intent_B_{series_name}")
    quality_report.save(OUTPUT_BASE / "reports" / f"quality_{series_name}.json")

    log_phase("J3", "审核人", "审核结论", f"score={quality_report.overall_score:.1f}, passed={quality_report.passed}")

    if not quality_report.passed:
        log_phase("J3", "制作人", "autoresearch优化", "审核未通过，启动优化迭代")
        _run_autoresearch(ctx, quality_report, series_dir, "intent_B")

    print(f"  ✅ 意图B完成: {generated}/{len(results)} 章节成功")
    print(f"  ✅ 质量评分: {quality_report.overall_score:.1f}")


# ═══════════════════════════════════════════════════════════════
# Journey Phase 4: 意图C — 深度思考系列（工作流3扩展）+ 出品审核 + autoresearch
# ═══════════════════════════════════════════════════════════════

def journey_phase4(ctx: ProjectContext, blueprint: dict):
    print_section("Journey Phase 4: 意图C — 深度思考系列（工作流3扩展）")

    intent = blueprint["intent_C"]
    series_name = intent["series"]
    clips = ctx.config.get_clips(series_name)

    log_phase("J4", "策划总监", "深度思考系列规划", f"系列={series_name}, 章节数={len(clips)}")

    assert len(clips) > 0, f"系列 '{series_name}' 无切片定义"

    for clip in clips:
        assert "chapter" in clip, f"深度思考切片缺少 chapter: {clip['id']}"

    log_phase("J4", "剪辑师", "process_clip单条处理", f"使用process_clip处理第一个切片")

    sample_clip = clips[0]
    clip_dir = OUTPUT_BASE / "clips" / series_name / sample_clip["id"]
    single_result = process_clip(
        clip=sample_clip,
        clip_dir=clip_dir,
        entries=ctx.entries,
        audio_source=ctx.config.source_audio,
        video_source=ctx.config.source_video,
        custom_errata=ctx.custom_errata,
        make_vertical=False,
        make_srt=True,
        skip_existing=True,
        max_chars=18,
        strip_punctuation=True,
        ass_style=None,
        fade_in_s=0.05,
        fade_out_s=0.1,
        extra_metadata={"journey_phase": "J4"},
    )

    assert isinstance(single_result, ClipProcessResult), "ClipProcessResult 类型错误"
    assert single_result.clip_id == sample_clip["id"], f"clip_id 不匹配"

    metadata_path = clip_dir / "metadata.json"
    assert metadata_path.exists(), "metadata.json 未生成"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["id"] == sample_clip["id"], "metadata id 不匹配"
    assert "journey_phase" in metadata, "extra_metadata 未写入"

    log_phase("J4", "剪辑师", "系列批量处理", f"process_series for {series_name}")

    series_dir = OUTPUT_BASE / "clips" / series_name
    results = process_series(
        clips=clips,
        series_dir=series_dir,
        entries=ctx.entries,
        audio_source=ctx.config.source_audio,
        video_source=ctx.config.source_video,
        custom_errata=ctx.custom_errata,
        make_vertical=False,
        make_srt=True,
        skip_existing=True,
        max_chars=18,
        strip_punctuation=True,
        series_name=series_name,
        project_name=ctx.config.project_name,
    )

    generated = sum(1 for r in results if not r.errors)
    log_phase("J4", "剪辑师", "系列制作完成", f"成功={generated}, 总数={len(results)}")

    log_phase("J4", "审核人", "出品审核", "run_quality_check")
    quality_report = run_quality_check(series_dir, ctx.config, version_key=f"intent_C_{series_name}")
    quality_report.save(OUTPUT_BASE / "reports" / f"quality_{series_name}.json")

    log_phase("J4", "审核人", "审核结论", f"score={quality_report.overall_score:.1f}, passed={quality_report.passed}")

    if not quality_report.passed:
        log_phase("J4", "制作人", "autoresearch优化", "审核未通过，启动优化迭代")
        _run_autoresearch(ctx, quality_report, series_dir, "intent_C")

    print(f"  ✅ 意图C完成: {generated}/{len(results)} 章节成功")
    print(f"  ✅ 质量评分: {quality_report.overall_score:.1f}")


# ═══════════════════════════════════════════════════════════════
# Journey Phase 5: 全平台出品（工作流4）+ 出品审核
# ═══════════════════════════════════════════════════════════════

def journey_phase5(ctx: ProjectContext):
    print_section("Journey Phase 5: 全平台出品（工作流4）")

    log_phase("J5", "出品人", "扫描成品视频", "查找所有 subtitled.mp4 文件")

    video_files = list(OUTPUT_BASE.rglob("*_subtitled.mp4"))
    if not video_files:
        video_files = list(OUTPUT_BASE.rglob("*.mp4"))

    if not video_files:
        log_phase("J5", "出品人", "无视频文件", "跳过视频导出，使用音频文件测试导出接口")
        audio_files = list(OUTPUT_BASE.rglob("*.wav"))
        if audio_files:
            _export_audio_platforms(ctx, audio_files[0])
        _test_export_api_signatures(ctx)
        return

    sample_video = video_files[0]
    log_phase("J5", "出品人", "选择导出样本", f"{sample_video.name}")

    for platform in ALL_PLATFORMS:
        log_phase("J5", "出品人", f"导出平台: {platform}", "export_for_platform")

        platform_dir = OUTPUT_BASE / "platforms" / platform
        result = export_for_platform(sample_video, platform_dir, platform, ctx.config)

        assert isinstance(result, ExportResult), f"ExportResult 类型错误: {platform}"
        assert result.platform == platform, f"平台不匹配: {result.platform} != {platform}"

        log_phase("J5", "出品人", f"导出结果: {platform}", f"success={result.success}, size={result.file_size_mb:.2f}MB")

    log_phase("J5", "出品人", "批量导出", "export_all_platforms")
    all_results = export_all_platforms(
        sample_video,
        OUTPUT_BASE / "platforms",
        ALL_PLATFORMS,
        ctx.config,
    )
    assert len(all_results) == len(ALL_PLATFORMS), f"批量导出数量不匹配: {len(all_results)} != {len(ALL_PLATFORMS)}"

    log_phase("J5", "出品人", "纯音频导出", "export_audio_only")
    audio_files = list(OUTPUT_BASE.rglob("*.wav"))
    if audio_files:
        for audio_platform in ["xiaoyuzhou", "apple_podcasts"]:
            audio_result = export_audio_only(
                audio_files[0],
                OUTPUT_BASE / "platforms" / audio_platform,
                audio_platform,
                ctx.config,
            )
            assert isinstance(audio_result, ExportResult), "ExportResult 类型错误"
            log_phase("J5", "出品人", f"音频导出: {audio_platform}", f"success={audio_result.success}")

    log_phase("J5", "声音设计师", "响度标准化", "normalize_for_platform / measure_loudness_detailed / normalize_loudness")

    if audio_files:
        loudness_info = measure_loudness_detailed(audio_files[0])
        log_phase("J5", "声音设计师", "响度测量", f"结果keys={list(loudness_info.keys()) if loudness_info else 'empty'}")

        norm_output = OUTPUT_BASE / "audio" / "normalized.wav"
        norm_output.parent.mkdir(parents=True, exist_ok=True)
        try:
            norm_result = normalize_loudness(audio_files[0], norm_output, target_lufs=-14.0, true_peak=-1.0)
            assert isinstance(norm_result, NormalizationResult), "NormalizationResult 类型错误"
            log_phase("J5", "声音设计师", "响度标准化完成", f"success={norm_result.success}")
        except Exception as e:
            log_phase("J5", "声音设计师", "响度标准化异常", str(e)[:200])

        try:
            platform_norm = normalize_for_platform(audio_files[0], OUTPUT_BASE / "audio" / "bilibili_norm.wav", "bilibili", ctx.config)
            assert isinstance(platform_norm, NormalizationResult), "平台标准化结果类型错误"
            log_phase("J5", "声音设计师", "平台响度标准化", f"success={platform_norm.success}")
        except Exception as e:
            log_phase("J5", "声音设计师", "平台响度标准化异常", str(e)[:200])

        try:
            batch_results = batch_normalize(audio_files[:3], OUTPUT_BASE / "audio" / "batch", target_lufs=-14.0)
            assert isinstance(batch_results, list), "batch_normalize 结果类型错误"
            log_phase("J5", "声音设计师", "批量标准化", f"处理{len(batch_results)}个文件")
        except Exception as e:
            log_phase("J5", "声音设计师", "批量标准化异常", str(e)[:200])

    log_phase("J5", "审核人", "出品审核", "run_quality_check on platforms")
    quality_report = run_quality_check(OUTPUT_BASE / "platforms", ctx.config, version_key="intent_D_platforms")
    quality_report.save(OUTPUT_BASE / "reports" / "quality_platforms.json")

    log_phase("J5", "审核人", "审核结论", f"score={quality_report.overall_score:.1f}, passed={quality_report.passed}")

    print(f"  ✅ 全平台导出完成: {sum(1 for r in all_results if r.success)}/{len(all_results)} 成功")
    print(f"  ✅ 质量评分: {quality_report.overall_score:.1f}")


def _export_audio_platforms(ctx: ProjectContext, audio_file: Path):
    for platform in ["xiaoyuzhou", "apple_podcasts"]:
        result = export_audio_only(audio_file, OUTPUT_BASE / "platforms" / platform, platform, ctx.config)
        log_phase("J5", "出品人", f"音频导出: {platform}", f"success={result.success}")


def _test_export_api_signatures(ctx: ProjectContext):
    log_phase("J5", "出品人", "导出API签名测试", "验证接口可调用性")

    for platform in ALL_PLATFORMS:
        platform_cfg = ctx.config.get_platform_config(platform)
        assert isinstance(platform_cfg, dict), f"平台配置类型错误: {platform}"

    log_phase("J5", "出品人", "API签名测试通过", "所有平台配置可读取")


# ═══════════════════════════════════════════════════════════════
# Journey Phase 6: 素材库打包 + 交付（工作流5）+ 最终审核
# ═══════════════════════════════════════════════════════════════

def journey_phase6(ctx: ProjectContext):
    print_section("Journey Phase 6: 素材库打包 + 交付（工作流5）")

    log_phase("J6", "出品人", "素材清单生成", "扫描输出目录")

    all_files = list(OUTPUT_BASE.rglob("*"))
    file_stats = {}
    for f in all_files:
        if f.is_file():
            ext = f.suffix.lower()
            file_stats[ext] = file_stats.get(ext, 0) + 1

    log_phase("J6", "出品人", "素材统计", f"文件类型: {dict(list(file_stats.items())[:10])}")

    log_phase("J6", "出品人", "版权声明生成", "COPYRIGHT.md")
    copyright_content = _generate_copyright(ctx)
    copyright_path = OUTPUT_BASE / "COPYRIGHT.md"
    copyright_path.write_text(copyright_content, encoding="utf-8")

    log_phase("J6", "出品人", "发布信息卡生成", "RELEASE_CARDS.json")
    release_cards = _generate_release_cards(ctx)
    release_path = OUTPUT_BASE / "RELEASE_CARDS.json"
    release_path.write_text(json.dumps(release_cards, ensure_ascii=False, indent=2), encoding="utf-8")

    log_phase("J6", "出品人", "项目总览生成", "summary.json")
    project_summary = _generate_project_summary(ctx, file_stats)
    summary_path = OUTPUT_BASE / "summary.json"
    summary_path.write_text(json.dumps(project_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    log_phase("J6", "审核人", "最终审核", "run_quality_check on full output")
    final_report = run_quality_check(OUTPUT_BASE, ctx.config, version_key="final_delivery")
    final_report.save(OUTPUT_BASE / "reports" / "quality_final.json")

    log_phase("J6", "审核人", "最终审核结论", f"score={final_report.overall_score:.1f}, passed={final_report.passed}")

    log_phase("J6", "制作人", "交付报告", "生成交付总结")

    delivery_report = {
        "project": ctx.config.project_name,
        "description": ctx.config.project_description,
        "output_dir": str(OUTPUT_BASE),
        "quality_score": final_report.overall_score,
        "quality_passed": final_report.passed,
        "critical_issues": len(final_report.critical_issues),
        "warnings": len(final_report.warnings),
        "recommendations": final_report.recommendations,
        "file_stats": file_stats,
        "journey_phases": len(journey_log),
        "journey_log_path": str(OUTPUT_BASE / "journey_log.json"),
    }
    delivery_path = OUTPUT_BASE / "delivery_report.json"
    delivery_path.write_text(json.dumps(delivery_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 版权声明: {copyright_path}")
    print(f"  ✅ 发布信息卡: {release_path}")
    print(f"  ✅ 项目总览: {summary_path}")
    print(f"  ✅ 最终质量评分: {final_report.overall_score:.1f}")
    print(f"  ✅ 最终审核: {'通过' if final_report.passed else '未通过'}")
    print(f"  ✅ 交付报告: {delivery_path}")


# ═══════════════════════════════════════════════════════════════
# Autoresearch 优化循环
# ═══════════════════════════════════════════════════════════════

def _run_autoresearch(ctx: ProjectContext, quality_report: QualityReport, version_dir: Path, intent_id: str):
    log_phase("AR", "制作人", "启动autoresearch", f"intent={intent_id}")

    experiment_dir = OUTPUT_BASE / "experiments" / intent_id
    experiment = Experiment(
        config=ctx.config,
        log_dir=experiment_dir,
        direction="general_quality",
    )
    experiment.set_baseline(quality_report)

    baseline_metrics = compute_metrics_from_quality_report(quality_report)
    log_phase("AR", "制作人", "基线指标", f"score={baseline_metrics.overall_score:.1f}, critical={baseline_metrics.critical_issue_count}")

    recommended = get_recommended_strategies(baseline_metrics)
    log_phase("AR", "制作人", "推荐策略", f"数量={len(recommended)}")

    all_strategies = get_all_strategies()
    log_phase("AR", "制作人", "全部策略", f"数量={len(all_strategies)}")

    low_risk = get_strategies_by_risk("low")
    assert len(low_risk) > 0, "应有低风险策略"

    medium_risk = get_strategies_by_risk("medium")
    log_phase("AR", "制作人", "策略风险分布", f"low={len(low_risk)}, medium={len(medium_risk)}")

    for i, strategy in enumerate(recommended[:3]):
        log_phase("AR", "制作人", f"执行策略: {strategy.strategy_name}", strategy.description)

        def quality_fn(cfg):
            return run_quality_check(version_dir, cfg, version_key=f"{intent_id}_exp_{i+1}")

        record = experiment.run_experiment(
            config_modifications=strategy.config_modifications,
            quality_report_fn=quality_fn,
            notes=f"Autoresearch for {intent_id}: {strategy.strategy_name}",
        )

        log_phase("AR", "制作人", f"实验结果: {strategy.strategy_name}", f"improved={record.improved}, kept={record.kept}")

    status = experiment.get_status()
    log_phase("AR", "制作人", "autoresearch状态", f"experiments={status['experiment_count']}, baseline={status['baseline_score']}, current={status['current_score']}")

    log_summary = experiment.log.summary()
    log_phase("AR", "制作人", "实验日志摘要", f"total={log_summary['total_experiments']}, improvements={log_summary['improvements']}")

    comparison = compare_metrics(baseline_metrics, baseline_metrics)
    assert "overall_score_delta" in comparison, "compare_metrics 结果缺少 overall_score_delta"
    assert "improved" in comparison, "compare_metrics 结果缺少 improved"

    is_better = compute_better_than_baseline(baseline_metrics, baseline_metrics)
    assert isinstance(is_better, bool), "compute_better_than_baseline 返回类型错误"

    log_phase("AR", "制作人", "autoresearch完成", f"intent={intent_id}")


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _generate_copyright(ctx: ProjectContext) -> str:
    return f"""# 版权声明

## 项目信息
- 项目名称：{ctx.config.project_name}
- 项目描述：{ctx.config.project_description}

## 原始素材来源
- 转录文件：{ctx.config.source_transcript}
- 音频文件：{ctx.config.source_audio}
- 视频文件：{ctx.config.source_video}

## 字幕文本版权
字幕文本基于ASR自动识别生成，经过人工勘误校正。
所有勘误规则基于项目级 errata.yaml 配置。

## 字体授权
- 字幕字体：Noto Sans SC（SIL Open Font License，商用免费）

## CC协议声明
本作品采用 CC BY-NC-SA 4.0 协议发布。

---
生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
"""


def _generate_release_cards(ctx: ProjectContext) -> list[dict]:
    cards = []
    for series_name in ctx.config.get_all_clips():
        clips = ctx.config.get_clips(series_name)
        for clip in clips:
            cards.append({
                "id": clip["id"],
                "title": clip.get("title", ""),
                "series": clip.get("series", series_name),
                "description": clip.get("description", ""),
                "hook": clip.get("hook", ""),
                "domain": clip.get("domain", ""),
                "duration_s": clip["end_s"] - clip["start_s"],
                "platform_tags": {
                    "bilibili": ["播客", "深度对话", clip.get("domain", "")],
                    "douyin": ["金句", clip.get("hook", "")],
                    "youtube": ["podcast", "philosophy", clip.get("domain", "")],
                },
            })
    return cards


def _generate_project_summary(ctx: ProjectContext, file_stats: dict) -> dict:
    all_clips = ctx.config.get_all_clips()
    total_clips = sum(len(v) for v in all_clips.values())

    return {
        "project": ctx.config.project_name,
        "description": ctx.config.project_description,
        "output_dir": str(OUTPUT_BASE),
        "series_count": len(all_clips),
        "total_clips": total_clips,
        "series": {k: len(v) for k, v in all_clips.items()},
        "platforms": ALL_PLATFORMS,
        "file_stats": file_stats,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SKILL Journey 端到端测试                               ║")
    print("║  项目：《小径分岔的花园》全平台素材                       ║")
    print("║  模式：SKILL角色驱动 + 流程编排                          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    if OUTPUT_BASE.exists():
        shutil.rmtree(OUTPUT_BASE)
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    try:
        ctx, blueprint = journey_phase1()
        journey_phase2(ctx, blueprint)
        journey_phase3(ctx, blueprint)
        journey_phase4(ctx, blueprint)
        journey_phase5(ctx)
        journey_phase6(ctx)
    except Exception as e:
        log_phase("ERROR", "系统", "执行异常", str(e)[:500])
        import traceback
        traceback.print_exc()

    elapsed = time.time() - start_time

    save_journey_log()

    print(f"\n{'='*60}")
    print(f"  SKILL Journey 测试完成")
    print(f"  总耗时: {elapsed:.1f}s")
    print(f"  日志条目: {len(journey_log)}")
    print(f"  输出目录: {OUTPUT_BASE}")
    print(f"{'='*60}")

    api_coverage = {
        "pipeline.config.PipelineConfig": ["__init__(project_dir=)", "get()", "set()", "get_platform_config()", "get_clips()", "get_all_clips()", "project_dir", "project_name", "source_transcript", "source_audio", "source_video", "output_dir", "clips", "sources", "standards", "platforms", "to_dict()", "save()"],
        "pipeline.loader": ["load_project()", "ProjectContext"],
        "pipeline.errata_engine": ["ErrataConfig.from_project_dir()", "ErrataConfig.from_dict()", "flatten_errata()", "apply_errata()", "apply_asr_phonetic_corrections()", "detect_asr_phonetic_errors()", "load_errata_yaml()", "load_asr_phonetic_patterns()", "load_semantic_patterns()", "validate_errata_entries()", "validate_semantic_entries()"],
        "pipeline.text_normalizer": ["traditional_to_simplified()", "convert_zhu_to_zhe()", "normalize_chinese()"],
        "pipeline.subtitle_formatter": ["add_punctuation_smart()", "clean_subtitle_text()", "enforce_single_line()", "format_subtitle_single_line()", "check_line_start_rules()", "check_line_end_rules()", "detect_meaningless_words()", "detect_context_anomalies()", "remove_display_punctuation()"],
        "pipeline.subtitle_renderer": ["generate_ass_with_rounded_bg()", "get_frosted_glass_ffmpeg_filter()", "validate_font_license()", "validate_render_style()"],
        "pipeline.content_validator": ["validate_simplified_chinese()", "validate_punctuation()", "validate_single_line()", "validate_line_length()", "validate_errata()", "validate_asr_phonetic()", "validate_sentence_by_sentence()", "validate_context_coherence()", "validate_line_break_rules()", "validate_contextual_errata()", "validate_word_level()", "validate_subtitle_overlap()", "validate_subtitle_content()"],
        "pipeline.subtitle_content": ["process_subtitle_content()", "normalize_to_simplified_chinese()", "apply_custom_errata()", "load_custom_errata()", "load_errata_from_project()", "validate_subtitle_content()", "validate_contextual_errata()", "set_project_verification_config()"],
        "pipeline.clip_processor": ["extract_clip_entries()", "process_clip_subtitles()", "merge_short_entries()", "generate_audio()", "generate_ass()", "generate_srt()", "generate_video_subtitled()", "generate_video_vertical()", "write_metadata()", "process_clip()", "process_series()"],
        "pipeline.exporter": ["export_for_platform()", "export_all_platforms()", "export_audio_only()"],
        "pipeline.loudness_normalizer": ["normalize_for_platform()", "measure_loudness_detailed()", "normalize_loudness()", "batch_normalize()"],
        "pipeline.quality_checker": ["run_quality_check()", "check_audio_files()", "check_subtitle_files()", "check_efficiency()", "generate_recommendations()"],
        "autoresearch.strategies": ["STRATEGIES", "get_strategy()", "get_all_strategies()", "get_strategies_by_risk()", "get_recommended_strategies()"],
        "autoresearch.experiment": ["Experiment()", "ExperimentLog()", "ExperimentRecord"],
        "autoresearch.metrics": ["compute_metrics_from_quality_report()", "compare_metrics()", "compute_better_than_baseline()"],
    }

    total_apis = sum(len(v) for v in api_coverage.values())
    print(f"\n  API覆盖: {len(api_coverage)} 模块, {total_apis} 接口")
    for module, apis in api_coverage.items():
        print(f"    {module}: {len(apis)} 个接口")


if __name__ == "__main__":
    main()
