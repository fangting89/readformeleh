from pathlib import Path
from typing import Literal, TypedDict

LetterCategory = Literal["government", "bill_or_medical", "suspicious", "unreadable"]


class ClassificationResult(TypedDict):
    category: LetterCategory
    red_flags: list[str]


def classify_letter(image_path: Path) -> ClassificationResult:
    raise NotImplementedError
