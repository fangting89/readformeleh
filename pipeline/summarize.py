from pathlib import Path
from typing import Literal

Language = Literal["en", "zh"]


def summarize_letter(image_path: Path, lang: Language = "en") -> str:
    raise NotImplementedError
