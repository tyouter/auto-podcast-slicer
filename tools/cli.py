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
@click.argument("source", type=click.Path(exists=True))
@click.option("--config", "-c", type=click.Path(), help="自定义配置文件路径")
def run(source, config):
    """运行完整 pipeline"""
    from tools.run_pipeline import run_full_pipeline

    config_obj = PipelineConfig()
    if config:
        import yaml
        with open(config, "r", encoding="utf-8") as f:
            override = yaml.safe_load(f)
        config_obj = PipelineConfig(override)

    source_path = Path(source)
    result = run_full_pipeline(source_path, config_obj)
    click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@cli.command()
@click.argument("strategy")
@click.option("--source", "-s", type=click.Path(), help="源媒体文件路径")
def experiment(strategy, source):
    """运行单个实验策略"""
    from tools.run_experiment import run_single_experiment

    source_path = Path(source) if source else None
    result = run_single_experiment(strategy, source_path)
    click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--max-experiments", "-n", default=10, help="最大实验次数")
def auto(source, max_experiments):
    """自动迭代改进"""
    from tools.run_experiment import run_auto_iteration

    source_path = Path(source)
    result = run_auto_iteration(source_path, max_experiments)
    click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@cli.command()
def status():
    """查看当前状态"""
    config = PipelineConfig()
    output_dir = config.output_dir

    click.echo("=" * 60)
    click.echo("Garden AutoResearch — 状态概览")
    click.echo("=" * 60)

    # Check experiments
    exp_log = output_dir / "experiments" / "experiment_log.json"
    if exp_log.exists():
        with open(exp_log, "r", encoding="utf-8") as f:
            records = json.load(f)
        click.echo(f"\n📊 实验记录: {len(records)} 次")
        improvements = sum(1 for r in records if r.get("improved"))
        click.echo(f"   改进: {improvements} | 退步: {len(records) - improvements}")
        if records:
            latest = records[-1]
            click.echo(f"   最近实验: {latest.get('experiment_id', 'N/A')}")
            click.echo(f"   改进: {latest.get('improved', False)} | 保留: {latest.get('kept', False)}")
    else:
        click.echo("\n📊 实验记录: 无")

    # Check quality reports
    quality_reports = list(output_dir.glob("clips/*/quality_report.json"))
    if quality_reports:
        click.echo(f"\n✅ 质量报告: {len(quality_reports)} 个版本")
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
        click.echo("\n✅ 质量报告: 无（请先运行 pipeline）")

    # Check output files
    clips_count = len(list(output_dir.glob("clips/*/*.wav"))) if output_dir.exists() else 0
    srt_count = len(list(output_dir.glob("srt/*.srt"))) if output_dir.exists() else 0
    click.echo(f"\n📁 输出文件: {clips_count} 音频 | {srt_count} 字幕")

    # Available strategies
    from autoresearch.strategies import get_all_strategies
    strategies = get_all_strategies()
    click.echo(f"\n🔧 可用策略: {len(strategies)} 个")
    for name, strategy in strategies.items():
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(strategy.risk_level, "⚪")
        click.echo(f"   {risk_icon} {name}: {strategy.description}")


@cli.command()
@click.option("--version", "-v", type=str, help="版本名称")
def report(version):
    """查看质量报告"""
    config = PipelineConfig()
    output_dir = config.output_dir

    if version:
        report_path = output_dir / "clips" / version / "quality_report.json"
    else:
        reports = list(output_dir.glob("clips/*/quality_report.json"))
        if reports:
            report_path = reports[0]
        else:
            click.echo("未找到质量报告。请先运行 pipeline。")
            return

    if not report_path.exists():
        click.echo(f"质量报告不存在: {report_path}")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    click.echo("=" * 60)
    click.echo(f"质量报告 — {data.get('version_key', 'N/A')}")
    click.echo("=" * 60)
    click.echo(f"\n总分: {data.get('overall_score', 0):.1f}/100")
    click.echo(f"通过: {'✅ 是' if data.get('passed') else '❌ 否'}")
    click.echo(f"严重问题: {len(data.get('critical_issues', []))}")
    click.echo(f"警告: {len(data.get('warnings', []))}")

    if data.get("recommendations"):
        click.echo("\n📋 建议:")
        for rec in data["recommendations"]:
            click.echo(f"   • {rec}")

    if data.get("critical_issues"):
        click.echo("\n🔴 严重问题:")
        for issue in data["critical_issues"]:
            click.echo(f"   • [{issue.get('issue_type')}] {issue.get('description')}")

    if data.get("warnings"):
        click.echo("\n🟡 警告:")
        for issue in data["warnings"][:10]:
            click.echo(f"   • [{issue.get('issue_type')}] {issue.get('description')}")


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


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--platform", "-p", multiple=True, help="目标平台 (bilibili/douyin/youtube/xiaoyuzhou)")
def export(source, platform):
    """导出到指定平台"""
    from pipeline.exporter import export_for_platform

    config = PipelineConfig()
    source_path = Path(source)

    platforms = list(platform) if platform else ["bilibili", "youtube"]
    output_dir = config.output_dir / "exports"

    for plat in platforms:
        click.echo(f"导出到 {plat}...")
        result = export_for_platform(source_path, output_dir / plat, plat, config)
        if result.success:
            click.echo(f"  ✅ 成功: {result.output_path}")
            click.echo(f"     大小: {result.file_size_mb:.1f}MB | 时长: {result.duration_s:.1f}s")
        else:
            click.echo(f"  ❌ 失败: {', '.join(result.issues)}")


if __name__ == "__main__":
    cli()
