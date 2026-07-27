"""CLI entrypoint: classify then summarize a letter photo from the command line."""

import argparse
from pathlib import Path

from pipeline.classify import classify_letter
from pipeline.summarize import summarize_letter_checked, translate_summary


def main() -> None:
    """CLI entrypoint: classify then summarize a letter photo, if safe to."""
    parser = argparse.ArgumentParser(
        description="Summarize a photographed government letter."
    )
    parser.add_argument("photo", type=Path)
    parser.add_argument("--lang", choices=["en", "zh", "ms", "ta"], default="en")
    args = parser.parse_args()

    result = classify_letter(args.photo)
    if result["category"] == "suspicious":
        print(
            f"This letter looks suspicious (scam_type: {result['scam_type']}):",
            ", ".join(result["red_flags"]),
        )
        return
    # Unlike app/main.py, this branch and the one below never escalate to a
    # stronger message after repeated failures: each CLI invocation is a
    # fresh one-shot process with no sender identity to track a streak
    # against, so there's no "consecutive" to count here.
    if result["category"] == "unreadable":
        print("Couldn't read this photo clearly - try a clearer, well-lit shot.")
        return
    if result["image_quality"] == "degraded":
        print(
            f"Category looks like {result['category']}, but the photo is too degraded "
            "to safely read specific figures - try a clearer, well-lit shot."
        )
        return

    # image_quality is "clear" here, so the extra independent read in
    # summarize_letter_checked is warranted (see its docstring). Always
    # computed in English first, then translated, matching app/main.py's
    # webhook path: this is the source of truth for every output language.
    summary_en = summarize_letter_checked(args.photo)
    print(translate_summary(summary_en, args.lang) if args.lang != "en" else summary_en)


if __name__ == "__main__":
    main()
