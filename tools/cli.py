import json
import click
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
from pipeline.config import PipelineConfig


@click.group()
def cli():
    """Garden AutoResearch — 播客视频制作自主研究框架"""
    pass


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True), help="项目目录路径")
@click.option("--series", "-s", type=str, help="系列名称 (如 highlights, philosophy, deep_thinking)")
@click.option("--make-vertical/--no-vertical", default=False, help="是否生成竖屏视频")
@click.option("--make-srt/--no-srt", default=True, help="是否生成SRT字幕")
@click.option("--max-chars", default=18, help="每行最大字符数")
@click.option("--strip-punctuation/--keep-punctuation", default=True, help="是否移除标点")
@click.option("--subtitle-mode", type=click.Choice(["single_cn", "single_en", "bilingual"]), default="single_cn", help="字幕模式")
def clip(project_dir, series, make_vertical, make_srt, max_chars, strip_punctuation, subtitle_mode):
    """基于项目配置运行剪辑 pipeline"""
    from pipeline.loader import load_project
    from pipeline.clip_processor import process_series

    if not project_dir:
        click.echo("请指定项目目录: --project-dir / -p")
        return

    config = PipelineConfig(project_dir=Path(project_dir))
    ctx = load_project(config=config)

    click.echo(f"项目: {config.project_name}")
    click.echo(f"转录条目: {len(ctx.entries)}")
    click.echo(f"勘误条目: {len(ctx.custom_errata)}")

    if series:
        series_names = [series]
    else:
        all_clips = config.get_all_clips()
        series_names = list(all_clips.keys())

    for series_name in series_names:
        clips = config.get_clips(series_name)
        if not clips:
            click.echo(f"系列 '{series_name}' 无切片定义，跳过")
            continue

        output_dir = config.output_dir / "clips" / series_name
        click.echo(f"\n处理系列: {series_name} ({len(clips)} 切片)")

        results = process_series(
            clips=clips,
            series_dir=output_dir,
            entries=ctx.entries,
            audio_source=config.source_audio,
            video_source=config.source_video,
            custom_errata=ctx.custom_errata,
            make_vertical=make_vertical,
            make_srt=make_srt,
            skip_existing=True,
            max_chars=max_chars,
            strip_punctuation=strip_punctuation,
            subtitle_mode=subtitle_mode,
            series_name=series_name,
            project_name=config.project_name,
        )

        generated = sum(1 for r in results if not r.errors)
        click.echo(f"  完成: {generated}/{len(results)} 成功")

    click.echo("\n✅ 剪辑完成")


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True), help="项目目录路径")
@click.option("--platform", "-P", multiple=True, help="目标平台 (bilibili/douyin/youtube/xiaoyuzhou/apple_podcasts/archive)")
def export(project_dir, platform):
    """导出到指定平台"""
    from pipeline.loader import load_project
    from pipeline.exporter import export_for_platform, export_all_platforms

    if not project_dir:
        click.echo("请指定项目目录: --project-dir / -p")
        return

    config = PipelineConfig(project_dir=Path(project_dir))
    output_dir = config.output_dir

    video_files = list(output_dir.rglob("*_subtitled.mp4"))
    if not video_files:
        video_files = list(output_dir.rglob("*.mp4"))

    if not video_files:
        click.echo("未找到视频文件。请先运行 clip 命令。")
        return

    sample_video = video_files[0]
    click.echo(f"导出样本: {sample_video.name}")

    platforms = list(platform) if platform else ["bilibili", "douyin", "youtube", "xiaoyuzhou", "apple_podcasts", "archive"]

    results = export_all_platforms(
        sample_video,
        output_dir / "platforms",
        platforms,
        config,
    )

    for result in results:
        icon = "✅" if result.success else "❌"
        click.echo(f"  {icon} {result.platform}: {result.file_size_mb:.1f}MB")


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True), help="项目目录路径")
def quality(project_dir):
    """运行质量检查"""
    from pipeline.loader import load_project
    from pipeline.quality_checker import run_quality_check

    if not project_dir:
        click.echo("请指定项目目录: --project-dir / -p")
        return

    config = PipelineConfig(project_dir=Path(project_dir))
    ctx = load_project(config=config)

    for series_name in config.get_all_clips():
        series_dir = config.output_dir / "clips" / series_name
        if not series_dir.exists():
            continue

        report = run_quality_check(series_dir, config, version_key=series_name)
        icon = "✅" if report.passed else "❌"
        click.echo(f"  {icon} {series_name}: 分数={report.overall_score:.1f}, 严重={len(report.critical_issues)}, 警告={len(report.warnings)}")

        if report.recommendations:
            for rec in report.recommendations:
                click.echo(f"     📋 {rec}")


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True), help="项目目录路径")
@click.option("--max-experiments", "-n", default=3, help="最大实验次数")
@click.option("--regenerate/--no-regenerate", default=True, help="每次实验是否重新生成视频")
def autoresearch(project_dir, max_experiments, regenerate):
    """自动迭代改进"""
    from pipeline.loader import load_project
    from pipeline.quality_checker import run_quality_check
    from pipeline.clip_processor import process_series
    from autoresearch.experiment import Experiment
    from autoresearch.strategies import get_recommended_strategies
    from autoresearch.metrics import compute_metrics_from_quality_report

    if not project_dir:
        click.echo("请指定项目目录: --project-dir / -p")
        return

    config = PipelineConfig(project_dir=Path(project_dir))
    ctx = load_project(config=config)

    for series_name in config.get_all_clips():
        series_dir = config.output_dir / "clips" / series_name
        if not series_dir.exists():
            continue

        baseline = run_quality_check(series_dir, config, version_key=f"auto_{series_name}")
        baseline_metrics = compute_metrics_from_quality_report(baseline)

        if baseline.passed:
            click.echo(f"  ✅ {series_name} 已通过质量检查，跳过优化")
            continue

        click.echo(f"\n🔧 优化 {series_name} (基线分数: {baseline.overall_score:.1f})")

        experiment_dir = config.output_dir / "experiments" / series_name
        experiment = Experiment(config=config, log_dir=experiment_dir, direction="general_quality")
        experiment.set_baseline(baseline)

        strategies = get_recommended_strategies(baseline_metrics)
        for i, strategy in enumerate(strategies[:max_experiments]):
            click.echo(f"  策略 {i+1}: {strategy.strategy_name}")

            def _make_quality_fn(sn, sd, idx):
                def quality_fn(cfg):
                    if regenerate:
                        clips = cfg.get_clips(sn)
                        if clips:
                            process_series(
                                clips=clips,
                                series_dir=sd,
                                entries=ctx.entries,
                                audio_source=cfg.source_audio,
                                video_source=cfg.source_video,
                                custom_errata=ctx.custom_errata,
                                make_vertical=True,
                                make_srt=True,
                                skip_existing=False,
                                max_chars=cfg.get("pipeline.subtitle.max_chars_per_line_cn", 18),
                                strip_punctuation=True,
                                series_name=sn,
                                project_name=cfg.project_name,
                            )
                    return run_quality_check(sd, cfg, version_key=f"auto_{sn}_exp_{idx+1}")
                return quality_fn

            record = experiment.run_experiment(
                config_modifications=strategy.config_modifications,
                quality_report_fn=_make_quality_fn(series_name, series_dir, i),
                notes=f"Autoresearch for {series_name}: {strategy.strategy_name}",
            )

            icon = "📈" if record.improved else "📉" if not record.kept else "➡️"
            click.echo(f"    {icon} improved={record.improved}, kept={record.kept}")

        status = experiment.get_status()
        click.echo(f"  最终分数: {status.get('current_score', 'N/A')}")


