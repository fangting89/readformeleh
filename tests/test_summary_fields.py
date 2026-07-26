"""Tests for pipeline/summary_fields.py's parsing/reconciliation logic.

Pure string logic, no mocking needed. That's the whole point of factoring this
out of pipeline/summarize.py's self-consistency guard."""

from pipeline.summary_fields import (
    HEDGE_SENTENCE,
    date_variants,
    extract_amount_line,
    extract_field,
    reconcile_summaries,
)

SUMMARY = """📬 This letter is from Ang Mo Kio Town Council.
**Action needed:** Yes, pay $89.50 by 25 Jul 2026.
**What it says:** Your conservancy charges are unpaid. Please settle by the due date.
**By when:** 25 Jul 2026
$89.50
**Note:** This is an automated summary. For anything important, please check the \
original letter or contact Ang Mo Kio Town Council directly."""


def test_extract_field_finds_labeled_value():
    assert extract_field(SUMMARY, "By when") == "25 Jul 2026"


def test_extract_field_returns_none_when_label_absent():
    assert extract_field(SUMMARY, "Deadline") is None


def test_extract_amount_line_finds_line_after_by_when():
    assert extract_amount_line(SUMMARY) == "$89.50"


def test_extract_amount_line_returns_none_when_next_line_is_note():
    no_amount = SUMMARY.replace("$89.50\n", "")
    assert extract_amount_line(no_amount) is None


def test_extract_amount_line_returns_none_when_phone_line_is_first_after_by_when():
    no_amount_with_phone = (
        "**By when:** No action needed.\n"
        "Questions? Call Ang Mo Kio Town Council at 6555 1234.\n"
    )
    assert extract_amount_line(no_amount_with_phone) is None


def test_date_variants_includes_abbreviated_and_full_month():
    assert "25 Jul 2026" in date_variants("25 Jul 2026")
    assert "25 July 2026" in date_variants("25 Jul 2026")


def test_date_variants_passthrough_for_unparseable_string():
    assert date_variants("not a date") == ["not a date"]


def test_reconcile_identical_summaries_returned_unchanged():
    assert reconcile_summaries(SUMMARY, SUMMARY) == SUMMARY


def test_reconcile_hedges_deadline_only_on_disagreement():
    secondary = SUMMARY.replace("25 Jul 2026", "26 Jul 2026")
    # keep the amount line agreeing across both reads (only the two
    # "By when:"-adjacent occurrences of the date differ meaningfully here,
    # but the amount line is untouched by this replace since it's "$89.50")
    result = reconcile_summaries(SUMMARY, secondary)
    assert HEDGE_SENTENCE in extract_field(result, "By when")
    assert extract_amount_line(result) == "$89.50"


def test_reconcile_hedges_amount_only_on_disagreement():
    secondary = SUMMARY.replace("$89.50", "$95.00")
    result = reconcile_summaries(SUMMARY, secondary)
    assert extract_field(result, "By when") == "25 Jul 2026"
    assert extract_amount_line(result) == HEDGE_SENTENCE


def test_reconcile_hedges_both_fields_when_both_disagree():
    secondary = SUMMARY.replace("$89.50", "$95.00").replace(
        "25 Jul 2026", "26 Jul 2026"
    )
    result = reconcile_summaries(SUMMARY, secondary)
    assert HEDGE_SENTENCE in extract_field(result, "By when")
    assert extract_amount_line(result) == HEDGE_SENTENCE


def test_reconcile_accepts_equivalent_month_spelling_as_agreement():
    secondary = SUMMARY.replace("25 Jul 2026", "25 July 2026")
    result = reconcile_summaries(SUMMARY, secondary)
    assert extract_field(result, "By when") == "25 Jul 2026"


def test_reconcile_does_not_hedge_field_present_in_only_one_read():
    no_deadline_secondary = SUMMARY.replace("**By when:** 25 Jul 2026", "**By when:** ")
    result = reconcile_summaries(SUMMARY, no_deadline_secondary)
    assert extract_field(result, "By when") == "25 Jul 2026"
