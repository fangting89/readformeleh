"""Tests for pipeline/client.py's image encoding."""

import base64
import io

from PIL import Image

from pipeline.client import MAX_DIMENSION, encode_image


def test_encode_image_returns_media_type_and_base64(tmp_path):
    image_path = tmp_path / "letter.jpg"
    Image.new("RGB", (10, 10), "white").save(image_path, "JPEG")

    media_type, data = encode_image(image_path)

    assert media_type == "image/jpeg"
    assert isinstance(data, str)
    assert len(data) > 0


def test_encode_image_downscales_oversized_images(tmp_path):
    image_path = tmp_path / "large.jpg"
    Image.new("RGB", (3000, 4000), "white").save(image_path, "JPEG")

    _, data = encode_image(image_path)

    decoded = Image.open(io.BytesIO(base64.standard_b64decode(data)))
    assert max(decoded.size) <= MAX_DIMENSION


def test_encode_image_leaves_small_images_unresized(tmp_path):
    image_path = tmp_path / "small.jpg"
    Image.new("RGB", (400, 300), "white").save(image_path, "JPEG")

    _, data = encode_image(image_path)

    decoded = Image.open(io.BytesIO(base64.standard_b64decode(data)))
    assert decoded.size == (400, 300)
