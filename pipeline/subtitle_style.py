from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def _parse_aspect_ratio(spec: str) -> tuple[int, int]:
    parts = spec.replace(":", "/").replace("x", "/").split("/")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    return 16, 9


@dataclass
class OrientationStyle:
    video_width: int = 3840
    video_height: int = 2160
    output_width: int = 1920
    output_height: int = 1080
    font_name: str = "Noto Sans SC"
    font_size: int = 104
    bg_color: str = "1A1A1A"
    bg_alpha: int = 128
    text_color: str = "FFFFFF"
    corner_radius: int = 24
    padding_h: int = 40
    padding_v: int = 20
    margin_v: int = 90
    outline_width: int = 0
    outline_color: str = "000000"
    shadow_enabled: bool = False
    shadow_depth: int = 0
    overlay_content_aspect: str = ""

    @property
    def effective_margin_v(self) -> int:
        if not self.overlay_content_aspect:
            return self.margin_v
        aw, ah = _parse_aspect_ratio(self.overlay_content_aspect)
        content_h = int(self.video_width * ah / aw)
        content_h = content_h + (content_h % 2)
        if content_h >= self.video_height:
            return self.margin_v
        content_bottom = (self.video_height + content_h) // 2
        return self.video_height - content_bottom + self.margin_v

    def to_ass_params(self) -> dict:
        return {
            "video_width": self.video_width,
            "video_height": self.video_height,
            "font_name": self.font_name,
            "font_size": self.font_size,
            "bg_color": self.bg_color,
            "bg_alpha": self.bg_alpha,
            "text_color": self.text_color,
            "corner_radius": self.corner_radius,
            "padding_h": self.padding_h,
            "padding_v": self.padding_v,
            "margin_v": self.effective_margin_v,
        }


@dataclass
class SubtitleStyle:
    name: str = "frosted_glass_dark"
    description: str = ""
    horizontal: OrientationStyle = field(default_factory=OrientationStyle)
    vertical: Optional[OrientationStyle] = None

    def __post_init__(self):
        if self.vertical is None:
            self.vertical = OrientationStyle(
                video_width=1080,
                video_height=1920,
                output_width=1080,
                output_height=1920,
                font_name=self.horizontal.font_name,
                font_size=72,
                bg_color=self.horizontal.bg_color,
                bg_alpha=192,
                text_color=self.horizontal.text_color,
                corner_radius=16,
                padding_h=28,
                padding_v=14,
                margin_v=80,
                overlay_content_aspect="16:9",
            )


_STYLES_DIR = Path(__file__).parent.parent / "config" / "subtitle_styles"
_CACHE: dict[str, SubtitleStyle] = {}


def _parse_orientation(data: dict, defaults: OrientationStyle | None = None) -> OrientationStyle:
    base = defaults or OrientationStyle()
    if not data:
        return base
    kwargs = {}
    for f_name in (
        "video_width", "video_height", "output_width", "output_height",
        "font_name", "font_size", "bg_color", "bg_alpha", "text_color",
        "corner_radius", "padding_h", "padding_v", "margin_v",
        "outline_width", "outline_color", "shadow_enabled", "shadow_depth",
        "overlay_content_aspect",
    ):
        if f_name in data:
            kwargs[f_name] = data[f_name]
    return OrientationStyle(**kwargs)


def load_style(name: str, styles_dir: Path | None = None) -> SubtitleStyle:
    if name in _CACHE:
        return _CACHE[name]

    styles_dir = styles_dir or _STYLES_DIR
    style_path = styles_dir / f"{name}.yaml"

    if not style_path.exists():
        raise FileNotFoundError(
            f"Subtitle style '{name}' not found at {style_path}. "
            f"Available styles: {list_available_styles(styles_dir)}"
        )

    with open(style_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    horizontal = _parse_orientation(data.get("horizontal", {}))
    vertical_data = data.get("vertical")
    vertical = _parse_orientation(vertical_data, defaults=horizontal) if vertical_data else None

    style = SubtitleStyle(
        name=data.get("name", name),
        description=data.get("description", ""),
        horizontal=horizontal,
        vertical=vertical,
    )
    _CACHE[name] = style
    return style


def list_available_styles(styles_dir: Path | None = None) -> list[str]:
    styles_dir = styles_dir or _STYLES_DIR
    if not styles_dir.exists():
        return []
    return sorted(p.stem for p in styles_dir.glob("*.yaml"))


def clear_cache():
    _CACHE.clear()


def get_default_style() -> SubtitleStyle:
    return load_style("frosted_glass_dark")
