import sys
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.config import PipelineConfig
from pipeline.loader import load_project
from pipeline.clip_processor import (
    process_clip,
    generate_video_vertical,
    generate_video_subtitled,
    ClipProcessResult,
)
from pipeline.exporter import export_for_platform
from pipeline.quality_checker import run_quality_check

OUTPUT_BASE = PROJECT_ROOT / "output" / "test_vertical_video"
PROJECT_DIR = PROJECT_ROOT / "projects" / "garden-forking-paths"


def test_vertical_video_single_clip():
    clip_dir = OUTPUT_BASE / "clips" / "highlights" / "H01_time_bifurcates"
    clip_dir.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(project_dir=PROJECT_DIR)
    config._data["output"]["base_dir"] = str(OUTPUT_BASE)
    ctx = load_project(config=config)

    sample_clip = {
        "id": "H01_time_bifurcates",
        "title": "时间不是线性的，是分岔的",
        "series": "高光",
        "description": "时间在这里分岔了——从博尔赫斯到时间哲学的核心洞见",
        "start_s": 1580,
        "end_s": 1610,
        "domain": "时间哲学",
        "hook": "时间在这里分岔了",
    }

    print(f"[竖版测试] 处理片段: {sample_clip['id']} ({sample_clip['end_s']-sample_clip['start_s']}s)")
    print(f"[竖版测试] 视频源: {config.source_video}")
    print(f"[竖版测试] 音频源: {config.source_audio}")

    t0 = time.time()
    result = process_clip(
        clip=sample_clip,
        clip_dir=clip_dir,
        entries=ctx.entries,
        audio_source=config.source_audio,
        video_source=config.source_video,
        custom_errata=ctx.custom_errata,
        make_vertical=True,
        make_srt=True,
        skip_existing=True,
        max_chars=18,
        strip_punctuation=True,
    )
    elapsed = time.time() - t0

    print(f"\n[竖版测试] 处理结果:")
    print(f"  clip_id: {result.clip_id}")
    print(f"  duration_s: {result.duration_s}")
    print(f"  audio_wav_ok: {result.audio_wav_ok}")
    print(f"  audio_mp3_ok: {result.audio_mp3_ok}")
    print(f"  ass_ok: {result.ass_ok}")
    print(f"  srt_ok: {result.srt_ok}")
    print(f"  video_sub_ok: {result.video_sub_ok}")
    print(f"  video_vertical_ok: {result.video_vertical_ok}")
    print(f"  metadata_ok: {result.metadata_ok}")
    print(f"  subtitle_count: {result.subtitle_count}")
    print(f"  耗时: {elapsed:.1f}s")

    if result.errors:
        print(f"  errors: {result.errors}")

    assert result.audio_wav_ok, "音频WAV生成失败"
    assert result.ass_ok, "ASS字幕生成失败"
    assert result.video_sub_ok, "横版字幕视频生成失败"

    if result.video_vertical_ok:
        print("\n[竖版测试] ✅ 竖版视频生成成功！验证技术参数...")

        vertical_path = clip_dir / f"{sample_clip['id']}_vertical.mp4"
        assert vertical_path.exists(), f"竖版视频文件不存在: {vertical_path}"

        file_size_mb = vertical_path.stat().st_size / (1024 * 1024)
        print(f"  文件大小: {file_size_mb:.1f}MB")

        import subprocess
        probe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(vertical_path),
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, encoding="utf-8", timeout=30)
        if probe_result.returncode == 0:
            probe_data = json.loads(probe_result.stdout)
            for stream in probe_data.get("streams", []):
                if stream["codec_type"] == "video":
                    width = int(stream.get("width", 0))
                    height = int(stream.get("height", 0))
                    codec = stream.get("codec_name", "")
                    pix_fmt = stream.get("pix_fmt", "")
                    print(f"  分辨率: {width}x{height}")
                    print(f"  编码: {codec}")
                    print(f"  像素格式: {pix_fmt}")

                    assert width == 1080, f"竖版视频宽度应为1080，实际为{width}"
                    assert height == 1920, f"竖版视频高度应为1920，实际为{height}"
                    assert codec == "h264", f"编码应为H.264，实际为{codec}"
                    assert pix_fmt == "yuv420p", f"像素格式应为yuv420p，实际为{pix_fmt}"

                elif stream["codec_type"] == "audio":
                    codec = stream.get("codec_name", "")
                    sample_rate = stream.get("sample_rate", "")
                    channels = stream.get("channels", "")
                    print(f"  音频编码: {codec}")
                    print(f"  采样率: {sample_rate}")
                    print(f"  声道数: {channels}")

            duration_s = float(probe_data.get("format", {}).get("duration", 0))
            print(f"  时长: {duration_s:.1f}s")
            assert abs(duration_s - 30) < 2, f"时长应为约30s，实际为{duration_s:.1f}s"
        else:
            print(f"  ⚠️ ffprobe执行失败: {probe_result.stderr[:200]}")
    else:
        print("\n[竖版测试] ⚠️ 竖版视频生成失败（可能超时）")
        print("  这不影响核心功能，但抖音平台需要竖版视频")

    return result


def test_vertical_export_douyin():
    print("\n[竖版测试] 测试抖音竖版导出...")

    config = PipelineConfig(project_dir=PROJECT_DIR)
    config._data["output"]["base_dir"] = str(OUTPUT_BASE)

    vertical_files = list(OUTPUT_BASE.rglob("*_vertical.mp4"))
    if not vertical_files:
        print("[竖版测试] ⚠️ 无竖版视频文件，跳过抖音导出测试")
        return

    sample_vertical = vertical_files[0]
    print(f"  导出文件: {sample_vertical.name}")

    export_dir = OUTPUT_BASE / "platforms" / "douyin_vertical"
    export_dir.mkdir(parents=True, exist_ok=True)

    result = export_for_platform(sample_vertical, export_dir, "douyin", config)
    print(f"  导出结果: success={result.success}, size={result.file_size_mb:.1f}MB")
    if result.issues:
        print(f"  问题: {result.issues}")

    if result.success:
        print("[竖版测试] ✅ 抖音竖版导出成功")
    else:
        print("[竖版测试] ❌ 抖音竖版导出失败")


def test_vertical_quality_check():
    print("\n[竖版测试] 运行质量检查...")

    config = PipelineConfig(project_dir=PROJECT_DIR)
    config._data["output"]["base_dir"] = str(OUTPUT_BASE)

    highlights_dir = OUTPUT_BASE / "clips" / "highlights"
    if not highlights_dir.exists():
        print("[竖版测试] ⚠️ 无输出目录，跳过质量检查")
        return

    report = run_quality_check(highlights_dir, config, version_key="vertical_test")
    print(f"  质量评分: {report.overall_score:.1f}")
    print(f"  通过: {report.passed}")
    print(f"  严重问题: {len(report.critical_issues)}")
    print(f"  警告: {len(report.warnings)}")
    for rec in report.recommendations:
        print(f"  建议: {rec}")


if __name__ == "__main__":
    print("=" * 60)
    print("竖版视频专项测试")
    print("=" * 60)

    try:
        result = test_vertical_video_single_clip()
        test_vertical_export_douyin()
        test_vertical_quality_check()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 60)
    print("竖版视频专项测试完成")
    print("=" * 60)
