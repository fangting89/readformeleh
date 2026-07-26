"""Parses and compares fields in summarize_letter's fixed-structure output.

Shared by pipeline/summarize.py's self-consistency guard and eval/run_eval.py's
scoring, so the amount/date-extraction regex used to reconcile two independent
reads and the regex used to score against a known-correct golden value don't
drift into two separate implementations of the same thing.

Pure string logic only: no API calls, no Anthropic import, so everything
here is unit-testable without mocking anything.
"""

import re

HEDGE_SENTENCE = "unclear from this photo, please check the original letter"

AMOUNT_RE = re.compile(r"\$[\d,]+\.\d{2}")

_MONTH_FULL = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
    "Jun": "June", "Jul": "July", "Aug": "August", "Sep": "September",
    "Oct": "October", "Nov": "November", "Dec": "December",
}  # fmt: skip


def date_variants(date_str: str) -> list[str]:
    """Expands a date to both spellings its month could legitimately take.

    A plain equality/substring check without this treats the model's free
    choice of abbreviation ("31 Aug 2026" vs "31 August 2026") as a
    mismatch, which it isn't.

    Args:
        date_str: A date string, e.g. "31 Aug 2026".

    Returns:
        `[date_str]` if it doesn't parse as `DD Mon YYYY`, otherwise both
        the abbreviated and full-month spellings.
    """
    match = re.fullmatch(r"(\d{1,2}) (\w{3,9}) (\d{4})", date_str)
    if not match:
        return [date_str]
    day, month, year = match.groups()
    full = _MONTH_FULL.get(month)
    return [date_str, f"{day} {full} {year}"] if full else [date_str]


def extract_field(summary: str, label: str) -> str | None:
    """Finds the value on the line containing `{label}:`.

    Tolerant of the `**label:**` bold markers the template uses.

    Args:
        summary: A summary produced by `summarize_letter`.
        label: The field label to look for, e.g. "By when".

    Returns:
        The text after the label on its line, or None if the label isn't
        present at all.
    """
    marker = f"{label}:"
    for line in summary.splitlines():
        idx = line.find(marker)
        if idx != -1:
            return line[idx + len(marker) :].strip().lstrip("*").strip()
    return None


def extract_amount_line(summary: str) -> str | None:
    """Finds the structure's optional standalone amount line.

    This is the first non-blank line after "By when:" that isn't the
    conditional phone-number line or the mandatory closing Note line.
    Positional rather than a whole-text regex scan, so a dollar figure
    mentioned in "What it says" isn't mistaken for the dedicated
    action-amount line.

    Args:
        summary: A summary produced by `summarize_letter`.

    Returns:
        The amount line's text, or None if there isn't one.
    """
    lines = summary.splitlines()
    # Find the "By when:" line first - the amount line, if any, is right after it.
    by_when_idx = next((i for i, line in enumerate(lines) if "By when:" in line), None)
    if by_when_idx is None:
        return None
    for line in lines[by_when_idx + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Questions?") or "Note:" in stripped:
            return None
        return stripped
    return None


def _dates_agree(a: str, b: str) -> bool:
    """True if two date strings match exactly or via a month-spelling variant."""
    return a == b or b in date_variants(a) or a in date_variants(b)


def _replace_field(summary: str, label: str, new_value: str) -> str:
    """Replaces a labeled field's value in place.

    Args:
        summary: A summary produced by `summarize_letter`.
        label: The field label to replace the value of, e.g. "By when".
        new_value: The replacement text.

    Returns:
        `summary` with that field's value swapped in, keeping the label
        and its markdown bold markers.
    """
    pattern = re.compile(rf"(\*{{0,2}}{re.escape(label)}:\*{{0,2}}\s*).*")
    return pattern.sub(lambda m: m.group(1) + new_value, summary, count=1)


def _replace_amount_line(summary: str, replacement: str) -> str:
    """Replaces the standalone amount line's text in place.

    Args:
        summary: A summary produced by `summarize_letter`.
        replacement: The replacement text for the amount line.

    Returns:
        `summary` with the amount line swapped in, or unchanged if there
        wasn't one to replace.
    """
    current = extract_amount_line(summary)
    if current is None:
        return summary
    lines = summary.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == current:
            lines[i] = replacement
            break
    return "\n".join(lines)


def reconcile_summaries(primary: str, secondary: str) -> str:
    """Reconciles two independent reads of the same letter photo.

    Compares the By-when and amount fields between the two reads. A
    single disagreeing field is treated as a plausible one-off misread on
    one read, not grounds to hedge the whole summary.

    Args:
        primary: The summary to return (with any disagreeing fields hedged).
        secondary: A second, independent summary of the same photo.

    Returns:
        `primary` with any field that disagrees between the two reads
        replaced by HEDGE_SENTENCE. Fields that agree, or that only
        appear in one read, are left as-is.
    """
    result = primary

    primary_deadline = extract_field(primary, "By when")
    secondary_deadline = extract_field(secondary, "By when")
    if (
        primary_deadline
        and secondary_deadline
        and not _dates_agree(primary_deadline, secondary_deadline)
    ):
        result = _replace_field(result, "By when", HEDGE_SENTENCE)

    primary_amounts = set(AMOUNT_RE.findall(extract_amount_line(primary) or ""))
    secondary_amounts = set(AMOUNT_RE.findall(extract_amount_line(secondary) or ""))
    if primary_amounts and primary_amounts != secondary_amounts:
        result = _replace_amount_line(result, HEDGE_SENTENCE)

    return result
