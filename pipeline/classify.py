from pathlib import Path
from typing import Literal, TypedDict

from pipeline.client import MODEL, encode_image, get_client

LetterCategory = Literal["government", "bill_or_medical", "suspicious", "unreadable"]


class ClassificationResult(TypedDict):
    category: LetterCategory
    red_flags: list[str]


_TOOL = {
    "name": "classify_letter",
    "description": (
        "Classify a photographed letter and, if suspicious, list the red flags observed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["government", "bill_or_medical", "suspicious", "unreadable"],
            },
            "red_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Only populate when category is 'suspicious'.",
            },
        },
        "required": ["category", "red_flags"],
    },
}

_SYSTEM_PROMPT = """You are screening photographed letters sent to elderly Singaporeans, \
to decide whether it is safe to summarize the letter for them.

Classify into exactly one category:
- government: genuine letter from a Singapore government agency \
(e.g. CPF, IRAS, HDB, a town council).
- bill_or_medical: genuine bill, receipt, or medical/clinic correspondence, not from government.
- suspicious: shows signs of being a scam - e.g. urgent threats, requests for NRIC or bank \
details, unofficial payment channels, generic greetings, pressure tactics.
- unreadable: the image is too blurry, dark, or incomplete to make a confident determination.

When classification is uncertain between government and suspicious, prefer suspicious - \
a false alarm is safer than helping a scam succeed.

If category is suspicious, list the specific red flags you observed. Otherwise return an \
empty list."""


def classify_letter(image_path: Path) -> ClassificationResult:
    """Classifies a photographed letter as the safety gate before summarizing.

    Args:
        image_path: Path to the letter photo (JPEG/PNG/GIF/WebP).

    Returns:
        A `ClassificationResult` with the category and, for suspicious
        letters, the specific red flags observed.
    """
    media_type, data = encode_image(image_path)
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "classify_letter"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    },
                    {"type": "text", "text": "Classify this letter."},
                ],
            }
        ],
    )
    tool_use = next(block for block in response.content if block.type == "tool_use")
    return ClassificationResult(
        category=tool_use.input["category"],
        red_flags=tool_use.input["red_flags"],
    )
