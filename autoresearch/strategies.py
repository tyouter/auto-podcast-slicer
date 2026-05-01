import json
from pathlib import Path
from dataclasses import dataclass, field
from autoresearch.experiment import Experiment, ExperimentLog
from autoresearch.metrics import PipelineMetrics


@dataclass
class StrategyResult:
    strategy_name: str
    description: str
    config_modifications: dict
    expected_improvement: str
    risk_level: str = "low"


STRATEGIES = {
    "improve_cut_points": StrategyResult(
        strategy_name="improve_cut_points",
        description="优化切点位置：增加静音检测搜索范围，添加零交叉点检测",
        config_modifications={
            "pipeline.audio_processor.cut_point.prefer_silence": True,
            "pipeline.audio_processor.cut_point.prefer_zero_crossing": True,
            "pipeline.audio_processor.cut_point.min_silence_for_cut": 0.5,
            "pipeline.audio_processor.cut_point.padding_before_ms": 150,
            "pipeline.audio_processor.cut_point.padding_after_ms": 150,
        },
        expected_improvement="减少突兀的音频进入和截断",
        risk_level="low",
    ),
    "improve_crossfade": StrategyResult(
        strategy_name="improve_crossfade",
        description="增加交叉淡化时长，使音频过渡更平滑",
        config_modifications={
            "pipeline.audio_processor.crossfade_duration_ms": 100,
            "pipeline.audio_processor.fade_in_duration_ms": 50,
            "pipeline.audio_processor.fade_out_duration_ms": 80,
        },
        expected_improvement="减少切点处的爆音和不自然过渡",
        risk_level="low",
    ),
    "improve_breath_handling": StrategyResult(
        strategy_name="improve_breath_handling",
        description="优化呼吸声处理：从删除改为降低音量，调整参数",
        config_modifications={
            "pipeline.audio_processor.breath_handling.mode": "reduce",
            "pipeline.audio_processor.breath_handling.reduction_db": -22,
            "pipeline.audio_processor.breath_handling.min_breath_duration": 0.12,
            "pipeline.audio_processor.breath_handling.max_breath_duration": 0.9,
        },
        expected_improvement="保留自然呼吸感，避免不自然的静音间隙",
        risk_level="low",
    ),
    "improve_subtitle_timing": StrategyResult(
        strategy_name="improve_subtitle_timing",
        description="调整字幕时间参数：增加最短显示时间，增加最小间隔",
        config_modifications={
            "pipeline.subtitle.min_display_duration": 1.2,
            "pipeline.subtitle.min_gap_duration": 0.1,
        },
        expected_improvement="减少字幕闪烁和阅读困难",
        risk_level="low",
    ),
    "improve_subtitle_readability": StrategyResult(
        strategy_name="improve_subtitle_readability",
        description="优化字幕可读性：减少每行字数，降低阅读速度",
        config_modifications={
            "pipeline.subtitle.max_chars_per_line_cn": 13,
            "pipeline.subtitle.max_display_duration": 6.0,
        },
        expected_improvement="提升字幕阅读舒适度",
        risk_level="low",
    ),
    "improve_loudness_target": StrategyResult(
        strategy_name="improve_loudness_target",
        description="调整响度目标以适应多平台发布",
        config_modifications={
            "pipeline.audio_verification.loudness.target_lufs": -14,
            "pipeline.audio_verification.loudness.true_peak_dbtp": -1.5,
            "pipeline.audio_verification.loudness.max_lra": 8,
        },
        expected_improvement="确保各平台响度合规",
        risk_level="medium",
    ),
    "improve_topic_segmentation": StrategyResult(
        strategy_name="improve_topic_segmentation",
        description="调整主题分割参数：增加最短段落时长，提高一致性阈值",
        config_modifications={
            "pipeline.topic_analysis.min_segment_duration": 90,
            "pipeline.topic_analysis.max_segment_duration": 480,
            "pipeline.topic_analysis.silence_min_duration": 2.0,
            "pipeline.topic_analysis.topic_coherence_threshold": 0.7,
        },
        expected_improvement="主题更完整，减少碎片化切片",
        risk_level="medium",
    ),
    "improve_clip_duration": StrategyResult(
        strategy_name="improve_clip_duration",
        description="优化切片时长范围，偏向更紧凑的切片",
        config_modifications={
            "pipeline.clip_planning.min_clip_duration": 180,
            "pipeline.clip_planning.max_clip_duration": 600,
            "pipeline.clip_planning.optimal_clip_duration": 240,
        },
        expected_improvement="切片更精炼，主题更集中",
        risk_level="medium",
    ),
    "improve_generation_efficiency": StrategyResult(
        strategy_name="improve_generation_efficiency",
        description="优化生成效率：跳过已存在的音视频文件，避免重复剪辑，每次迭代提速30%+",
        config_modifications={
            "pipeline.generation.skip_existing": True,
            "pipeline.generation.parallel_jobs": 2,
            "pipeline.generation.cache_transcript": True,
        },
        expected_improvement="避免重复音视频剪辑，GPU/CPU之外环节零重复，生成速度每次提升30%+",
        risk_level="low",
    ),
    "improve_subtitle_errata": StrategyResult(
        strategy_name="improve_subtitle_errata",
        description="增强字幕勘误：预定义人名宋锐/余传奇，上下文纠知名导演/作品/常识/成语/错别字",
        config_modifications={
            "pipeline.subtitle.errata.predefined_names": ["宋锐", "余传奇"],
            "pipeline.subtitle.errata.context_aware": True,
            "pipeline.subtitle.errata.check_directors": True,
            "pipeline.subtitle.errata.check_works": True,
            "pipeline.subtitle.errata.check_idioms": True,
            "pipeline.subtitle.errata.check_common_words": True,
        },
        expected_improvement="消除人名/作品/成语/常识/错别字等显著用词错误",
        risk_level="low",
    ),
    "improve_subtitle_frosted_glass": StrategyResult(
        strategy_name="improve_subtitle_frosted_glass",
        description="字幕背景采用毛玻璃半透明样式：灰黑色85%不透明+白色文字",
        config_modifications={
            "pipeline.subtitle.render_style.mode": "frosted_glass_dark",
            "pipeline.subtitle.render_style.bg_opacity": 0.85,
            "pipeline.subtitle.render_style.font_color": "white",
            "pipeline.subtitle.render_style.bg_color": "dark_gray",
        },
        expected_improvement="字幕背景灰黑色85%不透明，视觉层次更通透",
        risk_level="low",
    ),
    "improve_asr_phonetic_correction": StrategyResult(
        strategy_name="improve_asr_phonetic_correction",
        description="ASR语音识别纠错：矫正平翘舌不分、韵母混淆、口齿不清导致的词汇错误（如烫化→谈话、互联码→互联网）",
        config_modifications={
            "pipeline.subtitle.errata.asr_phonetic_correction": True,
            "pipeline.subtitle.errata.phonetic_context_window": 3,
            "pipeline.subtitle.errata.check_speech_errors": True,
        },
        expected_improvement="消除ASR语音识别导致的用词语病，提升字幕语义通顺度",
        risk_level="low",
    ),
    "improve_sentence_by_sentence_audit": StrategyResult(
        strategy_name="improve_sentence_by_sentence_audit",
        description="逐句强制字幕勘误：每一条字幕都必须经过语义审查，零容忍错误率，检测语义不通的组合词",
        config_modifications={
            "pipeline.subtitle.errata.sentence_by_sentence": True,
            "pipeline.subtitle.errata.zero_tolerance": True,
            "pipeline.subtitle.errata.semantic_check": True,
        },
        expected_improvement="逐句审查零容忍，确保不存在任何语义不通的字幕",
        risk_level="low",
    ),
    "zero_tolerance_subtitle_overlap": StrategyResult(
        strategy_name="zero_tolerance_subtitle_overlap",
        description="字幕重叠零容忍：任意两条字幕时间区间不得有交集，重叠即一票否决",
        config_modifications={
            "pipeline.subtitle.overlap_check.enabled": True,
            "pipeline.subtitle.overlap_check.zero_tolerance": True,
            "pipeline.subtitle.overlap_check.min_gap_s": 0.04,
        },
        expected_improvement="消除字幕重叠现象，确保任意时刻最多显示一条字幕",
        risk_level="low",
    ),
    "word_level_verification": StrategyResult(
        strategy_name="word_level_verification",
        description="逐词校验：对每句话分词分析，联系前后上下文，精准识别口音/含糊/吞字等ASR错误",
        config_modifications={
            "pipeline.subtitle.word_verify.enabled": True,
            "pipeline.subtitle.word_verify.context_window": 3,
            "pipeline.subtitle.word_verify.phonetic_check": True,
            "pipeline.subtitle.word_verify.context_disambiguation": True,
        },
        expected_improvement="精准识别口音/含糊/吞字导致的ASR误识别，提升字幕逐词准确率",
        risk_level="low",
    ),
}


