"""Eval harness for the classify/summarize pipeline.

Why this shape, not an LLM-judge: every specimen in `eval.dataset` is
synthetic with exactly known expected fields (we authored the letter
text), so scoring is exact-substring field matching, not fuzzy grading.
LLM-as-judge is the standard fallback when ground truth can't be matched
this cleanly (e.g. paraphrase-tolerant scoring), and isn't needed here.
Skipping it keeps scoring deterministic and reproducible run to run,
which an LLM-judge call would not be.

Two things are measured, independently:
1. classify_letter: run CLASSIFY_REPEATS times per specimen against the
   known category label. Gives both an accuracy/precision/recall
   confusion matrix AND a consistency ("flip rate") number, which is
   exactly the axis that was silently broken before the temperature=0
   fix (see docs/DESIGN.md).
2. summarize_letter: run SUMMARIZE_REPEATS times per government/
   bill_or_medical specimen, scored by exact-substring match against the
   expected action-needed phrasing, action amount, deadline, and agency
   keywords. Suspicious/unreadable specimens are excluded here, matching
   real pipeline behavior (summarize is only ever called after classify
   clears a letter). The gate itself is scored by classify's suspicious
   recall, not duplicated here.

Usage: `uv run python -m eval.run_eval`
"""

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import TypedDict

from eval.dataset import SPECIMENS, ExpectedCategory, Specimen
from pipeline.classify import classify_letter
from pipeline.summarize import summarize_letter
from pipeline.summary_fields import AMOUNT_RE, date_variants

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

CLASSIFY_REPEATS = 3
SUMMARIZE_REPEATS = 2

CATEGORIES: tuple[ExpectedCategory, ...] = (
    "government",
    "bill_or_medical",
    "suspicious",
    "unreadable",
)

NO_ACTION_PHRASE = "no, nothing to do"


class SummaryChecks(TypedDict):
    """Per-run scoring result from `_score_summary`."""

    action_needed_correct: bool | None
    amount_correct: bool | None
    deadline_correct: bool | None
    agency_mentioned: bool | None
    format_ok: bool
    unexpected_amounts: list[str]


def _run_classify_eval() -> dict:
    """Runs classify_letter CLASSIFY_REPEATS times per specimen.

    Returns:
        A dict with per-class precision/recall/F1 (computed over every
        repeat as an independent trial), overall accuracy, a per-specimen
        consistency ("flip rate") figure, and, separately, how often
        image_quality matched expectations for the specimens where that's
        checked (the gate that prevents summarize from being called on a
        photo that's readable enough to categorize but not to safely
        extract figures from). Shape isn't fixed enough for a TypedDict -
        `per_specimen`/`per_class` are keyed dynamically by specimen/
        category name.
    """
    confusion: Counter[tuple[str, str]] = Counter()  # (expected, predicted)
    per_specimen: dict[str, dict] = {}
    quality_checks: list[bool] = []

    for specimen in SPECIMENS:
        image_path = SAMPLES_DIR / f"{specimen.name}.jpg"
        predictions = []
        quality_predictions = []
        for _ in range(CLASSIFY_REPEATS):
            result = classify_letter(image_path)
            predictions.append(result["category"])
            quality_predictions.append(result["image_quality"])
            confusion[(specimen.expected_category, result["category"])] += 1
            if specimen.expected_image_quality is not None:
                quality_checks.append(
                    result["image_quality"] == specimen.expected_image_quality
                )
        counts = Counter(predictions)
        majority, majority_count = counts.most_common(1)[0]
        per_specimen[specimen.name] = {
            "expected": specimen.expected_category,
            "predictions": predictions,
            "flip_rate": round(1 - majority_count / len(predictions), 3),
            "majority_correct": majority == specimen.expected_category,
            "expected_image_quality": specimen.expected_image_quality,
            "image_quality_predictions": quality_predictions,
        }

    total = sum(confusion.values())
    correct = sum(
        n for (expected, predicted), n in confusion.items() if expected == predicted
    )
    per_class = {}
    for category in CATEGORIES:
        tp = confusion[(category, category)]
        fp = sum(
            n for (e, p), n in confusion.items() if p == category and e != category
        )
        fn = sum(
            n for (e, p), n in confusion.items() if e == category and p != category
        )
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall and (precision + recall)
            else None
        )
        per_class[category] = {
            "precision": _round(precision),
            "recall": _round(recall),
            "f1": _round(f1),
            "support": sum(n for (e, _), n in confusion.items() if e == category),
        }

    return {
        "trials": total,
        "accuracy": _round(correct / total) if total else None,
        "per_class": per_class,
        "image_quality_accuracy": _round(sum(quality_checks) / len(quality_checks))
        if quality_checks
        else None,
        "image_quality_trials": len(quality_checks),
        "per_specimen": per_specimen,
        "note": (
            "suspicious.recall is the safety-critical number: it's the "
            "catch rate on scam specimens. flip_rate > 0 for any specimen "
            "means classify_letter is not fully deterministic at "
            "temperature=0 on that input. image_quality_accuracy is a "
            "second, independent gate: it's what actually decides whether "
            "summarize_letter runs at all (see app/main.py), so it matters "
            "as much as category accuracy for specimens where it's checked."
        ),
    }


def _round(x: float | None) -> float | None:
    """Rounds to 3dp for readable JSON output, passing None through unchanged."""
    return round(x, 3) if x is not None else None


