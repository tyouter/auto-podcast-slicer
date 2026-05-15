from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline.subtitle_style_extractor import (
    ExtractedStyle,
    extract_and_save,
    extract_frames_from_video,
    extract_style_from_frame,
    extract_style_from_image,
    extract_style_from_video,
    extracted_to_orientation_style,
    generate_style_config,
    save_style_yaml,
    verify_extracted_style,
)
from pipeline.subtitle_style import OrientationStyle, SubtitleStyle, load_style


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _create_test_frame(
    width: int = 1920,
    height: int = 1080,
    bg_color: tuple = (40, 40, 50),
    subtitle_text: str = "Test Subtitle",
    text_color: tuple = (255, 255, 255),
    subtitle_bg_color: tuple | None = (26, 26, 26),
    subtitle_y: int = 900,
) -> np.ndarray:
    img = np.full((height, width, 3), bg_color, dtype=np.uint8)

    if subtitle_bg_color is not None:
        bg_x = width // 4
        bg_w = width // 2
        bg_h = 80
        cv2.rectangle(img, (bg_x, subtitle_y), (bg_x + bg_w, subtitle_y + bg_h), subtitle_bg_color, -1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(subtitle_text, font, 1.5, 3)[0]
    text_x = (width - text_size[0]) // 2
    text_y = subtitle_y + 55
    cv2.putText(img, subtitle_text, (text_x, text_y), font, 1.5, text_color, 3, cv2.LINE_AA)

    return img


def _create_vertical_frame(**kwargs) -> np.ndarray:
    kwargs.setdefault("width", 1080)
    kwargs.setdefault("height", 1920)
    kwargs.setdefault("subtitle_y", 1600)
    return _create_test_frame(**kwargs)


@pytest.fixture
def test_frame():
    return _create_test_frame()


@pytest.fixture
def test_frame_no_bg():
    return _create_test_frame(subtitle_bg_color=None)


@pytest.fixture
def vertical_frame():
    return _create_vertical_frame()


@pytest.fixture
def tmp_image(tmp_path, test_frame):
    path = tmp_path / "test_frame.png"
    cv2.imwrite(str(path), test_frame)
    return path


@pytest.fixture
def tmp_video(tmp_path, test_frame):
    path = tmp_path / "test_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 24.0, (test_frame.shape[1], test_frame.shape[0]))
    for _ in range(72):
        writer.write(test_frame)
    writer.release()
    return path


class TestExtractStyleFromFrame:
    def test_basic_extraction(self, test_frame):
        result = extract_style_from_frame(test_frame)
        assert isinstance(result, ExtractedStyle)
        assert result.confidence > 0
        assert len(result.text_color) == 6
        assert result.is_vertical is False

    def test_text_color_detection(self, test_frame):
        result = extract_style_from_frame(test_frame)
        r = int(result.text_color[0:2], 16)
        g = int(result.text_color[2:4], 16)
        b = int(result.text_color[4:6], 16)
        assert r > 200 or g > 200 or b > 200

    def test_bg_detection(self, test_frame):
        result = extract_style_from_frame(test_frame)
        assert result.bg_enabled is True

    def test_no_bg_detection(self, test_frame_no_bg):
        result = extract_style_from_frame(test_frame_no_bg)
        assert isinstance(result, ExtractedStyle)

    def test_vertical_detection(self, vertical_frame):
        result = extract_style_from_frame(vertical_frame)
        assert result.is_vertical is True
        assert result.video_width == 1080
        assert result.video_height == 1920

    def test_font_size_estimation(self, test_frame):
        result = extract_style_from_frame(test_frame)
        assert result.font_size > 0

    def test_margin_estimation(self, test_frame):
        result = extract_style_from_frame(test_frame)
        assert result.margin_v > 0


class TestExtractStyleFromImage:
    def test_from_image_file(self, tmp_image):
        result = extract_style_from_image(tmp_image)
        assert isinstance(result, ExtractedStyle)
        assert result.confidence > 0

    def test_invalid_path(self):
        with pytest.raises(ValueError, match="Cannot read image"):
            extract_style_from_image("/nonexistent/image.png")


class TestExtractStyleFromVideo:
    def test_from_video_file(self, tmp_video):
        result = extract_style_from_video(tmp_video, max_frames=2)
        assert isinstance(result, ExtractedStyle)

    def test_invalid_video(self):
        with pytest.raises(ValueError, match="Cannot open video|No frames extracted"):
            extract_style_from_video("/nonexistent/video.mp4")


class TestExtractFramesFromVideo:
    def test_extract_multiple_frames(self, tmp_video):
        frames = extract_frames_from_video(tmp_video, max_frames=3)
        assert len(frames) >= 1
        for f in frames:
            assert isinstance(f, np.ndarray)
            assert f.ndim == 3

    def test_custom_timestamps(self, tmp_video):
        frames = extract_frames_from_video(tmp_video, timestamps=[0.5, 1.0, 1.5])
        assert len(frames) >= 1


class TestExtractedToOrientationStyle:
    def test_horizontal_conversion(self):
        extracted = ExtractedStyle(
            text_color="FF0000",
            bg_enabled=True,
            bg_color="0000FF",
            font_size=80,
            margin_v=100,
        )
        style = extracted_to_orientation_style(extracted, is_vertical=False)
        assert isinstance(style, OrientationStyle)
        assert style.text_color == "FF0000"
        assert style.bg_enabled is True
        assert style.bg_color == "0000FF"
        assert style.font_size == 96  # default — style copy doesn't transfer font size
        assert style.video_width == 3840
        assert style.video_height == 2160

    def test_vertical_conversion(self):
        extracted = ExtractedStyle(
            text_color="FF0000",
            bg_enabled=True,
            bg_color="0000FF",
            font_size=80,
            margin_v=100,
        )
        style = extracted_to_orientation_style(extracted, is_vertical=True)
        assert style.video_width == 1080
        assert style.video_height == 1920
        assert style.font_size < 80
        assert style.text_color == "FF0000"

    def test_numpy_type_safety(self):
        extracted = ExtractedStyle(
            font_size=int(np.int64(80)),
            bold=bool(np.bool_(True)),
            margin_v=int(np.int32(100)),
        )
        style = extracted_to_orientation_style(extracted, is_vertical=False)
        assert isinstance(style.font_size, int)
        assert isinstance(style.bold, bool)
        assert isinstance(style.margin_v, int)


class TestGenerateStyleConfig:
    def test_basic_config(self):
        extracted = ExtractedStyle(
            text_color="FFFFFF",
            bg_enabled=True,
            bg_color="1A1A1A",
            font_size=104,
        )
        style = generate_style_config(extracted, name="test_style")
        assert isinstance(style, SubtitleStyle)
        assert style.name == "test_style"
        assert style.horizontal is not None
        assert style.vertical is not None
        assert style.horizontal.text_color == "FFFFFF"
        assert style.vertical.text_color == "FFFFFF"

    def test_custom_description(self):
        extracted = ExtractedStyle()
        style = generate_style_config(extracted, name="test", description="Custom desc")
        assert style.description == "Custom desc"

    def test_auto_description(self):
        extracted = ExtractedStyle(bg_enabled=True, bg_color="1A1A1A", text_color="FFFFFF")
        style = generate_style_config(extracted, name="test")
        assert "背景色" in style.description
        assert "文字色" in style.description


class TestSaveStyleYaml:
    def test_yaml_output(self, tmp_path):
        extracted = ExtractedStyle(
            text_color="FFFFFF",
            bg_enabled=True,
            bg_color="1A1A1A",
            font_size=104,
        )
        style = generate_style_config(extracted, name="yaml_test")
        yaml_path = save_style_yaml(style, tmp_path / "yaml_test.yaml")

        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "name: yaml_test" in content
        assert "horizontal:" in content
        assert "vertical:" in content

    def test_yaml_round_trip(self, tmp_path):
        extracted = ExtractedStyle(
            text_color="FF0000",
            bg_enabled=True,
            bg_color="0000FF",
            bg_alpha=200,
            font_size=90,
            outline_width=2.0,
            shadow_depth=1.5,
        )
        style = generate_style_config(extracted, name="roundtrip_test")
        yaml_path = save_style_yaml(style, tmp_path / "roundtrip_test.yaml")

        loaded = load_style("roundtrip_test", styles_dir=tmp_path)
        assert loaded.name == "roundtrip_test"
        assert loaded.horizontal.text_color == "FF0000"
        assert loaded.horizontal.bg_enabled is True
        assert loaded.horizontal.bg_color == "0000FF"
        assert loaded.horizontal.bg_alpha == 200
        assert loaded.horizontal.font_size == 96

    def test_no_numpy_types_in_yaml(self, tmp_path):
        extracted = ExtractedStyle(
            font_size=int(np.int64(80)),
            bold=bool(np.bool_(True)),
            margin_v=int(np.int32(100)),
        )
        style = generate_style_config(extracted, name="type_check")
        yaml_path = save_style_yaml(style, tmp_path / "type_check.yaml")

        content = yaml_path.read_text(encoding="utf-8")
        assert "!!python" not in content


class TestVerifyExtractedStyle:
    def test_verify_generates_ass(self):
        extracted = ExtractedStyle(
            text_color="FFFFFF",
            bg_enabled=True,
            bg_color="1A1A1A",
            font_size=104,
        )
        style = generate_style_config(extracted, name="verify_test")
        results = verify_extracted_style(style)

        assert results["horizontal"]["ass_generated"] is True
        assert results["horizontal"]["has_script_info"] is True
        assert results["horizontal"]["has_events"] is True
        assert results["horizontal"]["has_dialogue"] is True
        assert results["horizontal"]["has_text"] is True

        assert results["vertical"]["ass_generated"] is True
        assert results["vertical"]["has_text"] is True

    def test_verify_with_output_dir(self, tmp_path):
        extracted = ExtractedStyle(font_size=80)
        style = generate_style_config(extracted, name="file_test")
        results = verify_extracted_style(style, output_dir=tmp_path)

        assert "ass_path" in results["horizontal"]
        assert Path(results["horizontal"]["ass_path"]).exists()


class TestExtractAndSave:
    def test_from_image(self, tmp_image, tmp_path):
        style, yaml_path = extract_and_save(
            source=tmp_image,
            output_name="integrated_test",
            output_dir=tmp_path,
        )
        assert isinstance(style, SubtitleStyle)
        assert yaml_path.exists()

    def test_from_video(self, tmp_video, tmp_path):
        style, yaml_path = extract_and_save(
            source=tmp_video,
            output_name="video_test",
            output_dir=tmp_path,
            max_frames=2,
        )
        assert isinstance(style, SubtitleStyle)
        assert yaml_path.exists()

    def test_unsupported_format(self, tmp_path):
        fake_file = tmp_path / "test.xyz"
        fake_file.write_text("fake")
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_and_save(source=fake_file)

    def test_full_pipeline_round_trip(self, tmp_image, tmp_path):
        style, yaml_path = extract_and_save(
            source=tmp_image,
            output_name="full_pipeline",
            output_dir=tmp_path,
        )

        loaded = load_style("full_pipeline", styles_dir=tmp_path)
        assert loaded.name == "full_pipeline"
        assert loaded.horizontal.text_color == style.horizontal.text_color
        assert loaded.horizontal.bg_enabled == style.horizontal.bg_enabled
        assert loaded.horizontal.font_size == style.horizontal.font_size

        results = verify_extracted_style(loaded, output_dir=tmp_path / "verify")
        assert results["horizontal"]["has_text"] is True
        assert results["vertical"]["has_text"] is True


class TestVerticalOverlayContentAspect:
    def test_vertical_overlay_content_aspect_default(self):
        extracted = ExtractedStyle(
            text_color="FFFFFF",
            bg_enabled=True,
            bg_color="1A1A1A",
            font_size=80,
        )
        style = generate_style_config(extracted, name="aspect_test")
        assert style.vertical.overlay_content_aspect == "16:9", \
            f"竖版 overlay_content_aspect 应为 '16:9'，实际为 '{style.vertical.overlay_content_aspect}'"

    def test_vertical_overlay_content_aspect_yaml_round_trip(self, tmp_path):
        extracted = ExtractedStyle(
            text_color="FFFFFF",
            bg_enabled=True,
            bg_color="1A1A1A",
            font_size=80,
        )
        style = generate_style_config(extracted, name="aspect_yaml_test")
        yaml_path = save_style_yaml(style, tmp_path / "aspect_yaml_test.yaml")

        loaded = load_style("aspect_yaml_test", styles_dir=tmp_path)
        assert loaded.vertical.overlay_content_aspect == "16:9", \
            f"YAML round-trip 后竖版 overlay_content_aspect 应为 '16:9'，实际为 '{loaded.vertical.overlay_content_aspect}'"

    def test_existing_ttb_style_has_correct_aspect(self):
        style = load_style("ttb_auto_extracted_optimized")
        assert style.vertical.overlay_content_aspect == "16:9", \
            f"ttb_auto_extracted_optimized 竖版 overlay_content_aspect 应为 '16:9'，实际为 '{style.vertical.overlay_content_aspect}'"
