import base64
import mimetypes
from pathlib import Path

import anthropic

from pipeline.config import require_env

MODEL = "claude-sonnet-5"


def get_client() -> anthropic.Anthropic:
    """Returns an Anthropic client authenticated from ANTHROPIC_API_KEY.

    Returns:
        A configured `anthropic.Anthropic` client.

    Raises:
        RuntimeError: If ANTHROPIC_API_KEY is not set.
    """
    return anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))


def encode_image(path: Path) -> tuple[str, str]:
    """Reads an image file and encodes it for the Claude vision API.

    Args:
        path: Path to a JPEG/PNG/GIF/WebP image file.

    Returns:
        A `(media_type, base64_data)` tuple suitable for an API image
        content block.
    """
    media_type = mimetypes.guess_type(path)[0] or "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return media_type, data
