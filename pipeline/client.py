"""Shared Anthropic client and image encoding helpers."""

import base64
import io
from pathlib import Path

import anthropic
from PIL import Image

from pipeline.config import require_env

MODEL = "claude-haiku-4-5-20251001"

# Claude's vision token cost scales with pixel count; resolution beyond this
# doesn't improve reading accuracy on a document photo, so downscale to it
# before sending rather than paying for unused pixels.
MAX_DIMENSION = 1568


def get_client() -> anthropic.Anthropic:
    """Returns an Anthropic client authenticated from ANTHROPIC_API_KEY.

    Returns:
        A configured `anthropic.Anthropic` client.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set.
    """
    return anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))


def encode_image(path: Path) -> tuple[str, str]:
    """Reads an image file, downscales it, and encodes it for the Claude
    vision API.

    Args:
        path: Path to an image file (any format Pillow can read).

    Returns:
        A `("image/jpeg", base64_data)` tuple suitable for an API image
        content block.
    """
    image = Image.open(path).convert("RGB")
    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    data = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
    return "image/jpeg", data
