"""Tests for pipeline/summarize.py's summarize_letter_checked wiring.

Only the wiring is tested here (calls summarize_letter twice, reconciles
the results) — reconcile_summaries' own logic is tests/test_summary_fields.py's
job, so this stays a minimal, mocked test rather than re-testing that logic."""

from unittest.mock import patch

from pipeline.summarize import summarize_letter_checked
from pipeline.summary_fields import reconcile_summaries

SUMMARY_A = """**Action needed:** Yes — pay $89.50 by 25 Jul 2026.
**By when:** 25 Jul 2026
$89.50
**Note:** automated summary."""

SUMMARY_B = """**Action needed:** Yes — pay $95.00 by 25 Jul 2026.
**By when:** 25 Jul 2026
$95.00
**Note:** automated summary."""


@patch("pipeline.summarize.summarize_letter", side_effect=[SUMMARY_A, SUMMARY_B])
def test_summarize_letter_checked_calls_summarize_twice(mock_summarize, tmp_path):
    image_path = tmp_path / "letter.jpg"
    summarize_letter_checked(image_path)
    assert mock_summarize.call_count == 2
    for call in mock_summarize.call_args_list:
        assert call.args[0] == image_path
        assert call.kwargs["lang"] == "en"


@patch("pipeline.summarize.summarize_letter", side_effect=[SUMMARY_A, SUMMARY_B])
def test_summarize_letter_checked_reconciles_the_two_reads(mock_summarize, tmp_path):
    result = summarize_letter_checked(tmp_path / "letter.jpg")
    assert result == reconcile_summaries(SUMMARY_A, SUMMARY_B)
