from __future__ import annotations

from pathlib import Path
from pipeline.clip_processor import process_clip, _resolve_subtitle_style
from pipeline.subtitle_style import load_style, list_available_styles
from pipeline.config import PipelineConfig
from pipeline.quality_checker import parse_srt_file

VIDEO_SOURCE = Path(r"d:\boke\garden post factory\C0257_mono_video.mp4")
AUDIO_SOURCE = Path(r"d:\boke\garden post factory\C0257_mixed_normalized.wav")
SRT_SOURCE = Path(r"d:\boke\garden post factory\srt\C0257_final.srt")
OUTPUT_BASE = Path(r"d:\boke\garden in parallel - autoresearch\output\style_comparison")

CLIP_START = 2220
CLIP_END = 2280

STYLES = ["frosted_glass_dark", "minimal", "bold_highlight"]
METHODS = ["config_inject", "string_name", "object_load"]


def load_entries():
    srt_entries = parse_srt_file(SRT_SOURCE)
    return srt_entries


def run_method_config_inject(style_name: str, entries: list):
    cfg = PipelineConfig(config_override={
        "pipeline": {
            "subtitle": {
                "render_style": {"name": style_name}
            }
        }
    })
    style = cfg.subtitle_style
    clip_id = f"m1_{style_name}"
    clip_dir = OUTPUT_BASE / "method1_config" / clip_id
    clip = {"id": clip_id, "start_s": CLIP_START, "end_s": CLIP_END, "title": f"Config注入-{style_name}"}
    return process_clip(
        clip=clip,
        clip_dir=clip_dir,
        entries=entries,
        audio_source=AUDIO_SOURCE,
        video_source=VIDEO_SOURCE,
        subtitle_style=style,
        make_vertical=True,
        skip_existing=False,
    )


def run_method_string_name(style_name: str, entries: list):
    clip_id = f"m2_{style_name}"
    clip_dir = OUTPUT_BASE / "method2_string" / clip_id
    clip = {"id": clip_id, "start_s": CLIP_START, "end_s": CLIP_END, "title": f"字符串名-{style_name}"}
    return process_clip(
        clip=clip,
        clip_dir=clip_dir,
        entries=entries,
        audio_source=AUDIO_SOURCE,
        video_source=VIDEO_SOURCE,
        subtitle_style=style_name,
        make_vertical=True,
        skip_existing=False,
    )


def run_method_object_load(style_name: str, entries: list):
    style = load_style(style_name)
    clip_id = f"m3_{style_name}"
    clip_dir = OUTPUT_BASE / "method3_object" / clip_id
    clip = {"id": clip_id, "start_s": CLIP_START, "end_s": CLIP_END, "title": f"对象加载-{style_name}"}
    return process_clip(
        clip=clip,
        clip_dir=clip_dir,
        entries=entries,
        audio_source=AUDIO_SOURCE,
        video_source=VIDEO_SOURCE,
        subtitle_style=style,
        make_vertical=True,
        skip_existing=False,
    )


METHOD_RUNNERS = {
    "config_inject": run_method_config_inject,
    "string_name": run_method_string_name,
    "object_load": run_method_object_load,
}


def main():
    print("=" * 60)
    print("字幕样式对比测试 — 3方式 × 3样式 = 9个视频")
    print("=" * 60)
    print(f"视频源: {VIDEO_SOURCE}")
    print(f"音频源: {AUDIO_SOURCE}")
    print(f"切片: {CLIP_START}s - {CLIP_END}s ({CLIP_END - CLIP_START}s)")
    print(f"可用样式: {list_available_styles()}")
    print(f"输出目录: {OUTPUT_BASE}")
    print()

    entries = load_entries()
    print(f"加载转录条目: {len(entries)} 条")
    print()

    results = []
    total = len(METHODS) * len(STYLES)
    current = 0

    for method in METHODS:
        for style_name in STYLES:
            current += 1
            runner = METHOD_RUNNERS[method]
            print(f"[{current}/{total}] 方式={method}, 样式={style_name}")
            try:
                r = runner(style_name, entries)
                status = "OK" if not r.errors else f"ERR: {r.errors}"
                results.append({
                    "method": method,
                    "style": style_name,
                    "clip_id": r.clip_id,
                    "duration_s": r.duration_s,
                    "subtitles": r.subtitle_count,
                    "video_h": r.video_sub_ok,
                    "video_v": r.video_vertical_ok,
                    "status": status,
                })
                print(f"  -> {status} | 字幕={r.subtitle_count} | 横屏={r.video_sub_ok} | 竖屏={r.video_vertical_ok}")
            except Exception as e:
                results.append({
                    "method": method,
                    "style": style_name,
                    "status": f"EXCEPTION: {e}",
                })
                print(f"  -> EXCEPTION: {e}")
            print()

    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"{'方式':<16} {'样式':<22} {'横屏':>4} {'竖屏':>4} {'状态'}")
    print("-" * 60)
    for r in results:
        print(f"{r['method']:<16} {r['style']:<22} {str(r.get('video_h', '-')):>4} {str(r.get('video_v', '-')):>4} {r['status']}")


if __name__ == "__main__":
    main()