def get_strategy(name: str) -> StrategyResult | None:
    return STRATEGIES.get(name)


def get_all_strategies() -> dict[str, StrategyResult]:
    return STRATEGIES.copy()


def get_strategies_by_risk(risk_level: str) -> list[StrategyResult]:
    return [s for s in STRATEGIES.values() if s.risk_level == risk_level]


def get_recommended_strategies(current_metrics: PipelineMetrics) -> list[StrategyResult]:
    recommended = []

    if current_metrics.audio_abrupt_start_count > 0 or current_metrics.audio_abrupt_end_count > 0:
        recommended.append(STRATEGIES["improve_cut_points"])
        recommended.append(STRATEGIES["improve_crossfade"])

    if current_metrics.audio_tp_violations > 0:
        recommended.append(STRATEGIES["improve_loudness_target"])

    if current_metrics.subtitle_timing_violations > 0:
        recommended.append(STRATEGIES["improve_subtitle_timing"])

    if current_metrics.subtitle_reading_speed_violations > 0:
        recommended.append(STRATEGIES["improve_subtitle_readability"])

    if current_metrics.critical_issue_count > 3:
        recommended.append(STRATEGIES["improve_topic_segmentation"])

    if current_metrics.subtitle_errata_violations > 0:
        recommended.append(STRATEGIES["improve_subtitle_errata"])
        recommended.append(STRATEGIES["improve_asr_phonetic_correction"])
        recommended.append(STRATEGIES["improve_sentence_by_sentence_audit"])
        recommended.append(STRATEGIES["word_level_verification"])

    if current_metrics.subtitle_overlap_count > 0:
        recommended.append(STRATEGIES["zero_tolerance_subtitle_overlap"])

    if current_metrics.word_level_error_count > 0:
        recommended.append(STRATEGIES["word_level_verification"])

    if current_metrics.generation_efficiency_score < 90:
        recommended.append(STRATEGIES["improve_generation_efficiency"])

    if current_metrics.subtitle_style_score < 90:
        recommended.append(STRATEGIES["improve_subtitle_frosted_glass"])

    if not recommended:
        for strategy in STRATEGIES.values():
            if strategy.risk_level == "low":
                recommended.append(strategy)

    return recommended
