"""Renders the eval golden set (`eval.dataset.SPECIMENS`) into samples/ as
JPEGs, for pipeline development and for `eval/run_eval.py` to score against.
Re-run whenever `eval/dataset.py` changes."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from eval.dataset import SPECIMENS, Specimen

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _draw_text(text: str) -> Image.Image:
    """Renders plain black-on-white text onto a blank canvas.

    Args:
        text: The letter text to draw.

    Returns:
        An 800x1000 RGB image with the text drawn on it.
    """
    canvas = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=20)
    draw.multiline_text((40, 40), text, fill="black", font=font, spacing=10)
    return canvas


def render_normal(text: str) -> Image.Image:
    """Renders a clean, undegraded letter photo.

    Args:
        text: The letter text to draw.

    Returns:
        The rendered image, unmodified.
    """
    return _draw_text(text)


def render_blurred(text: str) -> Image.Image:
    """Renders a mildly degraded letter photo (slight rotation + blur).

    Args:
        text: The letter text to draw.

    Returns:
        The rendered image, rotated 6 degrees and Gaussian-blurred.
    """
    canvas = _draw_text(text)
    canvas = canvas.rotate(6, expand=True, fillcolor="white")
    return canvas.filter(ImageFilter.GaussianBlur(radius=3))


def render_heavy_blur(text: str) -> Image.Image:
    """Renders a heavily degraded letter photo.

    A harder degradation than render_blurred, which turned out to still
    be confidently readable (see eval/dataset.py note on
    bad_quality_photo). Kept as the specimen that actually exercises the
    unreadable path.

    Args:
        text: The letter text to draw.

    Returns:
        The rendered image, rotated 15 degrees and heavily blurred.
    """
    canvas = _draw_text(text)
    canvas = canvas.rotate(15, expand=True, fillcolor="white")
    return canvas.filter(ImageFilter.GaussianBlur(radius=6))


def render_low_light(text: str) -> Image.Image:
    """Renders a low-light letter photo.

    Low contrast plus blur, not just dimmer. A uniform brightness cut
    preserves the black/white contrast ratio and stays legible to a
    vision model, so this blends toward mid-gray first to actually
    collapse the contrast a bad-lighting phone photo would lose.

    Args:
        text: The letter text to draw.

    Returns:
        The rendered image, contrast-reduced and blurred.
    """
    canvas = _draw_text(text)
    gray = Image.new("RGB", canvas.size, (110, 110, 110))
    low_contrast = Image.blend(canvas, gray, alpha=0.88)
    return low_contrast.filter(ImageFilter.GaussianBlur(radius=4))


def render_partial_crop(text: str) -> Image.Image:
    """Renders a letter photo cropped to hide most of each line.

    Crops away the left half of every line (not just the tail of the
    document) so every line is a word-fragment. A cleanly cropped header
    would still let a model confidently identify the sender, which isn't
    the failure mode this specimen is meant to exercise.

    Args:
        text: The letter text to draw.

    Returns:
        The rendered image, cropped to its right 55%.
    """
    canvas = _draw_text(text)
    width, height = canvas.size
    return canvas.crop((int(width * 0.45), 0, width, height))


_RENDERERS = {
    "normal": render_normal,
    "blurred": render_blurred,
    "heavy_blur": render_heavy_blur,
    "low_light": render_low_light,
    "partial_crop": render_partial_crop,
}


def render_specimen(specimen: Specimen, path: Path) -> None:
    """Renders one specimen using its declared render mode and saves it as a JPEG.

    Args:
        specimen: The specimen to render (uses its `render` and `letter_text`).
        path: Where to save the resulting JPEG.
    """
    image = _RENDERERS[specimen.render](specimen.letter_text)
    image.convert("RGB").save(path, "JPEG")


def main() -> None:
    """Renders every specimen in SPECIMENS into samples/{name}.jpg."""
    SAMPLES_DIR.mkdir(exist_ok=True)
    for specimen in SPECIMENS:
        render_specimen(specimen, SAMPLES_DIR / f"{specimen.name}.jpg")
    print(f"Generated {len(SPECIMENS)} sample letters in {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