def _score_summary(summary: str, specimen: Specimen) -> SummaryChecks:
    """Scores one summarize_letter output against its specimen's known-correct fields.

    Args:
        summary: The generated summary text to score.
        specimen: The golden-set specimen with known expected fields.

    Returns:
        Per-check pass/fail results. A check is None where the specimen
        doesn't define an expected value for it (not applicable, not a
        failure).
    """
    lower = summary.lower()
    checks: SummaryChecks = {
        "action_needed_correct": None,
        "amount_correct": None,
        "deadline_correct": None,
        "agency_mentioned": None,
        "format_ok": False,
        "unexpected_amounts": [],
    }

    if specimen.expected_action_needed is not None:
        checks["action_needed_correct"] = (
            NO_ACTION_PHRASE not in lower
            if specimen.expected_action_needed
            else NO_ACTION_PHRASE in lower
        )

    checks["amount_correct"] = (
        specimen.expected_action_amount in summary
        if specimen.expected_action_amount is not None
        else None
    )
    checks["deadline_correct"] = (
        any(variant in summary for variant in date_variants(specimen.expected_deadline))
        if specimen.expected_deadline is not None
        else None
    )
    checks["agency_mentioned"] = (
        any(keyword.lower() in lower for keyword in specimen.expected_agency_keywords)
        if specimen.expected_agency_keywords
        else None
    )
    checks["format_ok"] = all(
        label in summary
        for label in ("Action needed:", "What it says:", "By when:", "Note:")
    )

    # Hallucination scan: any dollar figure in the summary that doesn't
    # match the one expected amount is worth a human look, even though a
    # letter can legitimately state other informational figures (e.g. CPF
    # account balances), so this is a flag for review, not a hard failure.
    amounts_in_summary = set(AMOUNT_RE.findall(summary))
    expected_amounts = (
        {specimen.expected_action_amount} if specimen.expected_action_amount else set()
    )
    checks["unexpected_amounts"] = sorted(amounts_in_summary - expected_amounts)

    return checks


def _run_summarize_eval() -> dict:
    """Runs summarize_letter SUMMARIZE_REPEATS times per scorable specimen.

    Only scores specimens the real app would actually pass to
    summarize_letter: expected_category in (government, bill_or_medical)
    AND expected_image_quality != "degraded". A degraded-quality specimen
    is intentionally excluded here even though its category is
    summarizable, matching app/main.py's gate (see eval/dataset.py's note
    on bad_quality_photo for why that gate exists).

    Returns:
        A dict with the count of specimens scored, runs per specimen,
        aggregate pass rates per check (see SummaryChecks), and the raw
        per-specimen results.
    """
    per_specimen: dict[str, dict] = {}
    scorable = [
        s
        for s in SPECIMENS
        if s.expected_category in ("government", "bill_or_medical")
        and s.expected_image_quality != "degraded"
    ]

    for specimen in scorable:
        image_path = SAMPLES_DIR / f"{specimen.name}.jpg"
        runs = []
        for _ in range(SUMMARIZE_REPEATS):
            summary = summarize_letter(image_path, lang="en")
            runs.append(
                {"summary": summary, "checks": _score_summary(summary, specimen)}
            )
        per_specimen[specimen.name] = {"runs": runs}

    # Aggregate pass rates per check across all runs.
    totals: dict[str, list[bool]] = defaultdict(list)
    for entry in per_specimen.values():
        for run in entry["runs"]:
            for check, value in run["checks"].items():
                if isinstance(value, bool):
                    totals[check].append(value)

    pass_rates = {
        check: _round(sum(values) / len(values))
        for check, values in totals.items()
        if values
    }

    return {
        "specimens_scored": len(scorable),
        "runs_per_specimen": SUMMARIZE_REPEATS,
        "pass_rates": pass_rates,
        "per_specimen": per_specimen,
    }


def main() -> None:
    """Runs both classify and summarize evals, prints a report, and saves it to JSON."""
    print(
        f"Running classify eval ({CLASSIFY_REPEATS} repeats x {len(SPECIMENS)} specimens)..."
    )
    started = time.monotonic()
    classify_results = _run_classify_eval()
    print(f"  done in {time.monotonic() - started:.1f}s")

    print("Running summarize eval...")
    started = time.monotonic()
    summarize_results = _run_summarize_eval()
    print(f"  done in {time.monotonic() - started:.1f}s")

    report = {"classify": classify_results, "summarize": summarize_results}

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "latest.json"
    out_path.write_text(json.dumps(report, indent=2))

    print("\n=== classify: per-class precision/recall/F1 ===")
    for category, metrics in classify_results["per_class"].items():
        print(
            f"  {category:16s} precision={metrics['precision']} recall={metrics['recall']} "
            f"f1={metrics['f1']} (support={metrics['support']})"
        )
    print(
        f"  overall accuracy: {classify_results['accuracy']} "
        f"({classify_results['trials']} trials)"
    )

    flips = {
        name: s["flip_rate"]
        for name, s in classify_results["per_specimen"].items()
        if s["flip_rate"] > 0
    }
    print(f"  specimens with any flip across repeats: {flips or 'none'}")
    print(
        f"  image_quality gate accuracy: {classify_results['image_quality_accuracy']} "
        f"({classify_results['image_quality_trials']} trials)"
    )

    print("\n=== summarize: pass rates across all scored runs ===")
    for check, rate in summarize_results["pass_rates"].items():
        print(f"  {check:24s} {rate}")

    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
