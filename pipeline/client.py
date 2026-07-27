"""Anthropic client and image encoding.

Now provided by the shared `lehcore` library rather than implemented here:
this and checkformeleh's `rag/config.py` had independently converged on the
identical `get_client`/`require_env` implementation, so it was extracted
into one tested, shared copy (see lehcore's README). Re-exported under the
original names so every other module in this repo keeps working unchanged.
"""

from lehcore.client import DEFAULT_MODEL as MODEL
from lehcore.client import MAX_DIMENSION, encode_image, get_client

__all__ = ["MAX_DIMENSION", "MODEL", "encode_image", "get_client"]