@cli.command()
def status():
    """查看当前状态"""
    config = PipelineConfig()
    output_dir = config.output_dir

    click.echo("=" * 60)
    click.echo("Garden AutoResearch — 状态概览")
    click.echo("=" * 60)

    quality_reports = list(output_dir.rglob("quality_report.json"))
    if quality_reports:
        click.echo(f"\n✅ 质量报告: {len(quality_reports)} 个")
        for qr_path in quality_reports:
            with open(qr_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            version = report.get("version_key", qr_path.parent.name)
            score = report.get("overall_score", 0)
            passed = report.get("passed", False)
            critical = len(report.get("critical_issues", []))
            warnings = len(report.get("warnings", []))
            status_icon = "✅" if passed else "❌"
            click.echo(f"   {status_icon} {version}: 分数={score:.1f}, 严重={critical}, 警告={warnings}")
    else:
        click.echo("\n✅ 质量报告: 无（请先运行 clip 命令）")

    clips_count = len(list(output_dir.rglob("*.wav"))) if output_dir.exists() else 0
    srt_count = len(list(output_dir.rglob("*.srt"))) if output_dir.exists() else 0
    ass_count = len(list(output_dir.rglob("*.ass"))) if output_dir.exists() else 0
    video_count = len(list(output_dir.rglob("*.mp4"))) if output_dir.exists() else 0
    click.echo(f"\n📁 输出文件: {clips_count} 音频 | {srt_count} SRT | {ass_count} ASS | {video_count} 视频")

    from autoresearch.strategies import get_all_strategies
    strategies = get_all_strategies()
    click.echo(f"\n🔧 可用策略: {len(strategies)} 个")
    for name, strategy in strategies.items():
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(strategy.risk_level, "⚪")
        click.echo(f"   {risk_icon} {name}: {strategy.description}")


@cli.command()
@click.option("--project-dir", "-p", type=click.Path(exists=True), help="项目目录路径")
def audit(project_dir):
    """对项目输出进行质量审计"""
    from pipeline.loader import load_project
    from pipeline.quality_checker import run_quality_check

    if not project_dir:
        click.echo("请指定项目目录: --project-dir / -p")
        return

    config = PipelineConfig(project_dir=Path(project_dir))
    ctx = load_project(config=config)

    click.echo(f"项目: {config.project_name}")
    click.echo(f"描述: {config.project_description}")
    click.echo(f"转录条目: {len(ctx.entries)}")
    click.echo(f"勘误条目: {len(ctx.custom_errata)}")

    all_series = config.get_all_clips()
    click.echo(f"系列: {', '.join(f'{k}({len(v)})' for k, v in all_series.items())}")

    for series_name, clips in all_series.items():
        series_dir = config.output_dir / "clips" / series_name
        if not series_dir.exists():
            click.echo(f"\n  ⚠️ {series_name}: 未生成")
            continue

        report = run_quality_check(series_dir, config, version_key=f"audit_{series_name}")
        icon = "✅" if report.passed else "❌"
        click.echo(f"\n  {icon} {series_name}: 分数={report.overall_score:.1f}")

        if report.critical_issues:
            click.echo(f"     🔴 严重问题 ({len(report.critical_issues)}):")
            for issue in report.critical_issues[:5]:
                click.echo(f"        [{issue.get('issue_type')}] {issue.get('description')}")

        if report.warnings:
            click.echo(f"     🟡 警告 ({len(report.warnings)}):")
            for issue in report.warnings[:5]:
                click.echo(f"        [{issue.get('issue_type')}] {issue.get('description')}")

        if report.recommendations:
            click.echo(f"     📋 建议:")
            for rec in report.recommendations:
                click.echo(f"        {rec}")


@cli.command()
@click.option("--source", "-s", type=click.Path(exists=True), required=True, help="截图或视频文件路径")
@click.option("--name", "-n", default="extracted_style", help="输出样式名称")
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录 (默认: config/subtitle_styles)")
@click.option("--verify/--no-verify", default=True, help="是否生成验证 ASS 文件")
@click.option("--timestamps", "-t", multiple=True, type=float, help="视频提取时间点 (秒)")
@click.option("--max-frames", default=5, help="从视频中提取的最大帧数")
def extract_subtitle_style(source, name, output_dir, verify, timestamps, max_frames):
    """从截图或视频中提取字幕样式并生成配置文件"""
    from pipeline.subtitle_style_extractor import extract_and_save, verify_extracted_style

    ts_list = list(timestamps) if timestamps else None

    style, yaml_path = extract_and_save(
        source=source,
        output_name=name,
        output_dir=output_dir,
        timestamps=ts_list,
        max_frames=max_frames,
    )

    click.echo(f"✅ 样式提取完成")
    click.echo(f"   名称: {style.name}")
    click.echo(f"   描述: {style.description}")
    click.echo(f"   配置文件: {yaml_path}")

    h = style.horizontal
    click.echo(f"\n   横版样式:")
    click.echo(f"     分辨率: {h.video_width}x{h.video_height}")
    click.echo(f"     字体: {h.font_name} {h.font_size}px {'粗体' if h.bold else ''}")
    click.echo(f"     文字色: #{h.text_color}")
    click.echo(f"     背景: {'启用' if h.bg_enabled else '禁用'} #{h.bg_color} alpha={h.bg_alpha}")
    click.echo(f"     描边: {h.outline_width}px #{h.outline_color}")
    click.echo(f"     阴影: {h.shadow_depth}px #{h.shadow_color}")
    click.echo(f"     圆角: {h.corner_radius}")
    click.echo(f"     边距: margin_v={h.margin_v}, padding_h={h.padding_h}, padding_v={h.padding_v}")

    v = style.vertical
    click.echo(f"\n   竖版样式:")
    click.echo(f"     分辨率: {v.video_width}x{v.video_height}")
    click.echo(f"     字体: {v.font_name} {v.font_size}px {'粗体' if v.bold else ''}")

    if verify:
        verify_dir = Path(output_dir) / "verify" if output_dir else Path(yaml_path).parent / "verify"
        results = verify_extracted_style(style, output_dir=verify_dir)
        for orient, data in results.items():
            if data:
                click.echo(f"\n   验证 ({orient}): {'✅' if data.get('has_text') else '❌'} ASS 生成{'成功' if data.get('has_text') else '失败'}")
                if data.get("ass_path"):
                    click.echo(f"     文件: {data['ass_path']}")


@cli.command()
def strategies():
    """列出所有改进策略"""
    from autoresearch.strategies import get_all_strategies

    all_strategies = get_all_strategies()
    click.echo("=" * 60)
    click.echo("可用改进策略")
    click.echo("=" * 60)

    for name, strategy in all_strategies.items():
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(strategy.risk_level, "⚪")
        click.echo(f"\n{risk_icon} {name}")
        click.echo(f"   描述: {strategy.description}")
        click.echo(f"   预期改进: {strategy.expected_improvement}")
        click.echo(f"   风险: {strategy.risk_level}")
        click.echo(f"   参数修改:")
        for key, value in strategy.config_modifications.items():
            click.echo(f"      {key} = {value}")


if __name__ == "__main__":
    cli()
