import re


COMMERCIAL_FREE_FONTS = {
    'Noto Sans SC', 'Noto Sans CJK SC', 'Source Han Sans SC',
    'Noto Serif SC', 'Noto Serif CJK SC', 'Source Han Serif SC',
    'Alibaba PuHuiTi', 'AlibabaSans',
    'HarmonyOS Sans SC',
    'LXGW WenKai', '霞鹜文楷',
    '站酷酷黑体', '站酷快乐体', '站酷高端黑',
}

NON_COMMERCIAL_FONTS = {
    'Microsoft YaHei', '微软雅黑', 'SimHei', '黑体',
    'SimSun', '宋体', 'FangSong', '仿宋', 'KaiTi', '楷体',
    'PingFang SC', 'Hiragino Sans GB',
}

_NOTO_SANS_SC_METRICS = {
    "descent_ratio": 0.154,
    "visible_height_ratio": 0.635,
}


def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_rounded_rect_drawing(w: int, h: int, r: int) -> str:
    r = min(r, w // 2, h // 2)
    return (
        f"m {r} 0 "
        f"l {w - r} 0 "
        f"b {w} 0 {w} {r} {w} {r} "
        f"l {w} {h - r} "
        f"b {w} {h} {w - r} {h} {w - r} {h} "
        f"l {r} {h} "
        f"b 0 {h} 0 {h - r} 0 {h - r} "
        f"l 0 {r} "
        f"b 0 0 {r} 0 {r} 0"
    )


def _measure_text_width(text: str, font_size: int) -> int:
    cjk_width = int(font_size * 0.673)
    ascii_width = int(font_size * 0.37)
    width = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            width += cjk_width
        elif ch.isascii() and ch.isalpha():
            width += ascii_width
        elif ch.isascii() and ch.isdigit():
            width += ascii_width
        elif ch == ' ':
            width += int(font_size * 0.2)
        else:
            width += int(font_size * 0.4)
    return width


def validate_font_license(font_name: str) -> list[dict]:
    issues = []
    if font_name in NON_COMMERCIAL_FONTS:
        issues.append({
            "issue_type": "non_commercial_font",
            "severity": "critical",
            "description": f"字体'{font_name}'不可商用，需替换为商用免费授权字体",
            "suggestion": "使用思源黑体(Noto Sans SC)或阿里巴巴普惠体",
        })
    elif font_name not in COMMERCIAL_FREE_FONTS and font_name not in NON_COMMERCIAL_FONTS:
        issues.append({
            "issue_type": "unknown_font_license",
            "severity": "warning",
            "description": f"字体'{font_name}'授权状态未知，需确认是否可商用",
            "suggestion": "确认字体授权或替换为已知商用免费字体",
        })
    return issues


def validate_render_style(style: dict) -> list[dict]:
    issues = []
    font_name = style.get("font_name", "")
    issues.extend(validate_font_license(font_name))

    font_color = style.get("font_color", "")
    bg_mode = style.get("mode", "")
    if bg_mode == "frosted_glass_dark" and font_color != "white":
        issues.append({
            "issue_type": "render_style_mismatch",
            "severity": "warning",
            "description": "毛玻璃暗色背景应使用白色字体",
            "suggestion": "设置font_color为white",
        })

    bg_opacity = style.get("bg_opacity", 0)
    if bg_mode == "frosted_glass_dark" and (bg_opacity < 0.4 or bg_opacity > 0.8):
        issues.append({
            "issue_type": "bg_opacity_out_of_range",
            "severity": "warning",
            "description": f"毛玻璃背景不透明度{bg_opacity}不在推荐范围0.4-0.8内",
            "suggestion": "调整bg_opacity至0.5-0.7之间",
        })

    return issues


def generate_ass_with_rounded_bg(
    entries: list[dict],
    video_width: int = 3840,
    video_height: int = 2160,
    font_name: str = "Noto Sans SC",
    font_size: int = 104,
    bg_color: str = "1A1A1A",
    bg_alpha: int = 38,
    text_color: str = "FFFFFF",
    corner_radius: int = 24,
    padding_h: int = 40,
    padding_v: int = 20,
    margin_v: int = 90,
) -> str:
    bg_alpha_hex = f"{bg_alpha:02X}"
    metrics = _NOTO_SANS_SC_METRICS
    descent = int(font_size * metrics["descent_ratio"])
    visible_h = int(font_size * metrics["visible_height_ratio"])

    ass = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{font_size},"
        f"&H00{text_color},&H000000FF,&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    cx = video_width // 2
    text_pos_y = video_height - margin_v

    for entry in entries:
        start = _format_ass_time(entry["start_s"])
        end = _format_ass_time(entry["end_s"])
        text = entry["text"]

        text_width = _measure_text_width(text, font_size)
        max_w = int(video_width * 0.85)
        text_width = min(text_width, max_w)

        text_top = text_pos_y - descent - visible_h
        text_left = cx - text_width // 2

        bg_x = text_left - padding_h
        bg_y = text_top - padding_v
        bg_w = text_width + padding_h * 2
        bg_h = visible_h + padding_v * 2

        r = min(corner_radius, bg_w // 2, bg_h // 2)

        drawing = _ass_rounded_rect_drawing(bg_w, bg_h, r)

        ass += (
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
            f"{{\\an7\\pos({bg_x},{bg_y})\\1c&H{bg_color}&\\1a&H{bg_alpha_hex}&"
            f"\\3a&HFF&\\4a&HFF&\\p1}}{drawing}{{\\p0}}\n"
        )
        ass += (
            f"Dialogue: 1,{start},{end},Default,,0,0,0,,"
            f"{{\\an2\\pos({cx},{text_pos_y})}}{text}\n"
        )

    return ass


def get_frosted_glass_ffmpeg_filter(
    video_width: int = 3840,
    video_height: int = 2160,
    blur_radius: int = 12,
    band_height: int = 120,
    margin_v: int = 50,
) -> str:
    y_start = video_height - margin_v - band_height
    return (
        f"split[original][blurred];"
        f"[blurred]crop={video_width}:{band_height}:0:{y_start},boxblur={blur_radius}:{blur_radius}[blurred_band];"
        f"[original][blurred_band]overlay=0:{y_start}"
    )
