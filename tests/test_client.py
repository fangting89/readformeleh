from PIL import Image

from pipeline.client import encode_image


def test_encode_image_returns_media_type_and_base64(tmp_path):
    image_path = tmp_path / "letter.jpg"
    Image.new("RGB", (10, 10), "white").save(image_path, "JPEG")

    media_type, data = encode_image(image_path)

    assert media_type == "image/jpeg"
    assert isinstance(data, str)
    assert len(data) > 0
