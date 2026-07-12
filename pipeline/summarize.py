from pathlib import Path
from typing import Literal

from pipeline.client import MODEL, encode_image, get_client

Language = Literal["en", "zh"]

_LANGUAGE_NAMES = {"en": "English", "zh": "Mandarin Chinese"}

_STRUCTURES = {
    "en": """📬 This letter is from [agency].
**What it says:** [3-4 short sentences, plain words, no unexpanded acronyms]
**What you need to do:** [action, or "Nothing! ..." if none]
**By when:** [date, or "No action needed."]
[amount involved, if any]""",
    "zh": """📬 这封信来自[机构]。
**信里说什么：** [3-4句简单的话，不用缩写]
**您需要做什么：** [要做的事，如果不需要就写"不需要做任何事！..."]
**截止日期：** [日期，或写"不需要采取任何行动。"]
[如果有金额，写出来]""",
}

_SYSTEM_PROMPT_TEMPLATE = """You write short, plain-language summaries of official letters \
for elderly Singaporean readers, in {language_name}.

Use exactly this structure, including the section labels shown (translated for the \
target language, not left in English):

{structure}

Rules:
- Short lines, one idea per line, key action bolded, no walls of text.
- Simple everyday {language_name}, appropriate for an elderly reader.
- Never state anything not present in the letter itself.
- Never repeat the full NRIC number or full home address, even if visible in the letter.
- If the photo is blurry, angled, or otherwise hard to read and you are not confident \
about a specific date, amount, or other fact, do not guess. Say that detail is unclear \
and the reader should check the original letter, rather than stating a value you're \
not sure of."""


def summarize_letter(image_path: Path, lang: Language = "en") -> str:
    """Summarizes a photographed letter in the fixed elder-friendly format.

    Only call this after `classify_letter` confirms the letter is safe to
    summarize (not `suspicious`).

    Args:
        image_path: Path to the letter photo (JPEG/PNG/GIF/WebP).
        lang: Output language, `"en"` or `"zh"`.

    Returns:
        The formatted plain-language summary.
    """
    media_type, data = encode_image(image_path)
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT_TEMPLATE.format(
            language_name=_LANGUAGE_NAMES[lang], structure=_STRUCTURES[lang]
        ),
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
                    {"type": "text", "text": "Summarize this letter."},
                ],
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text")
